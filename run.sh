#!/usr/bin/env bash
# Start Zero (voice companion) if not already running. Idempotent.
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$DIR" || exit 1
PY="$DIR/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3)
# already up? (HUD http port 9911)
/usr/bin/curl -s -o /dev/null -m 2 http://localhost:9911/ 2>/dev/null && { echo "zero already running"; exit 0; }
# Zero refuses to start when ANTHROPIC_API_KEY is set (it uses the Claude Code
# subscription; a set key would bill per token — see zero/brain.py). Unset it
# for the child so a launchd/dashboard-inherited key can't block startup.
unset ANTHROPIC_API_KEY
# Entry point is the `zero` package (`python -m zero` → zero/__main__.py).
# There is no main.py — the old main.py lookup always failed with
# "zero entry not found", which is why Initialize silently never started Zero.
nohup "$PY" -m zero > "$DIR/zero.run.out.log" 2>"$DIR/zero.run.err.log" &
disown; echo "zero starting (pid $!)"
