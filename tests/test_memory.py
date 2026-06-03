from zero.memory import Store

def test_remember_then_recall(tmp_path):
    s = Store(str(tmp_path / "z.db"))
    s.remember("Ahmad's flight is Tuesday 9am", source="explicit")
    hits = s.recall("when is my flight")
    assert any("Tuesday" in h for h in hits)

def test_log_and_recent(tmp_path):
    s = Store(str(tmp_path / "z.db"))
    s.log_turn("user", "hello"); s.log_turn("assistant", "Good evening, Ahmad.")
    recent = s.recent_turns(limit=2)
    assert recent[-1] == ("assistant", "Good evening, Ahmad.")

def test_semantic_recall_no_word_overlap(tmp_path):
    """Prove recall works by meaning, not keywords.

    Stores two facts with zero word overlap to the query, then verifies that
    the semantically-relevant one ranks first.
    """
    s = Store(str(tmp_path / "z.db"))
    s.remember("Ahmad drives a Porsche 911 Carrera", source="explicit")
    s.remember("The CI runners live in WSL2", source="explicit")

    # Query shares NO content words with either fact; only meaning connects them.
    hits = s.recall("what car does he own", limit=5)

    # The Porsche fact must come back and must be ranked first.
    assert hits, "recall returned nothing — similarity floor may be too high"
    assert "Porsche" in hits[0], (
        f"Expected Porsche fact first, got: {hits}"
    )
