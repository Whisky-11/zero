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
