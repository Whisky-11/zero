from zero.hud import Hud

def test_push_state_is_safe_with_no_clients():
    hud = Hud(ws_port=0, http_port=0)
    hud.push_state({"status": "idle"})   # must not raise when nobody connected
