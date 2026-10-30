"""Explicit local delivery of one reviewed Windows Pillow native repair.

No downloads, compiler fallback or trust in an embedded manifest alone. The
operator must supply independently approved bundle AND approval-record digests.
Approval records are issued only by approve_pillow_bundle.py after live CI proof.
"""

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import sysconfig
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "jcoggon/qlik-sse-tools"
REPOSITORY_ID = 1162745530
WORKFLOW = ".github/workflows/ci.yml"
PROFILE = {"system": "Windows", "machine": "AMD64", "implementation": "CPython",
           "python": "3.13.18", "soabi": "cp313-win_amd64", "bits": 64, "pillow": "13.0.0"}
MAX_BUNDLE = 16 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024
MAX_JSON = 128 * 1024
MAX_RECORD = 256 * 1024
EXTENSION = "PIL/_imagingft.cp313-win_amd64.pyd"
FONT = "PIL/raptor-native-smoke.woff2"
FONT_SHA256 = "b34551ae25916c460423b82beb8e0675b27f76a9a2908f18286260fbd6de6681"
LICENSE_DIR = "PIL/raptor-native-licenses"
LICENSES = ("zlib-ng-2.3.3.txt", "libpng-1.6.58.txt",
            "brotli-db24a98aed38a16de78cc05ca15cdd8dc2a0d92d.txt", "freetype-2.14.3.txt",
            "harfbuzz-14.5.0.txt", "pillow-test-fonts.txt")
PAYLOAD = (EXTENSION, FONT, *(LICENSE_DIR + "/" + name for name in LICENSES))
MEMBERS = ("manifest.json", "native-receipt.json", *PAYLOAD)
RECEIPT = "PIL/raptor-native-security.json"
APPROVAL = "PIL/raptor-native-bundle-approval.json"
RECORD = "pillow-13.0.0.dist-info/RECORD"
SOURCE_FILES = ("scripts/pillow_windows.py", "scripts/pillow_native.py", "scripts/pillow_bundle.py",
                "scripts/approve_pillow_bundle.py", "scripts/provision.py", "scripts/windows-native-inputs.json",
                "scripts/windows-pillow-wheel.json", "scripts/windows-native-python.json",
                "scripts/prepare_windows_native_python.py", ".github/workflows/ci.yml",
                "tests/qualify_windows_bundle.py", "tests/test_pillow_bundle.py", "locks/core.lock", "locks/bootstrap.lock")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def is_digest(value, length=64):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def decode_json(data):
    require(len(data) <= MAX_JSON, "Native JSON exceeds its dedicated budget")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate native JSON key")
            result[key] = value
        return result
    def constant(_):
        raise RuntimeError("Non-finite native JSON value")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant)


def file_id(path):
    info = path.lstat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def custody(path, directory=False):
    info = Path(path).lstat()
    require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
            "Native file custody rejects symlink/reparse aliases")
    if directory:
        require(stat.S_ISDIR(info.st_mode), "Native parent is not a directory")
    else:
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Native file custody rejects nonregular/shared files")
    return info


def read_file(path, limit, expected=None):
    path = Path(path)
    for parent in path.parents:
        custody(parent, directory=True)
    before = custody(path)
    require(before.st_size <= limit, "Native file exceeds its dedicated budget")
    identity = file_id(path)
    with path.open("rb") as source:
        require((os.fstat(source.fileno()).st_dev, os.fstat(source.fileno()).st_ino) == identity[:2],
                "Native file changed during open")
        data = source.read(limit + 1)
    require(len(data) <= limit and file_id(path) == identity, "Native file changed during read")
    if expected is not None:
        require(is_digest(expected) and sha(data) == expected, "Approved native file digest differs")
    return data


