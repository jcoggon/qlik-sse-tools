"""Rebuild only Pillow's Windows font extension with a fixed static decoder.

Use the checksum-pinned Pillow recipe and five native sources. Image codecs stay
in their reviewed wheel modules. No tools are installed by this module: MSVC C++
Build Tools must already be present, and frozen bootstrap supplies CMake.
"""

import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

INPUTS = Path(__file__).with_name("windows-native-inputs.json")


def sha256(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load_inputs():
    return json.loads(INPUTS.read_text(encoding="utf-8"))


def download(source, destination):
    with urllib.request.urlopen(source["url"], timeout=60) as response, destination.open("wb") as output:
        size = 0
        while chunk := response.read(65536):
            size += len(chunk)
            if size > 64 * 1024 * 1024:
                raise RuntimeError("Native source exceeds download budget")
            output.write(chunk)
    if sha256(destination) != source["sha256"]:
        raise RuntimeError("Native source checksum mismatch: " + source["filename"])


SHIM = r'''
#include <brotli/decode.h>
__declspec(dllexport) unsigned int QlikBrotliDecoderVersion(void) {
    return BrotliDecoderVersion();
}
__declspec(dllexport) int QlikBrotliDecoderDecompress(size_t encoded_size,
    const unsigned char *encoded, size_t *decoded_size, unsigned char *decoded) {
    return BrotliDecoderDecompress(encoded_size, encoded, decoded_size, decoded);
}
'''

SETUP = r'''
from setuptools import setup, Extension
from pathlib import Path
import os
prefix = Path(os.environ["QLIK_NATIVE_BUILD"])
setup(name="qlik-pillow-font-security", version="1.0.0", ext_modules=[Extension(
    "PIL._imagingft",
    sources=["src/_imagingft.c", "src/libImaging/Mode.c", "src/thirdparty/raqm/raqm.c",
             "src/thirdparty/fribidi-shim/fribidi.c", "qlik_brotli_probe.c"],
    include_dirs=[str(prefix / "inc"), "src"],
    library_dirs=[str(prefix / "lib")],
    libraries=["freetype", "harfbuzz", "libpng16", "zlib", "brotlidec", "brotlicommon"],
    define_macros=[("HAVE_RAQM", None)],
    extra_link_args=["/MAP:" + str(prefix / "extension.map")],
)])
'''


def preflight():
    root = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles", "")
    vswhere = Path(root) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    try:
        location = subprocess.check_output([
            str(vswhere), "-latest", "-prerelease", "-products", "*",
            "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property", "installationPath",
        ], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Windows native repair requires installed MSVC C++ Build Tools and Windows SDK") from error
    if not location or not (Path(location) / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat").is_file():
        raise RuntimeError("Windows native repair requires installed MSVC C++ Build Tools and Windows SDK")


def build(work, inputs):
    sources = inputs["sources"]
    archives = work / "archives"
    archives.mkdir()
    for source in sources.values():
        download(source, archives / source["filename"])
    with tarfile.open(archives / sources["pillow"]["filename"]) as archive:
        archive.extractall(work / "pillow", filter="data")
    pillow = work / "pillow" / "pillow-13.0.0"
    versions = pillow / ".github" / "dependencies.json"
    versions.parent.mkdir(exist_ok=True)
    versions.write_text(json.dumps(inputs["pillow_dependency_versions"]))
    recipe = pillow / "winbuild" / "build_prepare.py"
    spec = importlib.util.spec_from_file_location("pillow_build_recipe", recipe)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    selected = ["zlib", "libpng", "brotli", "freetype", "harfbuzz"]
    module.DEPS = {name: module.DEPS[name] for name in selected}
    module.DEPS["brotli"]["dir"] = "brotli-db24a98aed38a16de78cc05ca15cdd8dc2a0d92d"
    # zlib-ng enables tests that download GoogleTest by default. Build only the
    # required library and forbid CMake FetchContent for all selected sources.
    for name in selected:
        module.DEPS[name]["build"] = [
            line + " -DFETCHCONTENT_FULLY_DISCONNECTED=ON" + (" -DBUILD_TESTING=OFF" if name == "zlib" else "")
            if " -S ." in line else line for line in module.DEPS[name]["build"]
        ]
    # All downloads are already hash-verified. Forbid the recipe's live fallback.
    def no_download(*_):
        raise RuntimeError("Unexpected ungoverned native dependency download")
    module.download_dep = no_download
    original_write_script = module.write_script
    def checked_script(name, lines, prefs, verbose):
        # The upstream recipe copies libraries after its build commands. Preserve
        # every build/CTest failure instead of allowing a later copy to hide it.
        if name.startswith("build_dep_"):
            lines = [item for line in lines for item in (line, "if errorlevel 1 exit /b 1")]
        original_write_script(name, lines, prefs, verbose)
    module.write_script = checked_script
    module.cmd_cd = lambda path: f'cd /D "{path}"'
    module.cmd_set = lambda name, value: f'set "{name}={value}"'
    module.cmd_append = lambda name, value: f'set "{name}=%{name}%;{value}"'
    module.DEPS["brotli"]["build"] = [line.replace("-DBUILD_SHARED_LIBS:BOOL=OFF", "-DBUILD_SHARED_LIBS:BOOL=OFF -DBROTLI_DISABLE_TESTS=OFF") for line in module.DEPS["brotli"]["build"]]
    module.DEPS["brotli"]["build"].extend([
        '"{cmake}" --build . --parallel 2',
        'ctest.exe --output-on-failure --no-tests=error --parallel 2',
    ])
    prefix = work / "native"
    previous = sys.argv
    try:
        sys.argv = [str(recipe), "--architecture", "AMD64", "--nmake", "--build-dir", str(prefix), "--depends", str(archives)]
        module.main()
    finally:
        sys.argv = previous
    (pillow / "qlik_brotli_probe.c").write_text(SHIM)
    setup = pillow / "qlik_font_setup.py"
    setup.write_text(SETUP)
    output = work / "extension"
    script = work / "build-extension.cmd"
    script.write_text(
        '@echo off\ncall "' + str(prefix / "build_dep_all.cmd") + '"\nif errorlevel 1 exit /b 1\n'
        + 'call "' + str(prefix / "build_env.cmd") + '"\nif errorlevel 1 exit /b 1\n'
        + 'cd /D "' + str(pillow) + '"\n'
        + '"' + sys.executable + '" "' + str(setup) + '" build_ext --build-lib "' + str(output) + '"\n'
        + 'if errorlevel 1 exit /b 1\n', encoding="utf-8")
    environment = dict(os.environ, QLIK_NATIVE_BUILD=str(prefix))
    subprocess.run(["cmd.exe", "/d", "/c", str(script)], env=environment, check=True)
    extension = output / "PIL" / inputs["extension"]
    if not extension.is_file():
        raise RuntimeError("Windows font extension was not produced")
    return extension, prefix


def feature_snapshot():
    output = subprocess.check_output([
        sys.executable, "-c",
        "import json; from PIL import features; "
        "print(json.dumps({f: features.check(f) for f in ('raqm', 'harfbuzz', 'fribidi')}))",
    ], text=True)
    return json.loads(output)


def repair(package):
    inputs = load_inputs()
    root = Path(package.locate_file("PIL"))
    target = root / inputs["extension"]
    receipt_path = root / "raptor-native-security.json"
    verifier = Path(__file__).with_name("pillow_native.py")
    if receipt_path.is_symlink():
        raise RuntimeError("Windows native receipt cannot be a symlink")
    if receipt_path.exists():
        subprocess.run([sys.executable, str(verifier), "--probe"], check=True)
        return
    if sha256(target) != inputs["preimage_sha256"]:
        raise RuntimeError("Unreviewed Windows Pillow font-extension preimage")
    record_path = Path(package.locate_file("pillow-13.0.0.dist-info/RECORD"))
    original_record = record_path.read_bytes()
    original = target.read_bytes()
    original_features = feature_snapshot()
    licenses = root / "raptor-native-licenses"
    if (licenses.exists() or licenses.is_symlink()
            or (root / "raptor-native-smoke.woff2").exists()
            or (root / "raptor-native-smoke.woff2").is_symlink()):
        raise RuntimeError("Unreviewed Windows native license directory")
    with tempfile.TemporaryDirectory(prefix="sse-windows-native-") as directory:
        extension, prefix = build(Path(directory), inputs)
        try:
            shutil.copyfile(extension, target)
            shutil.copytree(prefix / "license", licenses)
            # Retain a controlled WOFF2 fixture from the same pinned Pillow
            # archive so readback exercises FreeType's actual Brotli path.
            fixture = root / "raptor-native-smoke.woff2"
            pillow_root = prefix.parent / "pillow" / "pillow-13.0.0"
            shutil.copyfile(pillow_root / "Tests" / "fonts" / "OpenSans.woff2", fixture)
            receipt = {
                "schema": "raptor.sse.native-security/v1", "component": "brotli", "version": "1.2.1",
                "source_commit": "db24a98aed38a16de78cc05ca15cdd8dc2a0d92d",
                "source_archive_sha256": sources_hash(inputs, "brotli"),
                "platform": ["Windows", "AMD64"], "libraries": {target.name: sha256(target)},
                "input_manifest_sha256": sha256(INPUTS),
                "build_recipe_sha256": sha256(__file__),
                "sources": {name: source["sha256"] for name, source in inputs["sources"].items()},
                "link_map_sha256": sha256(prefix / "extension.map"),
                "font_fixture_sha256": sha256(fixture),
                "original_text_features": original_features,
            }
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
            rows = list(csv.reader(io.StringIO(original_record.decode())))
            updated = 0
            for row in rows:
                if row[0] == "PIL/" + target.name:
                    row[1:] = record_hash(target)
                    updated += 1
            if updated != 1:
                raise RuntimeError("Windows Pillow installed RECORD differs")
            for file in sorted(licenses.iterdir()):
                rows.append(["PIL/raptor-native-licenses/" + file.name, *record_hash(file)])
            rows.append(["PIL/" + fixture.name, *record_hash(fixture)])
            rows.append(["PIL/" + receipt_path.name, "", ""])
            with record_path.open("w", newline="") as output:
                csv.writer(output, lineterminator="\n").writerows(rows)
            subprocess.run([sys.executable, str(verifier), "--probe"], check=True)
        except BaseException:
            target.write_bytes(original)
            record_path.write_bytes(original_record)
            receipt_path.unlink(missing_ok=True)
            (root / "raptor-native-smoke.woff2").unlink(missing_ok=True)
            if licenses.exists():
                shutil.rmtree(licenses)
            raise


def sources_hash(inputs, name):
    return inputs["sources"][name]["sha256"]


def record_hash(path):
    encoded = base64.urlsafe_b64encode(bytes.fromhex(sha256(path))).rstrip(b"=").decode()
    return ["sha256=" + encoded, str(Path(path).stat().st_size)]
