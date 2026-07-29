#!/usr/bin/env bash
# install.sh — macOS LaunchAgent installer for Zero voice assistant.
# Run once from the repo root: bash install.sh
# Requires: macOS (uses launchctl). Does nothing useful on Linux/Windows.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.ahmad.zero.plist"
PYTHON="$DIR/.venv/bin/python"
OUT_LOG="$DIR/zero.run.out.log"
ERR_LOG="$DIR/zero.run.err.log"

if [[ "$(uname)" != "Darwin" ]]; then
    echo "[install.sh] This script is for macOS only. Exiting." >&2
    exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ahmad.zero</string>

    <!-- Foreground wrapper: execs `python -m zero` so launchd supervises the real
         process and restarts only on actual death (KeepAlive + ThrottleInterval).
         A fast-exit supervisor (run.sh) double-starts during the ~40s model load. -->
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${DIR}/run-fg.sh</string>
    </array>

    <!-- Reap the whole process tree on restart so whisper multiprocessing children
         don't orphan + hold the HUD port (root cause of Errno 48 on restart). -->
    <key>AbandonProcessGroup</key>
    <false/>

    <key>WorkingDirectory</key>
    <string>${DIR}</string>

    <key>KeepAlive</key>
    <true/>

    <key>RunAtLoad</key>
    <true/>

    <!-- Guard against a tight crash-loop (e.g. whisper exit 143): wait 30s between restarts. -->
    <key>ThrottleInterval</key>
    <integer>30</integer>

    <key>StandardOutPath</key>
    <string>${OUT_LOG}</string>

    <key>StandardErrorPath</key>
    <string>${ERR_LOG}</string>
</dict>
</plist>
PLIST_EOF

echo "[install.sh] Wrote $PLIST"

# Unload existing agent silently (ignore errors if not loaded)
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "[install.sh] LaunchAgent com.ahmad.zero loaded — Zero will start now and at every login."
echo "[install.sh] IMPORTANT: ensure ANTHROPIC_API_KEY is NOT set in your environment."
echo "             Zero uses the Claude Code subscription; a set API key causes startup failure."
