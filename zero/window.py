"""window — the HUD in a native macOS window (python -m zero --window).

Opened from the menu bar ("Open HUD"). A separate process because pywebview,
like the menu bar, needs its own main thread. Falls back to the browser when
pywebview isn't installed.
"""
from __future__ import annotations

import webbrowser

from zero.config import load_config


def main() -> None:
    cfg = load_config()
    url = f"http://127.0.0.1:{cfg.hud.http_port}"
    try:
        import webview
    except ImportError:
        webbrowser.open(url)
        return
    webview.create_window("Zero", url, width=1180, height=760, min_size=(820, 560),
                          background_color="#050505", on_top=cfg.app.window_on_top)
    webview.start()


if __name__ == "__main__":
    main()
