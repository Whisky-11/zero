"""Tests for zero.profile.build_user_profile()."""
import pytest
from pathlib import Path

VAULT_DIR = Path(r"C:\Users\moze1\.claude\projects\C--Users-moze1\memory")

@pytest.mark.skipif(
    not VAULT_DIR.exists(),
    reason="Vault directory absent on this machine — skipping profile test"
)
def test_build_user_profile_contains_ahmad():
    from zero.profile import build_user_profile
    profile = build_user_profile()
    assert profile, "build_user_profile() returned empty string — check vault path"
    assert "Ahmad" in profile, f"Expected 'Ahmad' in profile. Got: {profile[:200]}"


@pytest.mark.skipif(
    not VAULT_DIR.exists(),
    reason="Vault directory absent on this machine — skipping profile test"
)
def test_build_user_profile_is_reasonably_sized():
    """Profile should be non-trivial but not bloated (≤ 400 words)."""
    from zero.profile import build_user_profile
    profile = build_user_profile()
    words = profile.split()
    assert len(words) >= 50, f"Profile suspiciously short: {len(words)} words"
    assert len(words) <= 400, f"Profile too long: {len(words)} words"


def test_build_user_profile_missing_vault(tmp_path, monkeypatch):
    """build_user_profile() must return '' rather than raising when vault absent."""
    import zero.profile as prof
    monkeypatch.setattr(prof, "_VAULT_DIR", tmp_path / "nonexistent")
    result = prof.build_user_profile()
    assert result == ""
