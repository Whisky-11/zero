#!/usr/bin/env bash
# Foreground launcher for the KeepAlive launchd job (com.ahmad.zero).
# execs `python -m zero` in the FOREGROUND so launchd supervises the REAL process
# and restarts it only when it actually dies (no fast-exit re-run → no double-start
# race during Zero's ~40s model-load). Unsets ANTHROPIC_API_KEY (launchd inherits
# it globally; Zero refuses to start with it set). Runs in its own process group so
# a launchd restart can reap the whole tree (whisper multiprocessing children),
# preventing orphans from holding the HUD port.
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$DIR" || exit 1
unset ANTHROPIC_API_KEY
PY="$DIR/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
exec "$PY" -m zero
