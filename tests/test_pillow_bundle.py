"""Static admission, original-wheel custody and transactional failure regressions.

Synthetic bytes in these tests never constitute native qualification; Windows CI
separately builds, downloads, applies and executes the real extension/fixtures.
"""

import copy
import csv
import io
import json
import os
import struct
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import approve_pillow_bundle as issuer
import pillow_bundle as bundle
import pillow_native
import provision


def zip_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return output.getvalue()


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    binary = bytearray(128)
    binary[:2] = b"MZ"
    struct.pack_into("<I", binary, 60, 64)
    binary[64:68] = b"PE\0\0"
    struct.pack_into("<H", binary, 68, 0x8664)
    struct.pack_into("<H", binary, 88, 0x20B)
    payload = {name: b"license" for name in bundle.PAYLOAD}
    payload[bundle.EXTENSION] = bytes(binary)
    payload[bundle.FONT] = b"synthetic unit-test font; not native acceptance"
    monkeypatch.setattr(bundle, "FONT_SHA256", bundle.sha(payload[bundle.FONT]))
    inputs = json.loads((bundle.ROOT / "scripts/windows-native-inputs.json").read_text())
    runtime = json.loads((bundle.ROOT / "scripts/windows-native-python.json").read_text())
    identities = bundle.source_files()
    toolchain = {"schema": "qlik.sse.windows-toolchain/v1", "python": "3.13.18", "msvc_version": "test",
        "windows_sdk_version": "test", "compiler_banner": "test", "base_python_sha256": runtime["base_python_sha256"],
        "python_dll_sha256": runtime["python_dll_sha256"], **{n: "a" * 64 for n in
        ("cl_sha256", "link_sha256", "cmake_sha256", "compiler_version_output_sha256", "python_executable_sha256")}}
    native = {"schema": "raptor.sse.native-security/v1", "component": "brotli", "version": "1.2.1",
        "platform": ["Windows", "AMD64"], "source_commit": "db24a98aed38a16de78cc05ca15cdd8dc2a0d92d",
        "source_archive_sha256": inputs["sources"]["brotli"]["sha256"],
        "sources": {n: v["sha256"] for n, v in inputs["sources"].items()},
        "build_recipe_sha256": identities["scripts/pillow_windows.py"]["sha256"],
        "input_manifest_sha256": identities["scripts/windows-native-inputs.json"]["sha256"],
        "libraries": {bundle.EXTENSION.split("/")[-1]: bundle.sha(payload[bundle.EXTENSION])},
        "font_fixture_sha256": bundle.FONT_SHA256, "link_map_sha256": "b" * 64,
        "original_text_features": {"raqm": True, "harfbuzz": True, "fribidi": False}, "toolchain": toolchain}
    producer = {"repository": bundle.REPOSITORY, "repository_id": bundle.REPOSITORY_ID, "workflow": bundle.WORKFLOW,
        "source_commit": "c" * 40, "source_tree": "d" * 40, "run_id": 123, "run_attempt": 1}
    manifest = {"schema": "qlik.sse.windows-native-bundle/v1", "producer": producer, "profile": bundle.PROFILE.copy(),
        "source_files": identities, "files": {n: {"sha256": bundle.sha(v), "size": len(v)} for n, v in payload.items()},
        "native_receipt_sha256": bundle.sha(bundle.json_bytes(native))}
    members = {"manifest.json": bundle.json_bytes(manifest), "native-receipt.json": bundle.json_bytes(native), **payload}
    approval = {"schema": "qlik.sse.approved-native-delivery/v1", "bundle_sha256": bundle.sha(zip_bytes(members)),
        "manifest_sha256": bundle.sha(members["manifest.json"]), "manifest": manifest, "native_receipt": native,
        "github": {"artifact_id": 456, "artifact_name": bundle.artifact_name(producer), "artifact_digest": "e" * 64,
        "run_id": 123, "run_attempt": 1, "producer_commit": producer["source_commit"], "consumer_commit": "f" * 40,
        "producer_tree": producer["source_tree"], "consumer_tree": producer["source_tree"],
        "workflow": bundle.WORKFLOW, "repository": bundle.REPOSITORY}}
    archive = tmp_path / "native.zip"
    archive.write_bytes(zip_bytes(members))
    approved = tmp_path / "approval.json"
    approved.write_bytes(bundle.json_bytes(approval))
    return archive, approved, approval, members


