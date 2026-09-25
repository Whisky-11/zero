from zero.config import load_config

def test_load_config_reads_voice_and_gate():
    cfg = load_config("config.toml")
    assert cfg.voice.voice == "bm_george"
    assert cfg.brain.user_name == "Ahmad"
    assert "rm " in cfg.gate.confirm_patterns
    assert cfg.hud.http_port == 9911  # >1024 so macOS allows a non-root bind
    # hallucination gate defaults survive config round-trip
    assert 0 < cfg.stt.no_speech_max <= 1
    assert cfg.stt.logprob_min < 0


def test_mac_and_app_sections():
    cfg = load_config("config.toml")
    assert cfg.mac.enabled is True
    assert "Terminal" in cfg.mac.sensitive_apps
    assert "osascript" in cfg.gate.confirm_patterns   # shell can't bypass the mac gate
    assert cfg.app.hotkey
    from zero.app import hotkey_matcher
    code, mods = hotkey_matcher(cfg.app.hotkey)
    assert isinstance(code, int) and mods


def test_load_config_defaults_to_repo_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)          # Zero.app may start anywhere
    assert load_config().voice.voice == "bm_george"
