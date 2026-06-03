import asyncio, pytest
from zero.config import load_config
from zero.memory import Store
from zero.brain import Brain

@pytest.mark.manual
def test_brain_answers_on_subscription(tmp_path):
    cfg = load_config("config.toml")
    brain = Brain(cfg, Store(str(tmp_path / "z.db")), confirm_aloud=lambda q: True)
    reply = asyncio.run(brain.ask_text("Say exactly: systems online"))
    assert "systems online" in reply.lower()
