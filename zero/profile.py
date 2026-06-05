"""profile.py — build a compact "who Ahmad is" text from his memory vault."""
from __future__ import annotations
import re
from pathlib import Path


def _find_memory_dir() -> Path | None:
    """Locate the memory/ directory inside ~/.claude/projects/ that contains MEMORY.md.

    Works on Windows (C:\\Users\\<name>\\.claude\\...) and macOS (~/.claude/...).
    Prefers the candidate with MEMORY.md; if multiple exist, picks the largest by
    file-count so we always get the main vault, not a stale shard.
    """
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return None
    # sort: has MEMORY.md first, then by descending child-file count (larger = richer vault)
    cands = sorted(
        base.glob("*/memory"),
        key=lambda p: ((p / "MEMORY.md").exists(), sum(1 for _ in p.iterdir()) if p.is_dir() else 0),
        reverse=True,
    )
    for d in cands:
        if (d / "MEMORY.md").exists():
            return d
    return None


_VAULT_DIR: Path | None = _find_memory_dir()


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) and strip leading blank lines."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]
    return text.lstrip()


def _md_to_prose(text: str) -> str:
    """Very light markdown → plain prose conversion suitable for a system prompt."""
    # Remove ATX headings markers but keep the heading text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove markdown links but keep label
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Collapse multiple blank lines to one
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate(text: str, max_words: int = 350) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


def build_user_profile() -> str:
    """Read Ahmad's scoped memory and return a compact plain-text profile.

    Reads MEMORY.md (the index) and any user-*.md files. Returns "" if the
    vault directory is absent so callers never crash.
    """
    if _VAULT_DIR is None or not _VAULT_DIR.exists():
        return ""

    sections: list[str] = []

    # 1. user-*.md files first — most direct "who Ahmad is" content
    for path in sorted(_VAULT_DIR.glob("user-*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
            prose = _md_to_prose(_strip_frontmatter(raw))
            if prose:
                sections.append(prose)
        except OSError:
            pass

    # 2. Append the MEMORY.md index (bullet list of lessons) as a single block
    memory_md = _VAULT_DIR / "MEMORY.md"
    if memory_md.exists():
        try:
            raw = memory_md.read_text(encoding="utf-8")
            prose = _md_to_prose(_strip_frontmatter(raw))
            if prose:
                sections.append("Memory index (recent lessons):\n" + prose)
        except OSError:
            pass

    if not sections:
        return ""

    combined = "\n\n".join(sections)
    return _truncate(combined)
