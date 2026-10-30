"""Export hash-locked pip bundles from uv.lock; --check never rewrites files."""

import argparse
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = {"core": [], "cloud": ["cloud"], "deep-learning": ["deep-learning"], "dev": ["dev", "cloud"], "notebooks": ["notebooks"], "visualization": ["visualization"], "transformers": ["transformers"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    subprocess.run(["uv", "lock", "--check"], cwd=ROOT, check=True)
    (ROOT / "locks").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        for name, extras in BUNDLES.items():
            target = Path(directory) / (name + ".lock")
            command = ["uv", "export", "--locked", "--no-emit-project", "--no-header", "--no-annotate", "-o", str(target)]
            for extra in extras:
                command.extend(["--extra", extra])
            subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
            destination = ROOT / "locks" / target.name
            if args.check:
                if not destination.exists() or target.read_bytes() != destination.read_bytes():
                    raise SystemExit(f"Stale dependency export: {destination.name}")
            else:
                destination.write_bytes(target.read_bytes())
        lock = tomllib.loads((ROOT / "uv.lock").read_text())
        constraints = "".join(f"{p['name']}=={p['version']}\n" for p in lock["package"] if "registry" in p["source"])
        destination = ROOT / "locks" / "constraints.txt"
        if args.check:
            if destination.read_text() != constraints:
                raise SystemExit("Stale optional-extension constraints")
        else:
            destination.write_text(constraints)
        target = Path(directory) / "bootstrap.lock"
        subprocess.run([
            "uv", "pip", "compile", "--universal", "--python-version", "3.13", "--generate-hashes",
            "--no-header", "--no-annotate", "requirements-bootstrap.in", "-o", str(target),
        ], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        destination = ROOT / "locks" / target.name
        if args.check:
            if target.read_bytes() != destination.read_bytes():
                raise SystemExit("Stale bootstrap export")
        else:
            destination.write_bytes(target.read_bytes())


if __name__ == "__main__":
    main()
