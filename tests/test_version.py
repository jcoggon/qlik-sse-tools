import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_version_has_one_runtime_source_of_truth():
    namespace = {}
    exec((ROOT / "core" / "_version.py").read_text(encoding="utf-8"), namespace)
    version = namespace["__version__"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "version" in project["dynamic"]
