"""paths — resolve Zero's files from the repo root, not the current directory.

Zero.app (and launchd) may start Python from anywhere, so every bundled file
(config.toml, prompts/, ui/, data/) is located relative to this package.
ZERO_HOME overrides the root (e.g. to point the app at another checkout).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("ZERO_HOME") or Path(__file__).resolve().parent.parent)
CONFIG = ROOT / "config.toml"
PROMPT = ROOT / "prompts" / "zero.md"
UI_DIR = ROOT / "ui"
DATA_DIR = ROOT / "data"
DB = DATA_DIR / "zero.db"
