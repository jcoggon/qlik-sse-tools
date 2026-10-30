"""Controlled local fixtures for the changed HTTP and model trust boundaries."""

import gzip
import hashlib
import json
import sys
import threading
import ssl
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "core"), str(ROOT / "generated")]
import _security as security  # noqa: E402


@pytest.fixture
def endpoint():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/normal")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            body = b'{"prediction": 42}'
            if self.path == "/gzip":
                body = gzip.compress(json.dumps({"value": "x" * 16384}).encode())
                self.send_header("Content-Encoding", "gzip")
            if self.path == "/chunked":
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(b"12\r\n{\"prediction\": 42}\r\n0\r\n\r\n")
                return
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_normal_and_chunked_predictions(endpoint):
    for path in ("/normal", "/chunked"):
        assert security.post_prediction({"url": endpoint + path, "json": {"x": 1}}) == {"prediction": 42}


def test_decoded_response_limit_and_redirect(endpoint, monkeypatch):
    monkeypatch.setenv("QLIK_REST_MAX_RESPONSE_BYTES", "512")
    with pytest.raises(ValueError, match="exceeds"):
        security.post_prediction({"url": endpoint + "/gzip"})
    with pytest.raises(ValueError, match="redirect"):
        security.post_prediction({"url": endpoint + "/redirect"})


def test_request_controls_close_on_failure(monkeypatch):
    response = Mock(status_code=200)
    response.iter_content.return_value = [b"x" * 10]
    manager = Mock()
    manager.__enter__ = Mock(return_value=response)
    manager.__exit__ = Mock(return_value=False)
    post = Mock(return_value=manager)
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setenv("QLIK_REST_MAX_RESPONSE_BYTES", "5")
    with pytest.raises(ValueError):
        security.post_prediction({"url": "https://model.invalid"})
    assert post.call_args.kwargs == {"url": "https://model.invalid", "stream": True, "timeout": (5, 30), "allow_redirects": False}
    manager.__exit__.assert_called_once()


def test_response_deadline(monkeypatch):
    response = Mock(status_code=200)
    response.iter_content.return_value = [b"{}"]
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(requests, "post", Mock(return_value=response))
    monkeypatch.setattr(security.time, "monotonic", Mock(side_effect=[0, 61]))
    with pytest.raises(TimeoutError):
        security.post_prediction({"url": "https://model.invalid"})


def test_artifact_manifest_refuses_unapproved_or_changed_bytes(tmp_path, monkeypatch):
    artifact = tmp_path / "model.h5"
    artifact.write_bytes(b"controlled model fixture")
    manifest = tmp_path / "approved.json"
    manifest.write_text(json.dumps({str(artifact): hashlib.sha256(artifact.read_bytes()).hexdigest()}))
    monkeypatch.setenv("QLIK_MODEL_MANIFEST", str(manifest))
    assert security.trusted_model_file(artifact) == artifact
    artifact.write_bytes(b"changed")
    loader = Mock()
    with pytest.raises(ValueError, match="SHA-256"):
        security.load_keras_model(SimpleNamespace(models=SimpleNamespace(load_model=loader)), artifact)
    loader.assert_not_called()
    other = tmp_path / "other.h5"
    other.write_bytes(b"other")
    with pytest.raises(ValueError, match="not approved"):
        security.trusted_model_file(other)


@pytest.mark.parametrize("name", ["../model", "a/b", "a\\b", "", "..", "a\x00b"])
def test_model_names_cannot_traverse_directories(name):
    with pytest.raises(ValueError):
        security.model_name(name)


def test_model_definition_cannot_follow_external_symlink(tmp_path):
    directory = tmp_path / "models"
    directory.mkdir()
    outside = tmp_path / "outside.yaml"
    outside.write_text("type: keras")
    try:
        (directory / "model.yaml").symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires permission on this platform")
    with pytest.raises(ValueError):
        security.model_definition(directory, "model")


def test_keras_baseline_and_safe_mode(tmp_path, monkeypatch):
    artifact = tmp_path / "trusted.h5"
    artifact.write_bytes(b"fixture")
    loader = Mock(return_value="model")
    keras = SimpleNamespace(models=SimpleNamespace(load_model=loader))
    monkeypatch.setattr(security.importlib.metadata, "version", lambda _: "3.13.2")
    with pytest.raises(RuntimeError, match="3.15.0"):
        security.load_keras_model(keras, artifact)
    loader.assert_not_called()
    monkeypatch.setattr(security.importlib.metadata, "version", lambda _: "3.15.0")
    assert security.load_keras_model(keras, artifact) == "model"
    loader.assert_called_once_with(str(artifact), safe_mode=True)


def test_model_size_rejected_before_loading(tmp_path, monkeypatch):
    artifact = tmp_path / "model.h5"
    artifact.write_bytes(b"123456")
    monkeypatch.setenv("QLIK_MODEL_MAX_BYTES", "5")
    with pytest.raises(ValueError, match="exceeds"):
        security.trusted_model_file(artifact)


def test_certifi_removed_emsign_roots():
    import certifi
    import ssl
    context = ssl.create_default_context(cafile=certifi.where())
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert not any("emsign ecc root ca - g3" in str(cert["subject"]).lower() for cert in context.get_ca_certs())


def test_rest_rejects_untrusted_tls_certificate(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(minutes=5))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip_address("127.0.0.1"))]), critical=False)
            .sign(key, hashes.SHA256()))
    certificate = tmp_path / "fixture.pem"
    certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM) + key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate)
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(requests.exceptions.SSLError):
            security.post_prediction({"url": f"https://127.0.0.1:{server.server_port}"})
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_async_dependency_compatibility(endpoint):
    import aiohttp
    import anyio
    from multidict import CIMultiDict

    async def exchange():
        send, receive = anyio.create_memory_object_stream(1)
        async with send, receive:
            await send.send("bounded")
            assert await receive.receive() == "bounded"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=2)) as client:
            async with client.post(endpoint + "/normal") as response:
                assert await response.json() == {"prediction": 42}

    anyio.run(exchange)
    value = object()
    mapping = CIMultiDict({"Header": value})
    before = sys.getrefcount(value)
    for _ in range(1000):
        result = mapping.items() - {("Other", value)}
        del result
        result = {("Other", value)} | mapping.items()
        del result
    assert sys.getrefcount(value) == before
