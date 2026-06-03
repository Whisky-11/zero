from zero.config import load_config

def test_load_config_reads_voice_and_gate():
    cfg = load_config("config.toml")
    assert cfg.voice.voice == "bm_george"
    assert cfg.brain.user_name == "Ahmad"
    assert "rm " in cfg.gate.confirm_patterns
    assert cfg.hud.http_port == 911
