"""profile.py — build a compact "who Ahmad is" text from his memory vault."""
from __future__ import annotations
import re
from pathlib import Path

_VAULT_DIR = Path(r"C:\Users\moze1\.claude\projects\C--Users-moze1\memory")


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
    if not _VAULT_DIR.exists():
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
