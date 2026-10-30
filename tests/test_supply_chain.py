"""Archive and native-custody regressions independent of analytics imports."""

import importlib.util
import json
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_retains_frozen_provisioning_and_excludes_runtime_secrets(tmp_path):
    package = script("package_sse")
    package.copy_package_files(tmp_path)
    root = tmp_path / package.PACKAGE_ROOT_NAME
    assert (root / "locks" / "core.lock").read_bytes() == (ROOT / "locks" / "core.lock").read_bytes()
    assert (root / "locks" / "deep-learning.lock").is_file()
    assert (root / "scripts" / "pillow_native.py").is_file()
    assert (root / "scripts" / "provision.py").is_file()
    assert not (root / "qlik-py-env").exists()
    assert not (root / ".env").exists()
    assert not (root / ".git").exists()


def test_core_does_not_install_optional_tensorflow():
    assert "tensorflow==" not in (ROOT / "locks" / "core.lock").read_text()
    assert "tensorflow==2.21.0" in (ROOT / "locks" / "deep-learning.lock").read_text()
    assert "pip==26.2.2" in (ROOT / "locks" / "dev.lock").read_text()
    assert "pip==26.2.2" in (ROOT / "locks" / "bootstrap.lock").read_text()


def test_patched_versions_agree_in_every_frozen_bundle():
    from packaging.version import Version
    minimum = {"certifi": "2026.10.19", "urllib3": "2.8.0", "pillow": "13.0.0", "aiohttp": "3.14.4", "anyio": "4.14.2", "multidict": "6.9.1", "yarl": "1.25.1"}
    packages = tomllib.loads((ROOT / "uv.lock").read_text())["package"]
    coordinates = {p["name"]: p["version"] for p in packages if "version" in p}
    assert all(Version(coordinates[name]) >= Version(version) for name, version in minimum.items())
    expected = {name: coordinates[name] for name in minimum}
    for bundle in ("core", "cloud", "deep-learning", "dev"):
        content = (ROOT / "locks" / (bundle + ".lock")).read_text()
        assert all(f"{name}=={version} \\\n    --hash=sha256:" in content for name, version in expected.items())


def test_native_repair_refuses_unknown_wheel_before_build_or_mutation(tmp_path, monkeypatch):
    native = script("pillow_native")
    monkeypatch.setattr(native.platform, "system", lambda: "Linux")
    target = tmp_path / "libbrotlidec.fixture"
    target.write_bytes(b"unreviewed native bytes")
    selected = {"files": {target.name: ("replacement", "0" * 64)}}
    monkeypatch.setattr(native, "policy", lambda: (None, tmp_path, selected))
    with pytest.raises(RuntimeError, match="preimage"):
        native.repair()
    assert target.read_bytes() == b"unreviewed native bytes"


def test_native_probe_refuses_changed_repair_bytes_before_loading(tmp_path, monkeypatch):
    native = script("pillow_native")
    monkeypatch.setattr(native.platform, "system", lambda: "Linux")
    target = tmp_path / "libbrotlidec.fixture"
    target.write_bytes(b"changed bytes")
    receipt = {"source_commit": native.SOURCE_COMMIT, "source_archive_sha256": native.SOURCE_SHA256, "libraries": {target.name: "0" * 64}}
    (tmp_path / "raptor-native-security.json").write_text(json.dumps(receipt))
    package = type("Package", (), {"read_text": lambda _, name: ""})()
    monkeypatch.setattr(native, "policy", lambda: (package, tmp_path, {"files": {target.name: None}}))
    with pytest.raises(RuntimeError, match="bytes differ"):
        native.probe()


def test_unqualified_windows_arm_native_path_cannot_report_acceptance(monkeypatch):
    native = script("pillow_native")
    monkeypatch.setattr(native.platform, "system", lambda: "Windows")
    monkeypatch.setattr(native.platform, "machine", lambda: "ARM64")
    with pytest.raises(RuntimeError, match="qualification unavailable"):
        native.policy()


def test_provisioning_requires_maintained_313_venv(monkeypatch):
    provision = script("provision")
    monkeypatch.setattr(sys, "version_info", (3, 13, 5))
    with pytest.raises(RuntimeError, match="3.13.18"):
        provision.install("core")


@pytest.mark.parametrize("failure", ["preimage", "probe"])
def test_windows_native_repair_preserves_original_on_failure(tmp_path, monkeypatch, failure):
    import csv
    import hashlib
    native = script("pillow_windows")
    root = tmp_path / "PIL"
    root.mkdir()
    target = root / "font.pyd"
    original = b"original wheel bytes"
    target.write_bytes(original)
    record = tmp_path / "pillow-13.0.0.dist-info" / "RECORD"
    record.parent.mkdir()
    with record.open("w", newline="") as output:
        csv.writer(output).writerow(["PIL/font.pyd", *native.record_hash(target)])
    original_record = record.read_bytes()
    inputs = native.load_inputs()
    inputs.update(extension="font.pyd", preimage_sha256=hashlib.sha256(original).hexdigest() if failure == "probe" else "0" * 64)
    monkeypatch.setattr(native, "load_inputs", lambda: inputs)
    package = type("Package", (), {"locate_file": lambda _, path: tmp_path / path})()

    def build(work, _):
        assert failure == "probe", "Unknown preimage must fail before build"
        extension = work / "replacement.pyd"
        extension.write_bytes(b"rebuilt extension")
        prefix = work / "native"
        (prefix / "license").mkdir(parents=True)
        (prefix / "license" / "source.txt").write_text("license")
        (prefix / "extension.map").write_text("map")
        fonts = work / "pillow" / "pillow-13.0.0" / "Tests" / "fonts"
        fonts.mkdir(parents=True)
        (fonts / "OpenSans.woff2").write_bytes(b"fixture")
        return extension, prefix

    monkeypatch.setattr(native, "feature_snapshot", lambda: {"raqm": False, "harfbuzz": False, "fribidi": False})
    monkeypatch.setattr(native, "build", build)
    monkeypatch.setattr(native.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("probe failed")))
    with pytest.raises(RuntimeError, match="preimage" if failure == "preimage" else "probe failed"):
        native.repair(package)
    assert target.read_bytes() == original
    assert record.read_bytes() == original_record
    assert sorted(path.name for path in root.iterdir()) == ["font.pyd"]