def test_valid_explicit_inputs(delivery):
    archive, approved, approval, _ = delivery
    result = bundle.approved_inputs(archive, approval["bundle_sha256"], approved, bundle.sha(approved.read_bytes()))
    assert result[0] == approval


@pytest.mark.parametrize("field", ["bundle", "approval", "missing"])
def test_independent_digests_before_parsing(delivery, field):
    archive, approved, approval, _ = delivery
    args = [archive, approval["bundle_sha256"], approved, bundle.sha(approved.read_bytes())]
    args[1 if field != "approval" else 3] = None if field == "missing" else "0" * 64
    with pytest.raises(RuntimeError, match="digest"):
        bundle.approved_inputs(*args)


@pytest.mark.parametrize("change", ["source", "abi", "recipe", "input", "runtime", "compiler", "postimage", "font", "tree", "artifact"])
def test_manifest_approval_drift(delivery, change):
    _, _, approval, _ = delivery
    bad = copy.deepcopy(approval)
    if change == "source":
        bad["manifest"]["source_files"]["scripts/pillow_windows.py"]["sha256"] = "0" * 64
    elif change == "abi":
        bad["manifest"]["profile"]["soabi"] = "cp314-win_arm64"
    elif change == "recipe":
        bad["native_receipt"]["build_recipe_sha256"] = "0" * 64
    elif change == "input":
        bad["native_receipt"]["sources"]["brotli"] = "0" * 64
    elif change == "runtime":
        bad["native_receipt"]["toolchain"]["base_python_sha256"] = "0" * 64
    elif change == "compiler":
        del bad["native_receipt"]["toolchain"]["cl_sha256"]
    elif change == "postimage":
        bad["native_receipt"]["libraries"] = {}
    elif change == "font":
        bad["manifest"]["files"][bundle.FONT]["sha256"] = "0" * 64
    elif change == "tree":
        bad["github"]["consumer_tree"] = "0" * 40
    else:
        bad["github"]["artifact_name"] = "foreign"
    with pytest.raises(RuntimeError):
        bundle.validate_approval(bad)


@pytest.mark.parametrize("change", ["extra", "missing", "case", "traversal", "payload", "pe"])
def test_archive_inventory_and_payload_before_load(delivery, change):
    _, _, approval, original = delivery
    members = dict(original)
    if change == "extra":
        members["evil.pyd"] = b"x"
    elif change == "missing":
        del members[bundle.FONT]
    elif change == "case":
        members[bundle.FONT.upper()] = members[bundle.FONT]
    elif change == "traversal":
        members["../evil"] = b"x"
    elif change == "payload":
        members[bundle.EXTENSION] += b"x"
    else:
        members[bundle.EXTENSION] = b"bad pe"
        approval["manifest"]["files"][bundle.EXTENSION] = {"sha256": bundle.sha(b"bad pe"), "size": 6}
        approval["native_receipt"]["libraries"] = {bundle.EXTENSION.split("/")[-1]: bundle.sha(b"bad pe")}
        members["native-receipt.json"] = bundle.json_bytes(approval["native_receipt"])
        approval["manifest"]["native_receipt_sha256"] = bundle.sha(members["native-receipt.json"])
        members["manifest.json"] = bundle.json_bytes(approval["manifest"])
    with pytest.raises(RuntimeError):
        bundle.inspect_bundle(zip_bytes(members))


