"""Install a frozen standalone bundle, then qualify its native dependencies."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install(bundle, native_bundle=None, native_bundle_sha256=None, native_approval=None, native_approval_sha256=None):
    if sys.version_info[:3] < (3, 13, 18) or sys.version_info[:2] != (3, 13):
        raise RuntimeError("Use maintained CPython 3.13.18 or later in the 3.13 series")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Provisioning requires a virtual environment")
    explicit = (native_bundle, native_bundle_sha256, native_approval, native_approval_sha256)
    if any(value is not None for value in explicit):
        if not all(value is not None for value in explicit):
            raise RuntimeError("Explicit native delivery requires bundle, approval and both independent digests")
        import pillow_bundle
        pillow_bundle.target_profile()
        pillow_bundle.approved_inputs(*explicit)
    else:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "pillow_native.py"), "--preflight"], check=True)
    for filename in ("bootstrap.lock", bundle + ".lock"):
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--require-hashes", "--only-binary=:all:",
            "--no-build-isolation", "-r", str(ROOT / "locks" / filename),
        ], check=True)
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    if any(value is not None for value in explicit):
        pillow_bundle.apply_bundle(*explicit)
    else:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "pillow_native.py"), "--repair"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", choices=["core", "cloud", "deep-learning", "dev", "notebooks", "visualization", "transformers"])
    parser.add_argument("--native-bundle")
    parser.add_argument("--native-bundle-sha256")
    parser.add_argument("--native-approval")
    parser.add_argument("--native-approval-sha256")
    args = parser.parse_args()
    install(args.bundle, args.native_bundle, args.native_bundle_sha256, args.native_approval, args.native_approval_sha256)
