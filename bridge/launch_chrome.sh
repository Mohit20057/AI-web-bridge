#!/usr/bin/env bash
# ==============================================================
# launch_chrome.sh  —  Start Chrome or Edge with remote debugging
# ==============================================================
# Configure via environment variables or edit the defaults below.
#
#   BROWSER             chrome (default) or edge
#   BROWSER_EXE         Optional path to the browser binary
#   BROWSER_PROFILE_DIR Dedicated browser profile path
#   CDP_PORT            CDP port the bridge connects to
#   CHROME_DEBUG_PORT   Legacy CDP port setting
#                       Default: 9222
#
# Usage:
#   chmod +x launch_chrome.sh
#   ./launch_chrome.sh
#   # or with overrides:
#   BROWSER=edge BROWSER_PROFILE_DIR=~/MyEdgeProfile CDP_PORT=9223 ./launch_chrome.sh
# ==============================================================

set -euo pipefail

BROWSER="${BROWSER:-chrome}"
CDP_PORT="${CDP_PORT:-${CHROME_DEBUG_PORT:-9222}}"
if [ -n "${BROWSER_PROFILE_DIR:-}" ]; then
    :
elif [ -n "${CHROME_PROFILE_DIR:-}" ]; then
    BROWSER_PROFILE_DIR="$CHROME_PROFILE_DIR"
elif [[ "$BROWSER" == "edge" ]]; then
    BROWSER_PROFILE_DIR="$HOME/ArgonEdgeProfile"
else
    BROWSER_PROFILE_DIR="$HOME/ArgonChromeProfile"
fi

# Auto-detect Chrome binary if not set
if [ -z "${BROWSER_EXE:-}" ]; then
    if [[ "$BROWSER" == "edge" ]]; then
        if command -v microsoft-edge &>/dev/null; then
            BROWSER_EXE="microsoft-edge"
        elif command -v microsoft-edge-stable &>/dev/null; then
            BROWSER_EXE="microsoft-edge-stable"
        elif [ -d "/Applications/Microsoft Edge.app" ]; then
            BROWSER_EXE="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        else
            echo "ERROR: Edge not found. Set BROWSER_EXE to the full path of its binary."
            exit 1
        fi
    elif command -v google-chrome &>/dev/null; then
        BROWSER_EXE="google-chrome"
    elif command -v google-chrome-stable &>/dev/null; then
        BROWSER_EXE="google-chrome-stable"
    elif command -v chromium-browser &>/dev/null; then
        BROWSER_EXE="chromium-browser"
    elif command -v chromium &>/dev/null; then
        BROWSER_EXE="chromium"
    elif [ -d "/Applications/Google Chrome.app" ]; then
        BROWSER_EXE="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else
        echo "ERROR: Chrome not found. Set BROWSER_EXE to the full path of the browser binary."
        exit 1
    fi
fi

echo "Starting $BROWSER..."
echo "  Browser: $BROWSER"
echo "  Binary : $BROWSER_EXE"
echo "  Profile: $BROWSER_PROFILE_DIR"
echo "  Port   : $CDP_PORT"
echo ""
echo "Log in to Gemini in this browser window."
echo "Then switch back to your terminal and run argon_bridge.py."
echo ""

mkdir -p "$BROWSER_PROFILE_DIR"

"$BROWSER_EXE" \
    --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port="$CDP_PORT" \
    --remote-allow-origins="http://localhost:$CDP_PORT,http://127.0.0.1:$CDP_PORT" \
    --user-data-dir="$BROWSER_PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    &

echo "$BROWSER launched in background (PID $!)."