@pytest.mark.parametrize("kind", ["symlink", "duplicate", "oversize"])
def test_zip_member_type_duplicate_and_budget(kind):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        info = zipfile.ZipInfo("member")
        if kind == "symlink":
            info.create_system = 3
            info.external_attr = 0o120777 << 16
        archive.writestr(info, b"x" * (bundle.MAX_JSON + 1) if kind == "oversize" else b"x")
        if kind == "duplicate":
            archive.writestr("member", b"y")
    with pytest.raises(RuntimeError):
        bundle.read_zip(output.getvalue(), ("member",))


@pytest.fixture
def installed(tmp_path, monkeypatch):
    root = tmp_path / "site-packages"
    (root / "PIL").mkdir(parents=True)
    (root / "pillow-13.0.0.dist-info").mkdir()
    original = {bundle.EXTENSION: b"original", "PIL/__init__.py": b"# vendor", "pillow-13.0.0.dist-info/METADATA": b"Name: pillow"}
    for name, data in original.items():
        (root / name).write_bytes(data)
    rows = [[n, *bundle.record_value(v)] for n, v in original.items()] + [[bundle.RECORD, "", ""]]
    with (root / bundle.RECORD).open("w", newline="") as target:
        csv.writer(target, lineterminator="\n").writerows(rows)
    package = type("Package", (), {"version": "13.0.0", "locate_file": lambda _, path: root / path})()
    monkeypatch.setattr(bundle, "package_root", lambda p: root)
    monkeypatch.setattr(bundle, "wheel_policy", lambda: {n: {"sha256": bundle.sha(v), "size": len(v)} for n, v in original.items()})
    monkeypatch.setattr(bundle, "target_profile", lambda: bundle.PROFILE)
    monkeypatch.setattr(pillow_native, "policy", lambda: (package, root / "PIL", {}))
    monkeypatch.setattr(bundle, "original_features", lambda: {"raqm": False, "harfbuzz": True, "fribidi": False})
    return root, package, original


@pytest.mark.parametrize("change", ["preimage", "python", "record", "extra", "symlink", "hardlink", "record_alias"])
def test_original_installation_custody(installed, change):
    root, package, _ = installed
    if change in ("preimage", "python"):
        (root / (bundle.EXTENSION if change == "preimage" else "PIL/__init__.py")).write_bytes(b"changed")
    elif change == "record":
        (root / bundle.RECORD).write_text("PIL/__init__.py,,\n")
    elif change == "extra":
        (root / "PIL/evil.py").write_bytes(b"x")
    elif change in ("symlink", "hardlink"):
        path = root / bundle.EXTENSION
        backup = root / "backup"
        path.rename(backup)
        if change == "symlink":
            path.symlink_to(backup)
        else:
            os.link(backup, path)
    else:
        with (root / bundle.RECORD).open("a") as target:
            target.write("PIL/__INIT__.py,,\n")
    with pytest.raises(RuntimeError):
        bundle.check_installation(package)


def test_runtime_generated_bytecode_is_never_immutable_vendor(installed):
    root, package, _ = installed
    cache = root / "PIL/__pycache__"
    cache.mkdir()
    (cache / "__init__.cpython-313.pyc").write_bytes(b"runtime-generated")
    bundle.check_installation(package)
    with (root / bundle.RECORD).open("a") as target:
        target.write("PIL/__pycache__/__init__.cpython-313.pyc,,\n")
    (cache / "__init__.cpython-313.pyc").unlink()
    bundle.check_installation(package)


