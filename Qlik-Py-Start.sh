#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/qlik-py-env/bin/activate"

# Sync source files to the virtual environment before starting
echo "Syncing source files..."
cp -R "$SCRIPT_DIR/core/"* "$SCRIPT_DIR/qlik-py-env/core/"
cp -R "$SCRIPT_DIR/generated/"* "$SCRIPT_DIR/qlik-py-env/generated/"
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$SCRIPT_DIR/qlik-py-env/.env"
fi

cd "$SCRIPT_DIR/qlik-py-env/core"
python -u __main__.py
