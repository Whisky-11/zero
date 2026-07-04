#!/usr/bin/env python3
"""serve-hud.py — run the Zero HUD standalone (no voice stack / no venv).

Serves ui/ + the read-only vault API on :911 using system python3, so the HUD
(CORE / CONNECTIONS / VAULT views) can be previewed without the full
wake-word→Whisper→Kokoro pipeline. In full voice mode zero/hud.py serves the
same handler. Usage:  python3 serve-hud.py [port]
"""
import socketserver
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zero.hud_api import HudApiHandler  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 911


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), HudApiHandler) as httpd:
        print(f"Zero HUD → http://127.0.0.1:{PORT}   (vault API live; voice stack not required)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
