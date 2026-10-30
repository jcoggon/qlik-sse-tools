#!/usr/bin/env python3
"""
Qlik Python Tools — Optional Packages Installer

Installs optional packages and models for advanced analytics capabilities.
Run this after Qlik-Py-Init to add extra features.

Usage:
    ./qlik-py-env/bin/python install_extras.py          # Interactive mode
    ./qlik-py-env/bin/python install_extras.py --all     # Install everything
    ./qlik-py-env/bin/python install_extras.py --list    # Show available packages
"""

import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Package definitions
# ---------------------------------------------------------------------------

EXTRAS = {
    "spacy_sm": {
        "name": "spaCy English Model (Small)",
        "description": "Basic NER & NLP — 15 MB, good for most use cases",
        "category": "NLP",
        "install": lambda: spacy_download("en_core_web_sm"),
        "check": lambda: spacy_check("en_core_web_sm"),
    },
    "spacy_md": {
        "name": "spaCy English Model (Medium)",
        "description": "Better accuracy + word vectors — 40 MB",
        "category": "NLP",
        "install": lambda: spacy_download("en_core_web_md"),
        "check": lambda: spacy_check("en_core_web_md"),
    },
    "spacy_lg": {
        "name": "spaCy English Model (Large)",
        "description": "Best accuracy + 685k word vectors — 560 MB",
        "category": "NLP",
        "install": lambda: spacy_download("en_core_web_lg"),
        "check": lambda: spacy_check("en_core_web_lg"),
    },
    "spacy_trf": {
        "name": "spaCy English Transformer Model",
        "description": "Transformer-based, highest accuracy — 400+ MB (requires GPU for speed)",
        "category": "NLP",
        "install": lambda: pip_install("spacy-curated-transformers") and spacy_download("en_core_web_trf"),
        "check": lambda: spacy_check("en_core_web_trf"),
    },
    "openpyxl": {
        "name": "Excel File Support (openpyxl)",
        "description": "Read/write Excel .xlsx files — required for sample data and Excel-based workflows",
        "category": "Data",
        "install": lambda: pip_install("openpyxl"),
        "check": lambda: module_check("openpyxl"),
    },
    "jupyter": {
        "name": "Jupyter Notebook",
        "description": "Run interactive notebooks from docs/ — includes JupyterLab",
        "category": "Development",
        "install": lambda: pip_install("jupyterlab", "notebook", "ipykernel"),
        "check": lambda: module_check("jupyterlab"),
    },
    "deep_learning": {
        "name": "Deep Learning (TensorFlow + Keras)",
        "description": "Neural network models via Keras/TensorFlow — 500+ MB",
        "category": "Machine Learning",
        "install": lambda: pip_install_requirements("requirements-deep-learning.txt"),
        "check": lambda: module_check("tensorflow"),
    },
    "plotly": {
        "name": "Interactive Visualizations (Plotly)",
        "description": "Interactive charts and dashboards",
        "category": "Visualization",
        "install": lambda: pip_install("plotly==6.9.0"),
        "check": lambda: module_check("plotly"),
    },
    "qlik_cloud": {
        "name": "Qlik Cloud REST Façade",
        "description": "Authenticated REST inference API for Qlik Cloud analytic connections",
        "category": "Deployment",
        "install": lambda: pip_install_requirements("requirements-cloud.txt"),
        "check": lambda: module_check("fastapi") and module_check("uvicorn"),
    },
}

# Recommended bundles
BUNDLES = {
    "essentials": {
        "name": "Essentials",
        "description": "Recommended minimum for most users",
        "packages": ["spacy_sm", "openpyxl"],
    },
    "analytics": {
        "name": "Full Analytics",
        "description": "All analytics capabilities (NLP + ML + Visualization)",
        "packages": ["spacy_md", "openpyxl", "deep_learning", "plotly"],
    },
    "nlp": {
        "name": "NLP Focus",
        "description": "All spaCy models for maximum NLP capability",
        "packages": ["spacy_sm", "spacy_md", "spacy_lg"],
    },
    "developer": {
        "name": "Developer",
        "description": "Everything including Jupyter for development",
        "packages": ["spacy_sm", "openpyxl", "jupyter", "plotly"],
    },
}

# ---------------------------------------------------------------------------
# Install helpers
# ---------------------------------------------------------------------------

def pip_install(*packages):
    """Install packages via pip."""
    cmd = [sys.executable, "-m", "pip", "install", "-c", os.path.join(SCRIPT_DIR, "locks", "constraints.txt")] + list(packages)
    return subprocess.run(cmd, capture_output=False).returncode == 0


