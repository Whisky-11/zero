#!/usr/bin/env bash
# setup.sh — from a fresh clone to a running Zero.app, in one command.
#
#   bash macos/setup.sh              # everything: deps, venv, models, app, login item
#   bash macos/setup.sh --no-app     # stop after the venv + models (run with python -m zero)
#
# Safe to re-run: every step skips what's already done.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"
APP=1; [[ "${1:-}" == "--no-app" ]] && APP=0
say() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }

[[ "$(uname)" == "Darwin" ]] || { echo "setup.sh: macOS only (Windows: see README)" >&2; exit 1; }

say "Checking tools"
if ! command -v brew >/dev/null; then
    echo "Homebrew is required: https://brew.sh — install it, then re-run this script." >&2
    exit 1
fi
for pkg in python@3.10 espeak-ng portaudio; do
    brew list --versions "$pkg" >/dev/null 2>&1 || { echo "installing $pkg"; brew install "$pkg"; }
done
PY310="$(brew --prefix python@3.10)/bin/python3.10"
if (( APP )) && ! xcode-select -p >/dev/null 2>&1; then
    echo "Xcode command-line tools are needed to build Zero.app. Starting the installer —"
    echo "finish it, then re-run this script."
    xcode-select --install || true
    exit 1
fi
if ! command -v claude >/dev/null && [[ ! -x "$HOME/.claude/local/claude" ]] && [[ ! -x "$HOME/.local/bin/claude" ]]; then
    echo "note: the 'claude' CLI wasn't found. Zero thinks through your Claude Code"
    echo "      subscription — install Claude Code and run 'claude' once to sign in."
fi

say "Python environment (.venv)"
[[ -x .venv/bin/python ]] || "$PY310" -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -c "import torch" 2>/dev/null || .venv/bin/pip install -q torch torchaudio

say "Downloading models (first time: a few minutes)"
env -u ANTHROPIC_API_KEY .venv/bin/python -m zero.prefetch || echo "some models failed — Zero will retry on first launch"

say "Running tests"
.venv/bin/python -m pytest -q -m "not manual" tests/ || echo "(test failures above — Zero may still run)"

if (( APP )); then
    say "Building and installing Zero.app"
    bash macos/install-app.sh
else
    say "Done. Start Zero with:  .venv/bin/python -m zero   (or --text, or --app)"
fi
