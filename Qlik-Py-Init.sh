#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Require Python 3.13. The current native analytics stack does not yet publish
# a complete set of Python 3.14 wheels (notably spaCy).
PYTHON_CMD=""
for cmd in python3.13 python3; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$($cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -eq 13 ]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python 3.13 is required but not found."
    echo "Please install Python 3.13 and try again."
    echo "  macOS:   brew install python@3.13"
    echo "  Linux:   See https://www.python.org/downloads/"
    exit 1
fi

echo "Using $($PYTHON_CMD --version) at $(which $PYTHON_CMD)"
echo ""
echo "Setting up the Python virtual environment..."
$PYTHON_CMD -m venv "$SCRIPT_DIR/qlik-py-env"

echo ""
echo "Copying project files to the new directory..."
cp -R "$SCRIPT_DIR/generated" "$SCRIPT_DIR/qlik-py-env/generated"
cp -R "$SCRIPT_DIR/core" "$SCRIPT_DIR/qlik-py-env/core"
cp "$SCRIPT_DIR/requirements.txt" "$SCRIPT_DIR/qlik-py-env/requirements.txt"
if [ -d "$SCRIPT_DIR/models" ]; then
    cp -R "$SCRIPT_DIR/models" "$SCRIPT_DIR/qlik-py-env/models"
fi
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$SCRIPT_DIR/qlik-py-env/.env"
fi
if [ -f "$SCRIPT_DIR/.env.example" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/qlik-py-env/.env.example"
fi

echo ""
echo "Activating the virtual environment..."
source "$SCRIPT_DIR/qlik-py-env/bin/activate"

# On macOS, XGBoost requires the OpenMP runtime (libomp)
if [[ "$(uname)" == "Darwin" ]]; then
    echo ""
    echo "Checking for OpenMP runtime (libomp) required by XGBoost on macOS..."
    if command -v brew &>/dev/null; then
        if ! brew list libomp &>/dev/null; then
            echo "Installing libomp via Homebrew..."
            brew install libomp
        else
            echo "libomp is already installed."
        fi
    else
        echo "WARNING: Homebrew not found. Please install libomp manually: brew install libomp"
    fi
fi

echo ""
echo "Installing required packages from requirements.txt..."
python "$SCRIPT_DIR/scripts/provision.py" core
python -m spacy download en_core_web_sm

echo ""
echo "Setup completed. Please check the log above for errors in red text."
echo "Run Qlik-Py-Start.sh to start this Server Side Extension."