def test_apply_rolls_back_after_probe_failure(delivery, installed, monkeypatch):
    archive, approved, approval, _ = delivery
    root, package, original = installed
    before = (root / bundle.RECORD).read_bytes()
    monkeypatch.setattr(bundle, "isolated_probe", lambda: (_ for _ in ()).throw(RuntimeError("real child failed")))
    with pytest.raises(RuntimeError, match="real child failed"):
        bundle.apply_bundle(archive, approval["bundle_sha256"], approved, bundle.sha(approved.read_bytes()))
    assert (root / bundle.EXTENSION).read_bytes() == original[bundle.EXTENSION]
    assert (root / bundle.RECORD).read_bytes() == before
    assert not (root / bundle.RECEIPT).exists() and not (root / bundle.LICENSE_DIR).exists()
    assert not list(root.glob(".sse-native-transaction-*"))
    bundle.check_installation(package)


def test_apply_retains_backups_on_concurrent_change(delivery, installed, monkeypatch):
    archive, approved, approval, _ = delivery
    root, _, _ = installed
    def changed():
        (root / bundle.EXTENSION).write_bytes(b"concurrent owner")
        raise RuntimeError("probe failed")
    monkeypatch.setattr(bundle, "isolated_probe", changed)
    with pytest.raises(RuntimeError, match="backups retained"):
        bundle.apply_bundle(archive, approval["bundle_sha256"], approved, bundle.sha(approved.read_bytes()))
    assert (root / bundle.EXTENSION).read_bytes() == b"concurrent owner"
    assert (next(root.glob(".sse-native-transaction-*")) / "original-extension").read_bytes() == b"original"


@pytest.mark.parametrize("change", ["pending", "job", "consumer", "tree", "expired", "digest", "repo"])
def test_issuer_rejects_incomplete_authenticated_proof(delivery, change):
    _, _, approval, _ = delivery
    producer = approval["manifest"]["producer"]
    run = {"status": "completed", "conclusion": "success", "path": bundle.WORKFLOW, "event": "pull_request",
        "repository": {"id": bundle.REPOSITORY_ID}, "head_repository": {"id": bundle.REPOSITORY_ID},
        "head_sha": producer["source_commit"], "id": 123}
    artifact = {"expired": False, "workflow_run": {"id": 123, "head_sha": run["head_sha"], "head_repository_id": bundle.REPOSITORY_ID}, "digest": "sha256:" + "a" * 64}
    names = ("frozen-locks", "deep-learning", "security", "optional-extras", "verify (windows-latest)", "verify (macos-latest)",
        "verify (ubuntu-latest, image)", "native-security (windows-latest)", "native-security (macos-latest)", "native-security (ubuntu-latest, image)")
    jobs = [{"id": i + 1, "name": n, "conclusion": "success", "steps": [{"name": "Qualify explicit Windows native bundle", "conclusion": "success"}]} for i, n in enumerate(names)]
    pc = {"sha": run["head_sha"], "tree": {"sha": producer["source_tree"]}}
    cc = {"sha": "f" * 40, "tree": {"sha": producer["source_tree"]}}
    tree = {"sha": producer["source_tree"]}
    proof = {"method": "authenticated-github-job-log", "job_id": jobs[7]["id"], "run_id": 123,
             "log_sha256": "a" * 64, "bundle_sha256": approval["bundle_sha256"]}
    issuer.qualify_evidence(run, artifact, jobs, pc, cc, tree, tree, cc["sha"], proof)
    if change == "pending":
        run["status"] = "in_progress"
    elif change == "job":
        jobs[0]["conclusion"] = "failure"
    elif change == "consumer":
        proof = None
    elif change == "tree":
        cc["tree"]["sha"] = "0" * 40
    elif change == "expired":
        artifact["expired"] = True
    elif change == "digest":
        artifact["digest"] = ""
    else:
        run["head_repository"]["id"] = 0
    with pytest.raises(RuntimeError):
        issuer.qualify_evidence(run, artifact, jobs, pc, cc, tree, tree, cc["sha"], proof)


def test_explicit_provisioning_requires_all_flags_before_pip(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 13, 18))
    monkeypatch.setattr(sys, "prefix", "venv")
    monkeypatch.setattr(provision.subprocess, "run", lambda *a, **k: pytest.fail("pip/preflight must not run"))
    with pytest.raises(RuntimeError, match="both independent digests"):
        provision.install("core", native_bundle="input.zip")


