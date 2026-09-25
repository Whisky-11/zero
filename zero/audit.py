"""audit — an append-only record of every tool Zero tried to use.

Each PreToolUse decision (allowed / confirmed / declined / denied) is written
as one JSON line to data/audit.ndjson, so "what did Zero just do on my Mac?"
always has an answer. Long text is truncated; screenshots store nothing. The
file rotates to audit.ndjson.1 at ~5 MB.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from zero.paths import DATA_DIR

MAX_BYTES = 5 * 1024 * 1024
_FIELD_MAX = 300


def _clip(v):
    if isinstance(v, str) and len(v) > _FIELD_MAX:
        return v[:_FIELD_MAX] + f"… (+{len(v) - _FIELD_MAX} chars)"
    return v


class Audit:
    def __init__(self, path: str | Path = DATA_DIR / "audit.ndjson") -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def record(self, event: dict) -> None:
        row = {"ts": round(time.time(), 3), **event}
        if isinstance(row.get("input"), dict):
            row["input"] = {k: _clip(v) for k, v in row["input"].items()}
        line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size > MAX_BYTES:
                    self.path.replace(self.path.with_name(self.path.name + ".1"))
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line)
        except OSError:
            pass  # auditing must never break a turn

    def recent(self, n: int = 20) -> list[dict]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-n:]
        except OSError:
            return []
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except ValueError:
                continue
        return out
