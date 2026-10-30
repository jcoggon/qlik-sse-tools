"""Qualify/repair Pillow's independent Brotli copy, never the system library.

Linux policy and source pin derive from Gateway 54d1af2's reviewed repair.
Unreviewed wheels/platforms fail closed. Run in the target virtual environment.
"""

import argparse
import base64
import csv
import ctypes
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

SOURCE_COMMIT = "db24a98aed38a16de78cc05ca15cdd8dc2a0d92d"
SOURCE_SHA256 = "113b9685dfc14dd2f3360d077283266eec2fbdfb0fe3e5600f11be151da0d68e"
SOURCE_URL = f"https://github.com/google/brotli/archive/{SOURCE_COMMIT}.tar.gz"
POLICIES = {
    ("Linux", "x86_64"): {
        "root": "pillow.libs",
        "files": {
            "libbrotlicommon-53534446.so.1.2.0": ("libbrotlicommon.so.1.2.1", "72c1ab487e4bd44c906336747bf1926cbf5f164f9d05e0b4fd18b7d8d113b7fe"),
            "libbrotlidec-7e5462ba.so.1.2.0": ("libbrotlidec.so.1.2.1", "1b497acc3d8d8e1fc286088f0c288be7c0c54bf5a8fa94b12b23e54de205d48c"),
        },
    },
    ("Darwin", "arm64"): {
        "root": "PIL/.dylibs",
        "files": {
            "libbrotlicommon.1.2.0.dylib": ("libbrotlicommon.1.2.1.dylib", "3f4843c17f3cccc986279a4c9ac8a11dc3077c412fd856d1bad8231bf027a25f"),
            "libbrotlidec.1.2.0.dylib": ("libbrotlidec.1.2.1.dylib", "351fa4a2f4faed4147dfead81a8b0f5500ada31db64f74c8368bc1ab894f0dd1"),
        },
    },
}


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def policy():
    key = (platform.system(), platform.machine())
    if key not in POLICIES:
        raise RuntimeError(f"Pillow native qualification unavailable for {key}; see docs/Security.md. No security acceptance claimed.")
    package = importlib.metadata.distribution("pillow")
    if package.version != "13.0.0":
        raise RuntimeError("Unreviewed Pillow version")
    selected = POLICIES[key]
    root = Path(package.locate_file(selected["root"]))
    if root.is_symlink() or root.resolve() != root or not root.is_dir():
        raise RuntimeError("Pillow library custody differs")
    if sys.prefix == sys.base_prefix or not root.is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError("Native qualification requires Pillow inside the target virtual environment")
    if set(p.name for p in root.glob("*brotli*")) != set(selected["files"]):
        raise RuntimeError("Unreviewed Pillow Brotli library set")
    if any((root / name).is_symlink() for name in selected["files"]):
        raise RuntimeError("Pillow Brotli libraries cannot be symlinks")
    return package, root, selected


