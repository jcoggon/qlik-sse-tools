"""Install a frozen standalone bundle, then qualify its native dependencies."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install(bundle):
    if sys.version_info[:3] < (3, 13, 18) or sys.version_info[:2] != (3, 13):
        raise RuntimeError("Use maintained CPython 3.13.18 or later in the 3.13 series")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Provisioning requires a virtual environment")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "pillow_native.py"), "--preflight"], check=True)
    for filename in ("bootstrap.lock", bundle + ".lock"):
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--require-hashes", "--only-binary=:all:",
            "--no-build-isolation", "-r", str(ROOT / "locks" / filename),
        ], check=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "pillow_native.py"), "--repair"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", choices=["core", "cloud", "deep-learning", "dev", "notebooks", "visualization", "transformers"])
    install(parser.parse_args().bundle)
