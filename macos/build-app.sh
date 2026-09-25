#!/usr/bin/env bash
# build-app.sh — build Zero.app (menu-bar app) from this checkout.
#
#   bash macos/build-app.sh [output-dir]      # default: ./dist
#
# The bundle holds only a tiny native launcher (macos/launcher.c) + Info.plist;
# it runs this repo's .venv Python, so code changes need NO rebuild — just quit
# and reopen Zero. Rebuild only when the launcher/plist change or the repo moves.
#
# Signing: ad-hoc by default. macOS ties privacy grants to the signature, so a
# rebuild may make it ask for Microphone/Accessibility/Screen Recording again.
# Set ZERO_SIGN_ID="Apple Development: …" (a real certificate) to keep grants
# across rebuilds.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$DIR/dist}"
APP="$OUT/Zero.app"
SIGN_ID="${ZERO_SIGN_ID:--}"

[[ "$(uname)" == "Darwin" ]] || { echo "build-app.sh: macOS only" >&2; exit 1; }
command -v clang >/dev/null || { echo "clang missing — run: xcode-select --install" >&2; exit 1; }
[[ -x "$DIR/.venv/bin/python" ]] || echo "warning: $DIR/.venv not found yet — create it before opening Zero (README, macOS setup)" >&2

echo "[build] $APP  (runs $DIR)"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# escape the repo path for a C string literal
CDIR=$(printf '%s' "$DIR" | sed 's/\\/\\\\/g; s/"/\\"/g')
clang -O2 -Wall -mmacosx-version-min=12.0 -arch arm64 -arch x86_64 \
    -DZERO_DIR="\"$CDIR\"" -o "$APP/Contents/MacOS/Zero" "$DIR/macos/launcher.c" 2>/dev/null \
  || clang -O2 -Wall -mmacosx-version-min=12.0 \
    -DZERO_DIR="\"$CDIR\"" -o "$APP/Contents/MacOS/Zero" "$DIR/macos/launcher.c"
cp "$DIR/macos/Info.plist" "$APP/Contents/Info.plist"
plutil -lint "$APP/Contents/Info.plist" >/dev/null

# icon: macos/Zero.icns if you have one, else render a simple ring from the HUD look
if [[ -f "$DIR/macos/Zero.icns" ]]; then
    cp "$DIR/macos/Zero.icns" "$APP/Contents/Resources/Zero.icns"
elif [[ -x "$DIR/.venv/bin/python" ]] && "$DIR/.venv/bin/python" -c "import AppKit" 2>/dev/null; then
    "$DIR/.venv/bin/python" "$DIR/macos/make_icon.py" "$APP/Contents/Resources/Zero.icns" || true
fi

# vendor three.js so the HUD works offline (hud_api falls back to the CDN if absent)
if [[ ! -f "$DIR/ui/vendor/three.module.js" ]]; then
    mkdir -p "$DIR/ui/vendor"
    curl -fsSL -o "$DIR/ui/vendor/three.module.js" \
        https://unpkg.com/three@0.160.0/build/three.module.js \
      && echo "[build] vendored three.js" || echo "[build] could not fetch three.js (HUD will use the CDN)"
fi

codesign --force --sign "$SIGN_ID" --identifier com.ahmad.zero "$APP"
codesign --verify "$APP"
echo "[build] done → $APP"
