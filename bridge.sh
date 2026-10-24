#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/bridge/argon_bridge.py" "$@"
else
    exec python3 "$SCRIPT_DIR/bridge/argon_bridge.py" "$@"
fi
