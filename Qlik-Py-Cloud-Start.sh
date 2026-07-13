#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/qlik-py-env/bin/activate"
export PYTHONPATH="$SCRIPT_DIR/core:$SCRIPT_DIR/generated${PYTHONPATH:+:$PYTHONPATH}"
HOST="${QLIK_CLOUD_HOST:-127.0.0.1}"
PORT="${QLIK_CLOUD_PORT:-8080}"
exec python -m uvicorn cloud_api:app --app-dir "$SCRIPT_DIR/core" --host "$HOST" --port "$PORT" --no-server-header
