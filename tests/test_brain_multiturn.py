import pytest
from zero.config import load_config
from zero.memory import Store
from zero.brain import Brain

@pytest.mark.manual
def test_two_turns_same_session(tmp_path):
    cfg = load_config("config.toml")
    b = Brain(cfg, Store(str(tmp_path / "z.db")), confirm_aloud=lambda q: True)
    r1 = b.ask("Remember the number 7. Reply 'ok'.")
    r2 = b.ask("What number did I just say? Reply with only the digit.")
    assert "7" in r2
