#!/usr/bin/env bash
# install-app.sh — build Zero.app into ~/Applications, retire the old LaunchAgent,
# add it to Login Items and open it.
#
#   bash macos/install-app.sh            # install + open at login
#   bash macos/install-app.sh --no-login # install only
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HOME/Applications"
LOGIN=1; [[ "${1:-}" == "--no-login" ]] && LOGIN=0

[[ "$(uname)" == "Darwin" ]] || { echo "install-app.sh: macOS only" >&2; exit 1; }

# stop a running Zero (app launcher, then any python daemon) so mic + HUD ports are free
pkill -x Zero 2>/dev/null || true
pkill -f "python.* -m zero" 2>/dev/null || true
sleep 1

mkdir -p "$DEST"
bash "$DIR/macos/build-app.sh" "$DEST"

# the old LaunchAgent (install.sh) would start a second Zero fighting for the mic
PLIST="$HOME/Library/LaunchAgents/com.ahmad.zero.plist"
if [[ -f "$PLIST" ]]; then
    launchctl unload "$PLIST" 2>/dev/null || true
    mv "$PLIST" "$PLIST.disabled"
    echo "[install] retired LaunchAgent → $PLIST.disabled"
fi

if (( LOGIN )); then
    osascript -e 'tell application "System Events" to delete (every login item whose name is "Zero")' 2>/dev/null || true
    osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$DEST/Zero.app\", hidden:true, name:\"Zero\"}" >/dev/null
    echo "[install] Zero will open at login (toggle it from the menu bar)"
fi

open "$DEST/Zero.app"
cat <<MSG

Zero is starting — look for ◯ in the menu bar (… while models load, ~40s).
Grant these once, to "Zero", when asked (or in System Settings > Privacy & Security):
  • Microphone        — hearing you
  • Accessibility     — clicking, typing, the ⌥Space hotkey
  • Screen Recording  — screenshots (then quit + reopen Zero)
  • Automation        — asked per app the first time Zero scripts it
Logs: $DIR/zero.run.out.log / zero.run.err.log
MSG