def pip_install_requirements(filename):
    """Install a pinned optional dependency bundle from the repository."""
    path = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(path):
        print(f"  Missing requirements file: {path}")
        return False
    bundle = {"requirements-deep-learning.txt": "deep-learning", "requirements-cloud.txt": "cloud"}[filename]
    return subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "scripts", "provision.py"), bundle],
        capture_output=False,
    ).returncode == 0


def spacy_download(model):
    """Download a spaCy model."""
    cmd = [sys.executable, "-m", "spacy", "download", model, "-c", os.path.join(SCRIPT_DIR, "locks", "constraints.txt")]
    return subprocess.run(cmd, capture_output=False).returncode == 0


def module_check(module_name):
    """Check if a Python module is importable."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def spacy_check(model_name):
    """Check if a spaCy model is installed and loadable."""
    try:
        import spacy
        spacy.load(model_name)
        return True
    except Exception:
        return False


def check_all():
    """Return dict of package_key -> installed status."""
    status = {}
    for key, pkg in EXTRAS.items():
        status[key] = pkg["check"]()
    return status


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def print_header():
    print()
    print("=" * 64)
    print("  Qlik Python Tools — Optional Packages Installer")
    print("=" * 64)
    print(f"  Python:  {sys.version.split()[0]}")
    print(f"  Venv:    {sys.prefix}")
    print("=" * 64)
    print()


def print_status():
    """Show all packages and their install status."""
    status = check_all()
    categories = {}
    for key, pkg in EXTRAS.items():
        cat = pkg["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((key, pkg, status[key]))

    for cat, items in categories.items():
        print(f"  [{cat}]")
        for key, pkg, installed in items:
            icon = "✅" if installed else "  "
            print(f"    {icon}  {key:<16} {pkg['name']}")
            print(f"        {pkg['description']}")
        print()


def print_bundles():
    """Show available bundles."""
    print("  Quick-install bundles:")
    print()
    for bkey, bundle in BUNDLES.items():
        pkgs = ", ".join(bundle["packages"])
        print(f"    {bkey:<14} {bundle['name']}")
        print(f"                 {bundle['description']}")
        print(f"                 Includes: {pkgs}")
        print()


def install_packages(keys):
    """Install a list of packages by key."""
    for key in keys:
        if key not in EXTRAS:
            print(f"  ⚠️  Unknown package: {key}")
            continue
        pkg = EXTRAS[key]
        if key not in {"deep_learning", "qlik_cloud"} and pkg["check"]():
            print(f"  ✅  {pkg['name']} — already installed")
            continue
        print(f"\n  📦 Installing {pkg['name']}...")
        print(f"     {pkg['description']}")
        print()
        success = pkg["install"]()
        if success:
            print(f"  ✅  {pkg['name']} — installed successfully")
        else:
            raise SystemExit(f"  {pkg['name']} — installation failed; setup is incomplete")


def interactive_mode():
    """Run the interactive installer."""
    print_header()
    print_status()
    print_bundles()

    print("  Options:")
    print("    • Enter a bundle name (e.g., 'essentials', 'analytics')")
    print("    • Enter package names separated by spaces (e.g., 'spacy_sm openpyxl')")
    print("    • Enter 'all' to install everything")
    print("    • Enter 'q' to quit")
    print()

    while True:
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice in ('q', 'quit', 'exit', ''):
            break
        elif choice == 'all':
            install_packages(list(EXTRAS.keys()))
            break
        elif choice in BUNDLES:
            install_packages(BUNDLES[choice]["packages"])
            break
        else:
            keys = choice.split()
            valid = [k for k in keys if k in EXTRAS]
            invalid = [k for k in keys if k not in EXTRAS]
            if invalid:
                print(f"  ⚠️  Unknown: {', '.join(invalid)}")
                print(f"     Available: {', '.join(EXTRAS.keys())}")
            if valid:
                install_packages(valid)
                break

    print()
    print("  Current status:")
    print_status()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if "--list" in sys.argv:
        print_header()
        print_status()
        print_bundles()
    elif "--all" in sys.argv:
        print_header()
        install_packages(list(EXTRAS.keys()))
        print("\n  Final status:")
        print_status()
    elif "--bundle" in sys.argv:
        idx = sys.argv.index("--bundle")
        if idx + 1 < len(sys.argv):
            bundle_name = sys.argv[idx + 1]
            if bundle_name in BUNDLES:
                print_header()
                install_packages(BUNDLES[bundle_name]["packages"])
            else:
                print(f"Unknown bundle: {bundle_name}")
                print(f"Available: {', '.join(BUNDLES.keys())}")
        else:
            print("Usage: --bundle <name>")
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # Direct package names: install_extras.py spacy_sm openpyxl
        print_header()
        install_packages(sys.argv[1:])
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
