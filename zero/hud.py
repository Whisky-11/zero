from __future__ import annotations
import asyncio, json, threading
import socketserver
from websockets.asyncio.server import broadcast, serve
from .hud_api import HudApiHandler


class Hud:
    """State out to the HUD (broadcast) and commands in from it.

    Commands (JSON with a "type") are only accepted from the HUD's own origin.
    WebSockets are not covered by CORS, so without this any web page open in a
    browser could connect to ws://localhost and make Zero act on its behalf.
    """

    def __init__(self, ws_port: int = 8765, http_port: int = 911, on_command=None) -> None:
        self._ws_port = ws_port; self._http_port = http_port
        self._clients = set(); self._loop = None
        self.on_command = on_command      # callback(dict), run off the event loop
        self._last: dict = {}

    def origin_allowed(self, origin: str | None) -> bool:
        if not origin or not self._http_port:
            return False
        return origin in (f"http://127.0.0.1:{self._http_port}",
                          f"http://localhost:{self._http_port}")

    async def _handler(self, ws):
        self._clients.add(ws)
        origin = None
        try:
            origin = ws.request.headers.get("Origin")
        except Exception:
            pass
        trusted = self.origin_allowed(origin)
        try:
            await ws.send(json.dumps({"status": "connected"}))
            if self._last:
                await ws.send(json.dumps(self._last))
            async for raw in ws:
                if not trusted or self.on_command is None:
                    continue
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if isinstance(msg, dict) and isinstance(msg.get("type"), str):
                    await asyncio.get_running_loop().run_in_executor(None, self._dispatch, msg)
        finally:
            self._clients.discard(ws)

    def _dispatch(self, msg: dict) -> None:
        try:
            self.on_command(msg)
        except Exception as e:  # a bad command must never kill the HUD
            print(f"[hud] command {msg.get('type')!r} failed: {e}")

    async def _serve(self):
        async with serve(self._handler, "localhost", self._ws_port):
            await asyncio.Future()

    def _serve_http(self, port):
        # HudApiHandler serves ui/ statically AND the read-only vault/connections API.
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), HudApiHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def start(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=lambda: (asyncio.set_event_loop(self._loop),
                                         self._loop.run_until_complete(self._serve())),
                         daemon=True).start()
        if self._http_port:
            self._serve_http(self._http_port)

    @property
    def has_clients(self) -> bool:
        return bool(self._clients)

    def push_state(self, state: dict) -> None:
        if "status" in state:
            self._last = {**self._last, **state}   # replayed to late-joining HUDs
        if self._loop and self._clients:
            msg = json.dumps(state)
            self._loop.call_soon_threadsafe(lambda: broadcast(self._clients, msg))
