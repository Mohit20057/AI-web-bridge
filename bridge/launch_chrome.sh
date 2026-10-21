#!/usr/bin/env bash
# ==============================================================
# launch_chrome.sh  —  Start Chrome with remote debugging
# ==============================================================
# Configure via environment variables or edit the defaults below.
#
#   CHROME_EXE          Path to the Chrome / Chromium binary
#   CHROME_PROFILE_DIR  Where Chrome stores this session's profile
#                       Default: ~/ArgonChromeProfile
#   CHROME_DEBUG_PORT   CDP port the bridge connects to
#                       Default: 9222
#
# Usage:
#   chmod +x launch_chrome.sh
#   ./launch_chrome.sh
#   # or with overrides:
#   CHROME_PROFILE_DIR=~/MyProfile CHROME_DEBUG_PORT=9223 ./launch_chrome.sh
# ==============================================================

set -euo pipefail

CHROME_DEBUG_PORT="${CHROME_DEBUG_PORT:-9222}"
CHROME_PROFILE_DIR="${CHROME_PROFILE_DIR:-$HOME/ArgonChromeProfile}"

# Auto-detect Chrome binary if not set
if [ -z "${CHROME_EXE:-}" ]; then
    if command -v google-chrome &>/dev/null; then
        CHROME_EXE="google-chrome"
    elif command -v google-chrome-stable &>/dev/null; then
        CHROME_EXE="google-chrome-stable"
    elif command -v chromium-browser &>/dev/null; then
        CHROME_EXE="chromium-browser"
    elif command -v chromium &>/dev/null; then
        CHROME_EXE="chromium"
    elif [ -d "/Applications/Google Chrome.app" ]; then
        CHROME_EXE="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else
        echo "ERROR: Chrome not found. Set CHROME_EXE to the full path of your Chrome binary."
        exit 1
    fi
fi

echo "Starting Chrome..."
echo "  Binary : $CHROME_EXE"
echo "  Profile: $CHROME_PROFILE_DIR"
echo "  Port   : $CHROME_DEBUG_PORT"
echo ""
echo "Log in to the web AI (e.g. gemini.google.com) in this browser window."
echo "Then switch back to your terminal and run argon_bridge.py."
echo ""

mkdir -p "$CHROME_PROFILE_DIR"

"$CHROME_EXE" \
    --remote-debugging-port="$CHROME_DEBUG_PORT" \
    --user-data-dir="$CHROME_PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    &

echo "Chrome launched in background (PID $!)."
