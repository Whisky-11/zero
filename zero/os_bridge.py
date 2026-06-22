"""os_bridge — Zero's window into the Force AI OS.

The OS (force-ai-foundation) writes its live state to ``~/.whisky-os-state/``.
This module gives Zero clean, spoken-friendly readers over that state so the
voice loop never has to parse NDJSON by hand:

    python3 -m zero.os_bridge status            # one-sentence health summary
    python3 -m zero.os_bridge inbox             # unspoken "tell Ahmad now" items
    python3 -m zero.os_bridge inbox --drain     # ...and mark them spoken

Read-only except ``inbox --drain`` (which rewrites zero-inbox.ndjson to mark
items spoken). Everything degrades gracefully when the OS hasn't written yet —
Zero may well start before the OS has produced any state.

Pure stdlib. Spoken output: plain sentences, no markdown/emoji (a voice reads it).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

STATE_DIR = Path(os.environ.get("WHISKY_STATE_DIR", Path.home() / ".whisky-os-state"))

_NUM = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
        7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def _say_count(n: int) -> str:
    return _NUM.get(n, str(n))


def _read_ndjson(name: str) -> list[dict]:
    p = STATE_DIR / name
    if not p.exists():
        return []
    out = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue  # skip malformed, never fatal
    except Exception:
        return []
    return out


def status_summary() -> str:
    """A one/two-sentence spoken summary of subsystem health."""
    if not STATE_DIR.exists():
        return "The OS has not reported any state yet."
    statuses = []
    for p in sorted(STATE_DIR.glob("*-status.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = p.name.replace("-status.json", "")
        ok = str(d.get("ok", "unknown")).lower()
        statuses.append((name, ok, d.get("summary", "")))
    if not statuses:
        return "The OS has not reported any subsystem health yet."
    green = [s for s in statuses if s[1] == "true"]
    warn = [s for s in statuses if s[1] == "warn"]
    bad = [s for s in statuses if s[1] == "false"]
    total = len(statuses)
    if not warn and not bad:
        return f"All {_say_count(total)} subsystems are green."
    parts = [f"{_say_count(len(green))} of {_say_count(total)} subsystems are green"]
    for label, items in (("failing", bad), ("warning", warn)):
        for name, _ok, summary in items[:2]:
            nice = name.replace("-", " ")
            tail = f": {summary}" if summary else ""
            parts.append(f"the {nice} is {label}{tail}")
    return ". ".join(parts).rstrip(".") + "."


def read_inbox(drain: bool = False) -> list[str]:
    """Return the summaries of unspoken inbox items. If drain, mark them spoken."""
    items = _read_ndjson("zero-inbox.ndjson")
    unspoken = [it for it in items if it.get("spoken") is False]
    summaries = [str(it.get("summary", "")).strip() for it in unspoken if it.get("summary")]
    if drain and unspoken:
        _mark_spoken()
    return summaries


def _mark_spoken() -> None:
    """Rewrite zero-inbox.ndjson with every item marked spoken (atomic-ish)."""
    p = STATE_DIR / "zero-inbox.ndjson"
    items = _read_ndjson("zero-inbox.ndjson")
    if not items:
        return
    for it in items:
        it["spoken"] = True
    try:
        tmp = p.with_suffix(".ndjson.tmp")
        tmp.write_text(
            "".join(json.dumps(it, separators=(",", ":"), ensure_ascii=False) + "\n" for it in items),
            encoding="utf-8",
        )
        os.replace(tmp, p)
    except Exception:
        pass  # never fatal — worst case an item is read aloud twice


def inbox_spoken_text(drain: bool = False) -> str:
    """A spoken-ready string for the inbox (or a calm all-clear)."""
    summaries = read_inbox(drain=drain)
    if not summaries:
        return "Nothing needs your attention right now."
    if len(summaries) == 1:
        return summaries[0]
    head = f"{_say_count(len(summaries))} things need you. "
    return head + " ".join(s.rstrip(".") + "." for s in summaries)


def _main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    drain = "--drain" in argv
    if cmd == "status":
        print(status_summary())
    elif cmd == "inbox":
        print(inbox_spoken_text(drain=drain))
    else:
        print("usage: python3 -m zero.os_bridge [status | inbox [--drain]]")
        return 2
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
