#!/usr/bin/env python3
"""
Build a clean Qlik SSE Tools download zip.

The package intentionally ships source, install scripts, generated protobuf
modules, docs, and tests. It does not include the local virtual environment,
local secrets, git metadata, runtime temp files, or generated caches.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_NAME = "raptor-qlik-sse-tools.zip"
PACKAGE_ROOT_NAME = "raptor-qlik-sse-tools"

INCLUDE_PATHS = [
    ".env.example",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "TESTING.md",
    "USAGE.md",
    "requirements.txt",
    "requirements-cloud.txt",
    "requirements-deep-learning.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "uv.lock",
    "install_extras.py",
    "Qlik-Py-Extras.bat",
    "Qlik-Py-Extras.sh",
    "Qlik-Py-Cloud-Start.bat",
    "Qlik-Py-Cloud-Start.ps1",
    "Qlik-Py-Cloud-Start.sh",
    "Qlik-Py-Init.bat",
    "Qlik-Py-Init.ps1",
    "Qlik-Py-Init.sh",
    "Qlik-Py-Service-Install.bat",
    "Qlik-Py-Service-Uninstall.bat",
    "Qlik-Py-Start.bat",
    "Qlik-Py-Start.ps1",
    "Qlik-Py-Start.sh",
    "core",
    "generated",
    "docs",
    "scripts",
    "tests",
]

EXCLUDED_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "downloads",
    "dist",
    "logs",
    "qlik-py-env",
    "tmp",
}

EXCLUDED_SUFFIXES = {
    ".log",
    ".pyc",
    ".pyo",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package Qlik SSE Tools for download.")
    parser.add_argument(
        "--artifact-name",
        default=DEFAULT_ARTIFACT_NAME,
        help=f"Zip file name to write. Defaults to {DEFAULT_ARTIFACT_NAME}.",
    )
    parser.add_argument(
        "--output-dir",
        action="append",
        default=[],
        help="Directory to receive the zip. Can be passed more than once.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Build the zip without running the standalone verification suite.",
    )
    return parser.parse_args()


def should_exclude(path: Path) -> bool:
    if path.name in EXCLUDED_NAMES:
        return True
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    return False


def copy_tree(source: Path, target: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            candidate = Path(directory) / name
            if should_exclude(candidate):
                ignored.add(name)
        return ignored

    shutil.copytree(source, target, ignore=ignore)


def copy_package_files(stage_root: Path) -> None:
    package_root = stage_root / PACKAGE_ROOT_NAME
    package_root.mkdir(parents=True, exist_ok=True)

    for relative_path in INCLUDE_PATHS:
        source = REPO_ROOT / relative_path
        if not source.exists():
            continue

        target = package_root / relative_path
        if source.is_dir():
            copy_tree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    write_package_metadata(package_root)


def run_tests() -> None:
    command = [sys.executable, str(REPO_ROOT / "tests" / "test_all_tools.py")]
    print("Running SSE verification suite...")
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def git_value(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return None

    value = result.stdout.strip()
    return value or None


def write_package_metadata(package_root: Path) -> None:
    metadata = {
        "name": PACKAGE_ROOT_NAME,
        "artifact": DEFAULT_ARTIFACT_NAME,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sourceCommit": git_value(["rev-parse", "HEAD"]),
        "sourceBranch": git_value(["branch", "--show-current"]),
    }
    lines = ["# Package Metadata", ""]
    for key, value in metadata.items():
        if value:
            lines.append(f"{key}: {value}")
    lines.append("")
    (package_root / "PACKAGE-METADATA.md").write_text("\n".join(lines), encoding="utf-8")


def create_zip(stage_root: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted((stage_root / PACKAGE_ROOT_NAME).rglob("*")):
            if file_path.is_dir() or should_exclude(file_path):
                continue
            archive.write(file_path, file_path.relative_to(stage_root))


def main() -> None:
    args = parse_args()
    output_dirs = args.output_dir or [str(REPO_ROOT / "dist")]

    if not args.skip_tests:
        run_tests()

    with tempfile.TemporaryDirectory(prefix="qlik-sse-package-") as temp_dir:
        stage_root = Path(temp_dir)
        copy_package_files(stage_root)

        for output_dir in output_dirs:
            zip_path = Path(os.path.expanduser(os.path.expandvars(output_dir))).resolve() / args.artifact_name
            create_zip(stage_root, zip_path)
            print(f"Created {zip_path}")


if __name__ == "__main__":
    main()
