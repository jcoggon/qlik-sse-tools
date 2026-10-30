import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

import grpc
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from grpc_health.v1 import health_pb2, health_pb2_grpc


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
GENERATED = ROOT / "generated"
sys.path.insert(0, str(GENERATED))

import ServerSideExtension_pb2 as SSE  # noqa: E402
import ServerSideExtension_pb2_grpc as SSE_grpc  # noqa: E402


def _free_port():
    with socket.socket() as sock:
        sock.bind(("0.0.0.0", 0))
        return sock.getsockname()[1]


def _server_env():
    env = os.environ.copy()
    env.pop("QLIK_SSE_HOST", None)
    env["PYTHONPATH"] = os.pathsep.join([str(CORE), str(GENERATED), env.get("PYTHONPATH", "")])
    return env


def _start_server(port, *, args=(), connect_host="127.0.0.1", credentials=None, env_updates=None):
    process_log = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-u", "__main__.py", "--port", str(port), "--workers", "2", *args],
        cwd=CORE,
        env={**_server_env(), **(env_updates or {})},
        stdout=process_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    target = f"[{connect_host}]:{port}" if ":" in connect_host else f"{connect_host}:{port}"
    channel = grpc.secure_channel(target, credentials) if credentials else grpc.insecure_channel(target)
    try:
        grpc.channel_ready_future(channel).result(timeout=30)
    except Exception:
        channel.close()
        process.terminate()
        process.wait(timeout=10)
        process_log.seek(0)
        output = process_log.read()
        process_log.close()
        raise AssertionError(f"SSE server did not become ready:\n{output}")
    return process, channel, process_log


def _stop_server(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        process.terminate()
    else:
        process.send_signal(signal.SIGINT)
    try:
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=5)


def test_diagnostics_command_reports_runtime_state():
    result = subprocess.run(
        [sys.executable, "__main__.py", "--check"],
        cwd=CORE,
        env=_server_env(),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["status"] == "ok"
    assert payload["version"] == "3.1.0"
    assert payload["function_count"] >= 59
    assert all(payload["modules"].values())
    assert payload["host"] == "127.0.0.1"
    assert payload["bind_address"] == f"127.0.0.1:{payload['port']}"


def test_grpc_health_capabilities_and_function_execution():
    port = _free_port()
    process, channel, process_log = _start_server(port)
    try:
        health_stub = health_pb2_grpc.HealthStub(channel)
        health_response = health_stub.Check(
            health_pb2.HealthCheckRequest(service="qlik.sse.Connector"), timeout=5
        )
        assert health_response.status == health_pb2.HealthCheckResponse.SERVING

        # A same-host Qlik connection alone would also work against a wildcard
        # listener. Check a real non-loopback interface when this runner has one.
        host = _local_ipv4()
        if host:
            try:
                external_socket = socket.create_connection((host, port), timeout=1)
            except OSError:
                pass
            else:
                external_socket.close()
                pytest.fail("Default SSE listener accepted a non-loopback connection")

        stub = SSE_grpc.ConnectorStub(channel)
        capabilities = stub.GetCapabilities(SSE.Empty(), timeout=5)
        assert capabilities.pluginIdentifier == "Qlik Python Tools"
        assert capabilities.pluginVersion == "v3.1.0"
        assert len(capabilities.functions) >= 59

        function_header = SSE.FunctionRequestHeader(functionId=4, version="1")
        common_header = SSE.CommonRequestHeader(
            appId="integration-test",
            userId="UserDirectory=LOCAL; UserId=ci",
            cardinality=1,
        )
        request = SSE.BundledRows(
            rows=[SSE.Row(duals=[SSE.Dual(strData="1;2;3;4"), SSE.Dual(strData="2;4;6;8")])]
        )
        response = list(
            stub.ExecuteFunction(
                iter([request]),
                metadata=[
                    ("qlik-functionrequestheader-bin", function_header.SerializeToString()),
                    ("qlik-commonrequestheader-bin", common_header.SerializeToString()),
                ],
                timeout=5,
            )
        )
        values = [dual.numData for bundle in response for row in bundle.rows for dual in row.duals]
        assert values == [1.0]
    finally:
        channel.close()
        _stop_server(process)
        process_log.close()


def _local_ipv4():
    try:
        addresses = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        return None
    return next((item[4][0] for item in addresses if not ipaddress.ip_address(item[4][0]).is_loopback), None)


def test_ipv6_cli_bind_overrides_environment():
    try:
        with socket.socket(socket.AF_INET6) as sock:
            sock.bind(("::1", 0))
            port = sock.getsockname()[1]
    except OSError:
        pytest.skip("Runner has no IPv6 loopback")
    process, channel, process_log = _start_server(
        port, args=("--host", "::1"), connect_host="::1", env_updates={"QLIK_SSE_HOST": "0.0.0.0"},
    )
    try:
        response = health_pb2_grpc.HealthStub(channel).Check(health_pb2.HealthCheckRequest(), timeout=5)
        assert response.status == health_pb2.HealthCheckResponse.SERVING
    finally:
        channel.close()
        _stop_server(process)
        process_log.close()


def _tls_fixture(directory, server_ip):
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SSE test CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .sign(ca_key, hashes.SHA256()))

    def identity(name, usage, address=None):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        builder = (x509.CertificateBuilder()
                   .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
                   .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
                   .add_extension(x509.ExtendedKeyUsage([usage]), critical=False))
        if address:
            builder = builder.add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(address))]), critical=False)
        cert = builder.sign(ca_key, hashes.SHA256())
        return (key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()), cert.public_bytes(serialization.Encoding.PEM))

    server_key, server_cert = identity("SSE test server", ExtendedKeyUsageOID.SERVER_AUTH, server_ip)
    client_key, client_cert = identity("SSE test client", ExtendedKeyUsageOID.CLIENT_AUTH)
    ca_pem = ca.public_bytes(serialization.Encoding.PEM)
    for name, data in {"sse_server_key.pem": server_key, "sse_server_cert.pem": server_cert, "root_cert.pem": ca_pem}.items():
        (directory / name).write_bytes(data)
    return ca_pem, client_key, client_cert


def test_explicit_wildcard_bind_preserves_mutual_tls(tmp_path):
    host = _local_ipv4() or "127.0.0.1"
    root, key, cert = _tls_fixture(tmp_path, host)
    credentials = grpc.ssl_channel_credentials(root_certificates=root, private_key=key, certificate_chain=cert)
    port = _free_port()
    process, channel, process_log = _start_server(
        port, args=("--host", "0.0.0.0", "--pem_dir", str(tmp_path), "--require_tls"),
        connect_host=host, credentials=credentials,
    )
    try:
        response = health_pb2_grpc.HealthStub(channel).Check(health_pb2.HealthCheckRequest(), timeout=5)
        assert response.status == health_pb2.HealthCheckResponse.SERVING
        with grpc.secure_channel(f"{host}:{port}", grpc.ssl_channel_credentials(root_certificates=root)) as unauthenticated:
            with pytest.raises(grpc.RpcError):
                health_pb2_grpc.HealthStub(unauthenticated).Check(health_pb2.HealthCheckRequest(), timeout=2)
    finally:
        channel.close()
        _stop_server(process)
        process_log.close()
