#!/bin/bash
# Qlik Python Tools — Optional Packages Installer
# Run after Qlik-Py-Init.sh to install extra capabilities

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/qlik-py-env/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Virtual environment not found at $SCRIPT_DIR/qlik-py-env/"
    echo "Please run Qlik-Py-Init.sh first."
    exit 1
fi

"$PYTHON" "$SCRIPT_DIR/install_extras.py" "$@"
