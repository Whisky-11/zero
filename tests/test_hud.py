from zero.hud import Hud

def test_push_state_is_safe_with_no_clients():
    hud = Hud(ws_port=0, http_port=0)
    hud.push_state({"status": "idle"})   # must not raise when nobody connected


def test_commands_only_from_hud_origin():
    hud = Hud(ws_port=0, http_port=9911)
    assert hud.origin_allowed("http://127.0.0.1:9911")
    assert hud.origin_allowed("http://localhost:9911")
    assert not hud.origin_allowed("https://evil.example")
    assert not hud.origin_allowed("http://127.0.0.1:7717")
    assert not hud.origin_allowed(None)          # non-browser / no Origin header


def _free_port():
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def test_ws_commands_dispatch_only_for_trusted_origin():
    import asyncio, json, threading, time
    from websockets.asyncio.client import connect
    got = []
    ev = threading.Event()
    ws_port, http_port = _free_port(), _free_port()
    hud = Hud(ws_port=ws_port, http_port=0, on_command=lambda m: (got.append(m), ev.set()))
    hud._http_port = http_port           # origin check uses it; no HTTP server needed
    hud.start()

    async def send(origin, msg):
        for _ in range(50):
            try:
                async with connect(f"ws://localhost:{ws_port}", origin=origin) as ws:
                    await ws.recv()                     # {"status": "connected"}
                    await ws.send(json.dumps(msg))
                    await asyncio.sleep(0.2)
                    return
            except OSError:
                await asyncio.sleep(0.05)

    asyncio.run(send("https://evil.example", {"type": "say", "text": "rm -rf ~"}))
    assert got == []
    asyncio.run(send(f"http://127.0.0.1:{http_port}", {"type": "say", "text": "hello"}))
    assert ev.wait(2) and got == [{"type": "say", "text": "hello"}]
