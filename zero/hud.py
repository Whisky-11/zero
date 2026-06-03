from __future__ import annotations
import asyncio, json, threading
from websockets.asyncio.server import broadcast, serve

class Hud:
    def __init__(self, ws_port: int = 8765, http_port: int = 911) -> None:
        self._ws_port = ws_port; self._clients = set(); self._loop = None

    async def _handler(self, ws):
        self._clients.add(ws)
        try:
            await ws.send(json.dumps({"status": "connected"}))
            async for _ in ws:
                pass
        finally:
            self._clients.discard(ws)

    async def _serve(self):
        async with serve(self._handler, "localhost", self._ws_port):
            await asyncio.Future()

    def start(self) -> None:
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=lambda: (asyncio.set_event_loop(self._loop),
                                         self._loop.run_until_complete(self._serve())),
                         daemon=True).start()

    def push_state(self, state: dict) -> None:
        if self._loop and self._clients:
            msg = json.dumps(state)
            self._loop.call_soon_threadsafe(lambda: broadcast(self._clients, msg))