def test_atomic_commit_failure_rolls_back_all_owned_members(delivery, installed, monkeypatch):
    archive, approved, approval, _ = delivery
    root, package, original = installed
    original_record = (root / bundle.RECORD).read_bytes()
    real_link = bundle.os.link
    count = 0
    def fail_link(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 4:
            raise OSError("simulated exclusive publish failure")
        return real_link(*args, **kwargs)
    monkeypatch.setattr(bundle.os, "link", fail_link)
    with pytest.raises(OSError, match="exclusive publish"):
        bundle.apply_bundle(archive, approval["bundle_sha256"], approved, bundle.sha(approved.read_bytes()))
    assert (root / bundle.EXTENSION).read_bytes() == original[bundle.EXTENSION]
    assert (root / bundle.RECORD).read_bytes() == original_record
    assert not list(root.glob(".sse-native-transaction-*"))
    bundle.check_installation(package)


def test_read_rejects_parent_alias_before_bytes(tmp_path):
    parent = tmp_path / "real"
    parent.mkdir()
    (parent / "member").write_bytes(b"x")
    alias = tmp_path / "alias"
    alias.symlink_to(parent, target_is_directory=True)
    with pytest.raises(RuntimeError, match="alias"):
        bundle.read_file(alias / "member", 10)


@pytest.mark.parametrize("profile", [("ARM64", "3.13.18"), ("AMD64", "3.13.19")])
def test_runtime_profile_cannot_fall_back_to_similar_abi(monkeypatch, profile):
    monkeypatch.setattr(bundle.platform, "system", lambda: "Windows")
    monkeypatch.setattr(bundle.platform, "machine", lambda: profile[0])
    monkeypatch.setattr(bundle.platform, "python_version", lambda: profile[1])
    monkeypatch.setattr(bundle.platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(bundle.sysconfig, "get_config_var", lambda key: "cp313-win_amd64" if key == "SOABI" else 0)
    with pytest.raises(RuntimeError, match="runtime/ABI"):
        bundle.target_profile()


@pytest.mark.parametrize("change", ["valid", "command", "bundle", "runtime", "probe", "duplicate", "oversize"])
def test_authenticated_log_requires_actual_consumer_outputs(delivery, change):
    _, _, approval, _ = delivery
    manifest, native = approval["manifest"], approval["native_receipt"]
    probe = dict(native, bundle_delivery={"bundle_sha256": approval["bundle_sha256"], "approval_sha256": "a" * 64})
    result = {"qualification": "CI test fixture only; not operator approval", "profile": copy.deepcopy(bundle.PROFILE),
              "bundle_sha256": approval["bundle_sha256"], "producer": manifest["producer"], "toolchain": native["toolchain"]}
    command = "##[group]Run .ci-consumer/Scripts/python.exe tests/qualify_windows_bundle.py"
    if change == "command":
        command = "##[group]Run skipped.py"
    elif change == "bundle":
        result["bundle_sha256"] = "0" * 64
    elif change == "runtime":
        result["profile"]["python"] = "3.13.16"
    lines = [command, json.dumps(probe), json.dumps(probe), json.dumps(result)]
    if change == "probe":
        del lines[1]
    elif change == "duplicate":
        lines.append(json.dumps(result))
    data = ("\r\n".join("2026-10-30T18:10:20.5963931Z " + line for line in lines)).encode()
    if change == "oversize":
        data = b"x" * (2 * 1024 * 1024 + 1)
    if change == "valid":
        assert issuer.qualify_consumer_log(data, manifest, native, approval["bundle_sha256"], 456, 123)["log_sha256"] == bundle.sha(data)
    else:
        with pytest.raises(RuntimeError):
            issuer.qualify_consumer_log(data, manifest, native, approval["bundle_sha256"], 456, 123)