def source_files():
    result = {}
    for name in SOURCE_FILES:
        data = read_file(ROOT / name, 2 * 1024 * 1024)
        result[name] = {"sha256": sha(data), "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
    return result


def target_profile():
    actual = {"system": platform.system(), "machine": platform.machine(),
              "implementation": platform.python_implementation(), "python": platform.python_version(),
              "soabi": sysconfig.get_config_var("SOABI"), "bits": struct.calcsize("P") * 8, "pillow": "13.0.0"}
    require(actual == PROFILE and not sysconfig.get_config_var("Py_GIL_DISABLED"), "Unqualified native bundle runtime/ABI")
    require(sys.prefix != sys.base_prefix, "Native bundle requires a virtual environment")
    policy = decode_json(read_file(ROOT / "scripts/windows-native-python.json", MAX_JSON))
    base = Path(sys._base_executable)
    read_file(base, MAX_EXPANDED, policy["base_python_sha256"])
    read_file(base.with_name("python313.dll"), MAX_EXPANDED, policy["python_dll_sha256"])
    return actual


def payload_limit(name):
    return 16 * 1024 * 1024 if name == EXTENSION else MAX_JSON


def read_zip(data, expected_names, total_limit=MAX_EXPANDED):
    require(len(data) <= MAX_BUNDLE, "Native archive exceeds its dedicated budget")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        require(len(names) == len(set(n.casefold() for n in names)) and set(names) == set(expected_names),
                "Native archive member inventory/alias differs")
        require(sum(i.file_size for i in infos) <= total_limit, "Native archive expanded budget exceeded")
        result = {}
        for info in infos:
            mode = info.external_attr >> 16
            require(not info.is_dir() and not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    and stat.S_IFMT(mode) in (0, stat.S_IFREG) and not info.external_attr & 0x10,
                    "Native archive member type is not a regular unencrypted file")
            limit = payload_limit(info.filename)
            # A transport archive carries the already-compressed native bundle.
            if info.filename == "windows-native-bundle.zip":
                limit = MAX_BUNDLE
            require(0 <= info.file_size <= limit, "Native member budget exceeded")
            with archive.open(info) as source:
                content = source.read(limit + 1)
            require(len(content) == info.file_size and len(content) <= limit, "Native member size differs")
            result[info.filename] = content
        return result


def validate_native(receipt, manifest):
    inputs = decode_json(read_file(ROOT / "scripts/windows-native-inputs.json", MAX_JSON))
    require(receipt.get("schema") == "raptor.sse.native-security/v1" and receipt.get("component") == "brotli"
            and receipt.get("version") == "1.2.1" and receipt.get("platform") == ["Windows", "AMD64"], "Native identity differs")
    require(receipt.get("source_commit") == "db24a98aed38a16de78cc05ca15cdd8dc2a0d92d"
            and receipt.get("source_archive_sha256") == inputs["sources"]["brotli"]["sha256"], "Native source provenance differs")
    require(receipt.get("sources") == {n: s["sha256"] for n, s in inputs["sources"].items()}, "Native source inventory differs")
    require(receipt.get("build_recipe_sha256") == manifest["source_files"]["scripts/pillow_windows.py"]["sha256"]
            and receipt.get("input_manifest_sha256") == manifest["source_files"]["scripts/windows-native-inputs.json"]["sha256"],
            "Native recipe/input bytes differ")
    require(receipt.get("libraries") == {EXTENSION.split("/")[-1]: manifest["files"][EXTENSION]["sha256"]}
            and receipt.get("font_fixture_sha256") == FONT_SHA256, "Native postimage/fixture identity differs")
    require(is_digest(receipt.get("link_map_sha256")), "Native link-map provenance missing")
    require(set(receipt.get("original_text_features", {})) == {"raqm", "harfbuzz", "fribidi"}
            and all(type(v) is bool for v in receipt["original_text_features"].values()), "Native text-feature profile differs")
    toolchain = receipt.get("toolchain", {})
    require(toolchain.get("schema") == "qlik.sse.windows-toolchain/v1" and toolchain.get("python") == "3.13.18"
            and toolchain.get("msvc_version") and toolchain.get("windows_sdk_version") and toolchain.get("compiler_banner"),
            "Native compiler/runtime provenance missing")
    runtime = decode_json(read_file(ROOT / "scripts/windows-native-python.json", MAX_JSON))
    require(toolchain.get("base_python_sha256") == runtime["base_python_sha256"]
            and toolchain.get("python_dll_sha256") == runtime["python_dll_sha256"], "Native runtime supplier differs")
    for field in ("cl_sha256", "link_sha256", "cmake_sha256", "compiler_version_output_sha256", "python_executable_sha256"):
        require(is_digest(toolchain.get(field)), "Native compiler/runtime digest missing")


def validate_manifest(manifest, native):
    require(set(manifest) == {"schema", "producer", "profile", "source_files", "files", "native_receipt_sha256"}
            and manifest["schema"] == "qlik.sse.windows-native-bundle/v1", "Native manifest schema differs")
    require(manifest["profile"] == PROFILE, "Native manifest ABI differs")
    require(manifest["source_files"] == source_files(), "Qualified native consumer/source bytes differ")
    producer = manifest["producer"]
    require(set(producer) == {"repository", "repository_id", "workflow", "source_commit", "source_tree", "run_id", "run_attempt"}
            and producer["repository"] == REPOSITORY and producer["repository_id"] == REPOSITORY_ID
            and producer["workflow"] == WORKFLOW, "Native producer identity differs")
    require(is_digest(producer["source_commit"], 40) and is_digest(producer["source_tree"], 40)
            and type(producer["run_id"]) is int and producer["run_id"] > 0
            and type(producer["run_attempt"]) is int and producer["run_attempt"] > 0, "Native producer source/run identity differs")
    require(set(manifest["files"]) == set(PAYLOAD), "Native payload inventory differs")
    for name, item in manifest["files"].items():
        require(set(item) == {"sha256", "size"} and is_digest(item["sha256"]) and type(item["size"]) is int
                and 0 < item["size"] <= payload_limit(name), "Native payload hash/size differs")
    require(manifest["files"][FONT]["sha256"] == FONT_SHA256, "Native WOFF2 fixture differs")
    validate_native(native, manifest)


def artifact_name(producer):
    return f"sse-windows-native-{producer['source_commit']}-{producer['run_id']}-{producer['run_attempt']}"


def validate_approval(approval):
    require(set(approval) == {"schema", "bundle_sha256", "manifest_sha256", "manifest", "native_receipt", "github"}
            and approval["schema"] == "qlik.sse.approved-native-delivery/v1", "Independent native approval schema differs")
    require(is_digest(approval["bundle_sha256"]) and is_digest(approval["manifest_sha256"]), "Independent native approval digest missing")
    validate_manifest(approval["manifest"], approval["native_receipt"])
    producer = approval["manifest"]["producer"]
    github = approval["github"]
    require(set(github) == {"artifact_id", "artifact_name", "artifact_digest", "run_id", "run_attempt", "producer_commit", "consumer_commit", "producer_tree", "consumer_tree", "workflow", "repository"},
            "GitHub native approval inventory differs")
    require(type(github["artifact_id"]) is int and github["artifact_id"] > 0
            and github["artifact_name"] == artifact_name(producer) and is_digest(github["artifact_digest"])
            and github["run_id"] == producer["run_id"] and github["run_attempt"] == producer["run_attempt"]
            and github["producer_commit"] == producer["source_commit"] and github["producer_tree"] == producer["source_tree"]
            and is_digest(github["consumer_commit"], 40) and github["consumer_tree"] == producer["source_tree"]
            and github["workflow"] == WORKFLOW and github["repository"] == REPOSITORY,
            "Approved GitHub artifact/source binding differs")


def inspect_bundle(data):
    members = read_zip(data, MEMBERS)
    manifest = decode_json(members["manifest.json"])
    native = decode_json(members["native-receipt.json"])
    validate_manifest(manifest, native)
    require(sha(members["native-receipt.json"]) == manifest["native_receipt_sha256"], "Native receipt bytes differ")
    for name in PAYLOAD:
        require(manifest["files"][name] == {"sha256": sha(members[name]), "size": len(members[name])}, "Native payload postimage differs")
    binary = members[EXTENSION]
    require(len(binary) >= 64 and binary[:2] == b"MZ", "Native extension is not PE")
    offset = struct.unpack_from("<I", binary, 60)[0]
    require(offset <= len(binary) - 26 and binary[offset:offset + 4] == b"PE\0\0"
            and struct.unpack_from("<H", binary, offset + 4)[0] == 0x8664
            and struct.unpack_from("<H", binary, offset + 24)[0] == 0x20B, "Native extension PE/AMD64 identity differs")
    return manifest, native, members


def approved_inputs(bundle, bundle_sha256, approval, approval_sha256):
    # Both out-of-band digests are mandatory; neither comes from the ZIP itself.
    require(is_digest(bundle_sha256) and is_digest(approval_sha256), "Independent approved digests are required")
    approved_data = read_file(approval, MAX_JSON, approval_sha256)
    approved = decode_json(approved_data)
    validate_approval(approved)
    require(approved["bundle_sha256"] == bundle_sha256, "Approved whole-bundle digest differs")
    data = read_file(bundle, MAX_BUNDLE, bundle_sha256)
    manifest, native, members = inspect_bundle(data)
    require(manifest == approved["manifest"] and native == approved["native_receipt"]
            and sha(members["manifest.json"]) == approved["manifest_sha256"], "Independent native approval does not describe bundle")
    return approved, approved_data, members


def wheel_policy():
    return decode_json(read_file(ROOT / "scripts/windows-pillow-wheel.json", MAX_JSON))["files"]


def record_value(data):
    return ["sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode(), str(len(data))]


def read_record(path):
    data = read_file(path, MAX_RECORD)
    rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
    require(len(rows) <= 1024 and all(len(row) == 3 for row in rows), "Installed RECORD shape differs")
    names = [row[0] for row in rows]
    require(len(names) == len(set(n.casefold() for n in names)), "Installed RECORD duplicate/alias")
    for name in names:
        require(name == str(PurePosixPath(name)) and not name.startswith("/") and "\\" not in name
                and ":" not in name and not any(p in ("", ".", "..") for p in name.split("/")), "Installed RECORD path differs")
    return data, rows, {row[0]: row[1:] for row in rows}


def package_root(package):
    root = Path(package.locate_file("PIL"))
    prefix = Path(sys.prefix).resolve()
    require(sys.prefix != sys.base_prefix and root.resolve() == root and root.is_relative_to(prefix), "Native package custody/prefix differs")
    for path in (root, *root.parents):
        custody(path, directory=True)
        if path == prefix:
            break
    require(package.version == "13.0.0", "Native bundle requires original Pillow13")
    return root.parent


def check_installation(package, replacements=None, receipt_data=None, approval_data=None):
    root = package_root(package)
    vendor = wheel_policy()
    expected = dict(vendor)
    allowed = {}
    if replacements is not None:
        expected.update(replacements)
        allowed[RECEIPT] = receipt_data
        if approval_data is not None:
            allowed[APPROVAL] = approval_data
    record_data, rows, records = read_record(root / RECORD)
    expected_dirs = {"PIL", "PIL/__pycache__", "pillow-13.0.0.dist-info"}
    for name in [*expected, *allowed, RECORD]:
        expected_dirs.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
    extras = {"pillow-13.0.0.dist-info/" + n for n in ("INSTALLER", "REQUESTED", "direct_url.json")}
    def permitted_generated(name):
        if name in extras:
            return True
        match = re.fullmatch(r"PIL/__pycache__/(\w+)\.cpython-313\.pyc", name)
        return bool(match and "PIL/" + match[1] + ".py" in vendor)
    seen = set()
    for base in ("PIL", "pillow-13.0.0.dist-info"):
        for directory, dirs, files in os.walk(root / base, followlinks=False):
            custody(directory, directory=True)
            for name in dirs:
                path = Path(directory) / name
                custody(path, directory=True)
                require(path.relative_to(root).as_posix() in expected_dirs, "Unreviewed native package directory")
            for name in files:
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                custody(path)
                require(relative in expected or relative in allowed or relative == RECORD or permitted_generated(relative), "Unreviewed native package file")
                seen.add(relative)
    require(set(expected).issubset(seen) and set(allowed).issubset(seen), "Original wheel/native members missing")
    require(all(name in seen or permitted_generated(name) and name.endswith(".pyc") for name in records)
            and all(name in records or permitted_generated(name) and name.endswith(".pyc") for name in seen),
            "Installed RECORD inventory differs")
    for name in (seen | set(records)) - set(expected) - set(allowed) - {RECORD}:
        require(permitted_generated(name), "Unreviewed installed RECORD member")
        if name.endswith(".pyc"):
            # Caches are mutable and never read by our isolated fresh-cache probes.
            require(records.get(name, ["", ""]) == ["", ""], "Unexpected bytecode RECORD digest")
            if name in seen:
                read_file(root / name, 2 * 1024 * 1024)
        else:
            data = read_file(root / name, MAX_JSON)
            require(records[name] == record_value(data), "Installer metadata RECORD differs")
            if name.endswith("/INSTALLER"):
                require(data == b"pip\n", "Unreviewed wheel installer")
            elif name.endswith("/REQUESTED"):
                require(data == b"", "Unreviewed installer request marker")
            else:
                direct = decode_json(data)
                require(set(direct) == {"url", "archive_info"} and isinstance(direct["url"], str)
                        and isinstance(direct["archive_info"], dict), "Unreviewed direct wheel metadata")
    for name, item in expected.items():
        data = read_file(root / name, MAX_EXPANDED, item["sha256"])
        require(len(data) == item["size"] and records[name] == record_value(data), "Original wheel/installed RECORD differs")
    for name, data in allowed.items():
        actual = read_file(root / name, MAX_JSON)
        require(actual == data, "Installed native receipt/approval bytes differ")
        if approval_data is not None:
            require(records[name] == record_value(data), "Installed native receipt/approval RECORD differs")
    require(records.get(RECORD) == ["", ""], "Installed RECORD self-entry differs")
    return root, record_data, rows


def isolated_probe():
    with tempfile.TemporaryDirectory(prefix="sse-native-probe-") as cache:
        subprocess.run([sys.executable, "-I", "-B", "-X", "pycache_prefix=" + cache,
                        str(Path(__file__).with_name("pillow_native.py")), "--probe"], check=True)


def original_features():
    with tempfile.TemporaryDirectory(prefix="sse-native-original-") as cache:
        result = subprocess.check_output([
            sys.executable, "-I", "-B", "-X", "pycache_prefix=" + cache, "-c",
            "import json; from PIL import features; print(json.dumps({f:features.check(f) for f in ('raqm','harfbuzz','fribidi')}))",
        ], text=True)
    return decode_json(result.encode())


def verify_delivery(package, receipt):
    target_profile()
    root = package_root(package)
    delivery = receipt["bundle_delivery"]
    require(set(delivery) == {"bundle_sha256", "approval_sha256"}, "Installed native delivery shape differs")
    approved_data = read_file(root / APPROVAL, MAX_JSON, delivery["approval_sha256"])
    approved = decode_json(approved_data)
    validate_approval(approved)
    require(delivery["bundle_sha256"] == approved["bundle_sha256"], "Installed native bundle identity differs")
    producer_receipt = approved["native_receipt"]
    require({k: v for k, v in receipt.items() if k not in ("bundle_delivery", "original_text_features")}
            == {k: v for k, v in producer_receipt.items() if k != "original_text_features"}, "Installed native producer provenance differs")
    require(set(receipt.get("original_text_features", {})) == {"raqm", "harfbuzz", "fribidi"}
            and all(type(v) is bool for v in receipt["original_text_features"].values()), "Installed original feature profile differs")
    check_installation(package, approved["manifest"]["files"], json_bytes(receipt), approved_data)


def apply_bundle(bundle, bundle_sha256, approval, approval_sha256):
    target_profile()
    approved, approved_data, members = approved_inputs(bundle, bundle_sha256, approval, approval_sha256)
    import pillow_native
    package, _, _ = pillow_native.policy()
    root = package_root(package)
    if (root / RECEIPT).exists():
        receipt = decode_json(read_file(root / RECEIPT, MAX_JSON))
        require(receipt.get("bundle_delivery") == {"bundle_sha256": bundle_sha256, "approval_sha256": approval_sha256},
                "Existing native repair is not this approved delivery")
        verify_delivery(package, receipt)
        isolated_probe()
        return
    root, original_record, rows = check_installation(package)
    original = read_file(root / EXTENSION, 16 * 1024 * 1024)
    original_identity = file_id(root / EXTENSION), file_id(root / RECORD)
    features = original_features()
    receipt = dict(approved["native_receipt"], original_text_features=features,
                   bundle_delivery={"bundle_sha256": bundle_sha256, "approval_sha256": approval_sha256})
    files = {name: members[name] for name in PAYLOAD}
    files[APPROVAL] = approved_data
    files[RECEIPT] = json_bytes(receipt)
    work = Path(tempfile.mkdtemp(prefix=".sse-native-transaction-", dir=root))
    completed = False
    committed = {}
    committed_ids = {}
    parent_ids = {path: file_id(path)[:2] for path in (root, root / "PIL", root / "pillow-13.0.0.dist-info")}
    def check_parents():
        for path, identity in parent_ids.items():
            custody(path, directory=True)
            require(file_id(path)[:2] == identity, "Native transaction parent custody changed; backups retained at " + str(work))
    created_license = False
    try:
        (work / "original-extension").write_bytes(original)
        (work / "original-RECORD").write_bytes(original_record)
        for name, data in files.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        new_rows = [row if row[0] != EXTENSION else [EXTENSION, *record_value(files[EXTENSION])] for row in rows]
        new_rows.extend([name, *record_value(data)] for name, data in files.items() if name != EXTENSION)
        output = io.StringIO()
        csv.writer(output, lineterminator="\n").writerows(new_rows)
        new_record = output.getvalue().encode()
        (work / "new-RECORD").write_bytes(new_record)
        check_installation(package)
        require(original_identity == (file_id(root / EXTENSION), file_id(root / RECORD)), "Native preimage changed before commit")
        (root / LICENSE_DIR).mkdir()
        created_license = True
        parent_ids[root / LICENSE_DIR] = file_id(root / LICENSE_DIR)[:2]
        for name, data in files.items():
            check_parents()
            path = root / name
            if name == EXTENSION:
                os.replace(work / name, path)
            else:
                # Atomic exclusive publication of complete staged bytes on the
                # same volume. Existing names are never overwritten; no partial
                # new member can be left by a failing write.
                os.link(work / name, path)
            committed[name] = data
            committed_ids[name] = file_id(path)
            if name != EXTENSION:
                (work / name).unlink()
        check_parents()
        os.replace(work / "new-RECORD", root / RECORD)
        committed[RECORD] = new_record
        committed_ids[RECORD] = file_id(root / RECORD)
        verify_delivery(package, receipt)
        isolated_probe()
        verify_delivery(package, receipt)
        completed = True
    except BaseException:
        # Restore only bytes still owned by this transaction; never clobber a
        # concurrent change. Retain backups if custody prevents safe rollback.
        check_parents()
        for name, data in committed.items():
            require(file_id(root / name) == committed_ids[name] and read_file(root / name, MAX_EXPANDED) == data,
                    "Rollback custody changed; backups retained at " + str(work))
        if EXTENSION in committed:
            os.replace(work / "original-extension", root / EXTENSION)
        if RECORD in committed:
            os.replace(work / "original-RECORD", root / RECORD)
        for name in committed:
            if name not in (EXTENSION, RECORD):
                (root / name).unlink()
        if created_license:
            (root / LICENSE_DIR).rmdir()
        check_installation(package)
        completed = True
        raise
    finally:
        if completed:
            shutil.rmtree(work)


def export_bundle(output):
    target_profile()
    import pillow_native
    isolated_probe()
    package, _, _ = pillow_native.policy()
    root = package_root(package)
    receipt_data = read_file(root / RECEIPT, MAX_JSON)
    receipt = decode_json(receipt_data)
    require("bundle_delivery" not in receipt, "Producer must use source-built native repair")
    files = {name: read_file(root / name, payload_limit(name)) for name in PAYLOAD}
    coordinates = {name: {"sha256": sha(data), "size": len(data)} for name, data in files.items()}
    check_installation(package, coordinates, receipt_data)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    producer = {"repository": os.environ.get("GITHUB_REPOSITORY"), "repository_id": int(os.environ.get("GITHUB_REPOSITORY_ID", "0")),
                "workflow": WORKFLOW, "source_commit": git("rev-parse", "HEAD"), "source_tree": git("rev-parse", "HEAD^{tree}"),
                "run_id": int(os.environ.get("GITHUB_RUN_ID", "0")), "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0"))}
    require(not git("status", "--porcelain", "--untracked-files=no"), "Producer tracked checkout is not clean")
    identities = source_files()
    for name, item in identities.items():
        require(git("rev-parse", "HEAD:" + name) == item["git_blob"], "Producer checkout source bytes differ from Git")
    manifest = {"schema": "qlik.sse.windows-native-bundle/v1", "producer": producer, "profile": PROFILE,
                "source_files": identities, "files": coordinates, "native_receipt_sha256": sha(receipt_data)}
    validate_manifest(manifest, receipt)
    output = Path(output)
    output.mkdir(exist_ok=False)
    with zipfile.ZipFile(output / "windows-native-bundle.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in {"manifest.json": json_bytes(manifest), "native-receipt.json": receipt_data, **files}.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
    bundle = read_file(output / "windows-native-bundle.zip", MAX_BUNDLE)
    inspect_bundle(bundle)
    # Receipt is outside the native ZIP. It is transport evidence, NOT approval.
    (output / "producer-receipt.json").write_bytes(json_bytes({"schema": "qlik.sse.native-producer-receipt/v1",
        "bundle_sha256": sha(bundle), "manifest_sha256": sha(json_bytes(manifest)), "producer": producer,
        "profile": PROFILE, "toolchain": receipt["toolchain"], "artifact_name": artifact_name(producer)}))
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output_file:
            output_file.write("artifact_name=" + artifact_name(producer) + "\n" + "bundle_sha256=" + sha(bundle) + "\n")
    print(json.dumps({"bundle_sha256": sha(bundle), "artifact_name": artifact_name(producer)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--output", required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--bundle", required=True)
    apply.add_argument("--bundle-sha256", required=True)
    apply.add_argument("--approval", required=True)
    apply.add_argument("--approval-sha256", required=True)
    sub.add_parser("inspect-original")
    args = parser.parse_args()
    if args.command == "export":
        export_bundle(args.output)
    elif args.command == "apply":
        apply_bundle(args.bundle, args.bundle_sha256, args.approval, args.approval_sha256)
    else:
        target_profile()
        import pillow_native
        package, _, _ = pillow_native.policy()
        check_installation(package)
        print("Original reviewed Windows Pillow wheel/RECORD verified")


if __name__ == "__main__":
    main()