def probe():
    package, root, selected = policy()
    receipt = json.loads((root / "raptor-native-security.json").read_text())
    if receipt.get("source_commit") != SOURCE_COMMIT or receipt.get("source_archive_sha256") != SOURCE_SHA256:
        raise RuntimeError("Native repair provenance differs")
    if set(receipt["libraries"]) != set(selected["files"]):
        raise RuntimeError("Native repair library inventory differs")
    records = {row[0]: row for row in csv.reader(package.read_text("RECORD").splitlines())}
    for name, expected in receipt["libraries"].items():
        path = root / name
        if digest(path) != expected:
            raise RuntimeError("Native repair bytes differ")
        record = records[selected["root"] + "/" + name]
        encoded = base64.urlsafe_b64encode(bytes.fromhex(expected)).rstrip(b"=").decode()
        if record[1:] != ["sha256=" + encoded, str(path.stat().st_size)]:
            raise RuntimeError("Installed RECORD does not describe the repaired library")
    decoder = next(root / name for name in selected["files"] if "brotlidec" in name)
    lib = ctypes.CDLL(str(decoder))
    lib.BrotliDecoderVersion.restype = ctypes.c_uint32
    if lib.BrotliDecoderVersion() != 0x1002001:
        raise RuntimeError("Pillow Brotli decoder is not 1.2.1")
    compressed = bytes.fromhex("0b0a80526170746f7220736563757269747920736d6f6b6503")
    encoded = ctypes.create_string_buffer(compressed)
    decoded = ctypes.create_string_buffer(64)
    length = ctypes.c_size_t(len(decoded))
    lib.BrotliDecoderDecompress.argtypes = [ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
    lib.BrotliDecoderDecompress.restype = ctypes.c_int
    if lib.BrotliDecoderDecompress(len(compressed), encoded, ctypes.byref(length), decoded) != 1 or decoded.raw[:length.value] != b"Raptor security smoke":
        raise RuntimeError("Brotli bounded round trip failed")
    from PIL import Image, ImageFont, features
    for feature in ("freetype2", "littlecms2", "webp", "avif", "jpg", "jpg_2000", "zlib", "libtiff"):
        if not features.check(feature):
            raise RuntimeError("Pillow feature unavailable: " + feature)
    for image_format in ("PNG", "JPEG", "TIFF", "WEBP", "AVIF", "JPEG2000"):
        stream = io.BytesIO()
        Image.new("RGB", (8, 8), (10, 20, 30)).save(stream, format=image_format)
        stream.seek(0)
        with Image.open(stream) as image:
            image.load()
            if image.size != (8, 8):
                raise RuntimeError("Pillow image round trip failed")
    if ImageFont.load_default().getbbox("Raptor")[2] <= 0:
        raise RuntimeError("Pillow FreeType smoke failed")
    print(json.dumps(receipt, sort_keys=True))


def run(*command):
    subprocess.run([str(arg) for arg in command], check=True)


def repair():
    package, root, selected = policy()
    receipt_path = root / "raptor-native-security.json"
    if receipt_path.exists():
        run(sys.executable, __file__, "--probe")
        return
    for name, (_, expected) in selected["files"].items():
        if digest(root / name) != expected:
            raise RuntimeError("Unreviewed Pillow Brotli preimage; refusing mutation")
    tool_root = Path(sys.executable).parent
    cmake = shutil.which("cmake", path=str(tool_root) + os.pathsep + os.environ.get("PATH", ""))
    ctest = shutil.which("ctest", path=str(tool_root) + os.pathsep + os.environ.get("PATH", ""))
    if not cmake or not ctest:
        raise RuntimeError("Install locks/bootstrap.lock for the reviewed CMake tools")
    record_path = Path(package.locate_file("pillow-13.0.0.dist-info/RECORD"))
    original_record = record_path.read_bytes()
    originals = {name: (root / name).read_bytes() for name in selected["files"]}
    with tempfile.TemporaryDirectory(prefix="sse-brotli-") as directory:
        work = Path(directory)
        archive = work / "brotli.tar.gz"
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response, archive.open("wb") as output:
            total = 0
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > 16 * 1024 * 1024:
                    raise RuntimeError("Brotli source archive exceeds its download budget")
                output.write(chunk)
        if digest(archive) != SOURCE_SHA256:
            raise RuntimeError("Brotli source checksum mismatch")
        with tarfile.open(archive) as source:
            source.extractall(work / "source", filter="data")
        source_root = work / "source" / ("brotli-" + SOURCE_COMMIT)
        build = work / "build"
        options = ["-DCMAKE_BUILD_TYPE=Release", "-DBUILD_SHARED_LIBS=ON", "-DBROTLI_DISABLE_TESTS=OFF"]
        if platform.system() == "Darwin":
            options.extend(["-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0", "-DCMAKE_OSX_ARCHITECTURES=arm64"])
        run(cmake, "-S", source_root, "-B", build, *options)
        run(cmake, "--build", build, "--parallel", "2")
        run(ctest, "--test-dir", build, "--output-on-failure", "--no-tests=error", "--parallel", "2")
        try:
            for name, (replacement, _) in selected["files"].items():
                target = root / name
                shutil.copyfile(build / replacement, target)
                if platform.system() == "Linux":
                    patchelf = shutil.which("patchelf", path=str(tool_root) + os.pathsep + os.environ.get("PATH", ""))
                    if not patchelf:
                        raise RuntimeError("Install the reviewed patchelf bootstrap tool")
                    run(patchelf, "--set-soname", name, target)
                    if "brotlidec" in name:
                        run(patchelf, "--set-rpath", "$ORIGIN", target)
                        run(patchelf, "--replace-needed", "libbrotlicommon.so.1", "libbrotlicommon-53534446.so.1.2.0", target)
                else:
                    run("install_name_tool", "-id", "@loader_path/" + name, target)
                    if "brotlidec" in name:
                        dependency = next(line.strip().split(" (")[0] for line in subprocess.check_output(["otool", "-L", str(target)], text=True).splitlines()[1:] if "libbrotlicommon" in line)
                        run("install_name_tool", "-change", dependency, "@loader_path/libbrotlicommon.1.2.0.dylib", target)
                    run("codesign", "--force", "--sign", "-", target)
            receipt = {"schema": "raptor.sse.native-security/v1", "component": "brotli", "version": "1.2.1", "source_commit": SOURCE_COMMIT, "source_archive_sha256": SOURCE_SHA256, "platform": list((platform.system(), platform.machine())), "libraries": {name: digest(root / name) for name in selected["files"]}}
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
            rows = list(csv.reader(io.StringIO(original_record.decode())))
            changed = 0
            for row in rows:
                if row[0] in {selected["root"] + "/" + name for name in selected["files"]}:
                    data = Path(package.locate_file(row[0])).read_bytes()
                    row[1:] = ["sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode(), str(len(data))]
                    changed += 1
            if changed != len(selected["files"]):
                raise RuntimeError("Unexpected installed RECORD")
            rows.append([selected["root"] + "/" + receipt_path.name, "", ""])
            with record_path.open("w", newline="") as output:
                csv.writer(output, lineterminator="\n").writerows(rows)
            run(sys.executable, __file__, "--probe")
        except BaseException:
            for name, data in originals.items():
                (root / name).write_bytes(data)
            record_path.write_bytes(original_record)
            receipt_path.unlink(missing_ok=True)
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--probe", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repair:
        repair()
    else:
        probe()
