"""Admission checks for operator-managed model artifacts and REST predictions.

These checks do not make pickle/joblib or Keras models safe untrusted uploads.
The model directory, YAML definitions and optional manifest must be writable only
by trusted operators. Importing this module never imports TensorFlow/Keras.
"""

import hashlib
import importlib.metadata
import json
import os
import time
from pathlib import Path

import requests
from packaging.version import Version


def model_name(name):
    if not isinstance(name, str) or not name or name in {".", ".."} or any(c in name for c in "/\\:\x00"):
        raise ValueError("Model name must be a single filename component")
    return name


def model_definition(root, name):
    root = Path(root).resolve()
    path = (root / (model_name(name) + ".yaml")).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Model definition must remain within the model directory")
    return path


def trusted_model_file(filename, expected_sha256=None):
    path = Path(filename).resolve(strict=True)
    if not path.is_file():
        raise ValueError("Model artifact must be a regular local file")
    maximum = int(os.getenv("QLIK_MODEL_MAX_BYTES", str(1024 * 1024 * 1024)))
    if maximum <= 0 or path.stat().st_size > maximum:
        raise ValueError("Model artifact exceeds QLIK_MODEL_MAX_BYTES")
    manifest_path = os.getenv("QLIK_MODEL_MANIFEST")
    if manifest_path:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        approved = manifest.get(str(path))
        if not approved or (expected_sha256 and approved != expected_sha256):
            raise ValueError("Model artifact is not approved by QLIK_MODEL_MANIFEST")
        expected_sha256 = approved
    if expected_sha256:
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            raise ValueError("Model SHA-256 must be a 64-character hexadecimal digest")
        with path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != expected_sha256.lower():
            raise ValueError("Model artifact SHA-256 does not match its approved provenance")
    return path


def load_keras_model(keras, filename):
    path = trusted_model_file(filename)
    if Version(importlib.metadata.version("keras")) < Version("3.15.0"):
        raise RuntimeError("Keras 3.15.0 or later is required for model loading")
    return keras.models.load_model(str(path), safe_mode=True)


def post_prediction(model):
    """Read bounded decoded JSON, retaining Requests' certificate verification.

    The deadline is checked between chunks; the socket read timeout bounds a
    stalled read. It is not a hard CPU/process deadline for an arbitrary decoder.
    urllib3's fixed parser/decoder is therefore required independently.
    """
    maximum = int(os.getenv("QLIK_REST_MAX_RESPONSE_BYTES", str(8 * 1024 * 1024)))
    deadline_seconds = float(os.getenv("QLIK_REST_RESPONSE_SECONDS", "60"))
    if maximum <= 0 or not 0 < deadline_seconds <= 3600:
        raise ValueError("REST response bounds must be positive (deadline at most 3600s)")
    started = time.monotonic()
    with requests.post(**model, stream=True, timeout=(5, 30), allow_redirects=False) as response:
        response.raise_for_status()
        if 300 <= response.status_code < 400:
            raise ValueError("REST model redirects require an explicit endpoint configuration")
        body = bytearray()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if time.monotonic() - started > deadline_seconds:
                raise TimeoutError("REST model response deadline exceeded")
            if len(body) + len(chunk) > maximum:
                raise ValueError("REST model response exceeds QLIK_REST_MAX_RESPONSE_BYTES")
            body.extend(chunk)
        return json.loads(body)
