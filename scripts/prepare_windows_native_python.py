"""CI-only, one-download staging of the approved full private Windows runtime.

Never installs a launcher, changes registry/system PATH, or retries suppliers.
The complete archive digest is checked before opening the archive or execution.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

POLICY = Path(__file__).with_name("windows-native-python.json")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def extract(archive, output, policy):
    with tarfile.open(archive) as source:
        members = source.getmembers()
        require(len(members) == policy["member_count"] and sum(m.size for m in members) == policy["expanded_bytes"],
                "Approved runtime archive layout/size differs")
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            require(path.parts and path.parts[0] == "python" and not path.is_absolute()
                    and "\\" not in member.name and ":" not in member.name
                    and all(p not in ("", ".", "..") and p == p.rstrip(" .")
                            and not re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", p) for p in path.parts)
                    and (member.isfile() or member.isdir()) and not member.issparse(), "Unsafe runtime archive member")
            name = str(path).casefold()
            require(name not in names, "Aliased runtime archive member")
            names.add(name)
        source.extractall(output, members=members, filter="data")


def stage(output):
    require(platform.system() == "Windows" and platform.machine() == "AMD64", "Windows AMD64 CI staging only")
    policy = json.loads(POLICY.read_text())
    output = Path(output).absolute()
    require(not output.exists() and not output.is_symlink() and output.parent.resolve() == output.parent,
            "Runtime staging path already exists or aliases another location")
    with tempfile.TemporaryDirectory(prefix="sse-python-download-", dir=output.parent) as temp:
        archive = Path(temp) / "runtime.tar.gz"
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(policy["url"], timeout=60) as response, archive.open("xb") as target:
            while chunk := response.read(65536):
                size += len(chunk)
                require(size <= policy["bytes"], "Approved runtime download exceeds fixed size")
                digest.update(chunk)
                target.write(chunk)
        require(size == policy["bytes"] and digest.hexdigest() == policy["sha256"], "Approved runtime archive size/SHA differs")
        try:
            output.mkdir()
            extract(archive, output, policy)
            base = output / "python"
            for name, key in (("python.exe", "base_python_sha256"), ("python313.dll", "python_dll_sha256")):
                require(hashlib.sha256((base / name).read_bytes()).hexdigest() == policy[key], "Private runtime binary identity differs")
            # Execute only after entire archive and binary admission above.
            code = "import json,platform,struct; print(json.dumps([platform.python_version(),platform.machine(),struct.calcsize('P')*8]))"
            result = json.loads(subprocess.check_output([str(base / "python.exe"), "-I", "-c", code], text=True, timeout=30))
            require(result == [policy["version"], "AMD64", 64], "Private runtime execution profile differs")
            if "GITHUB_PATH" in os.environ:
                with open(os.environ["GITHUB_PATH"], "a", encoding="utf-8") as path_file:
                    path_file.write(str(base) + "\n" + str(base / "Scripts") + "\n")
            print(json.dumps({"runtime": result, "supplier_archive_sha256": policy["sha256"],
                              "python_sha256": policy["base_python_sha256"], "python_dll_sha256": policy["python_dll_sha256"]}))
        except BaseException:
            shutil.rmtree(output)
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    stage(parser.parse_args().output)
