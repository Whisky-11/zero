"""app — Zero as a macOS menu-bar app (python -m zero --app).

Zero.app's launcher starts this. It owns the main thread (AppKit), shows a
status item in the menu bar, and runs the voice loop in a background thread:

    ◯ idle   ◉ listening   ◌ thinking   ◍ speaking   ⊘ muted   … starting

Menu: Talk (push-to-talk), Type to Zero…, Mute microphone, Stop speaking,
Open HUD, Open at login, Quit. A global hotkey (config [app] hotkey, default
⌥Space) also triggers push-to-talk from any app — it needs Accessibility.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import traceback
import webbrowser

from zero import mac, permissions
from zero.config import load_config

ICONS = {"starting": "…", "idle": "◯", "listening": "◉", "thinking": "◌",
         "speaking": "◍", "connected": "◯", "error": "⚠"}


def hotkey_matcher(combo: str):
    """Return (keycode, required_modifier_names) for a combo like 'alt+space'."""
    key, mods = mac.parse_combo(combo)
    code = mac.KEY_CODES.get(key.lower(), mac.CHAR_CODES.get(key.lower()))
    if code is None:
        raise ValueError(f"unsupported hotkey key: {key}")
    return code, set(mods)


def _install_hotkey(combo: str, on_press) -> bool:
    try:
        from AppKit import (NSEvent, NSEventMaskKeyDown, NSEventModifierFlagCommand,
                            NSEventModifierFlagControl, NSEventModifierFlagOption,
                            NSEventModifierFlagShift)
    except Exception:
        return False
    code, want = hotkey_matcher(combo)
    flags = {"command": NSEventModifierFlagCommand, "control": NSEventModifierFlagControl,
             "option": NSEventModifierFlagOption, "shift": NSEventModifierFlagShift}

    def matches(ev) -> bool:
        if ev.keyCode() != code or ev.isARepeat():
            return False
        have = {n for n, f in flags.items() if ev.modifierFlags() & f}
        return have == want

    def on_global(ev):
        if matches(ev):
            on_press()

    def on_local(ev):
        if matches(ev):
            on_press()
            return None
        return ev

    # the monitors must stay referenced or PyObjC lets them go
    _install_hotkey._monitors = (
        NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, on_global),
        NSEvent.addLocalMonitorForEventsMatchingMask_handler_(NSEventMaskKeyDown, on_local),
    )
    return True


def _app_bundle() -> str:
    """Path of Zero.app (set by the launcher), or '' when run from a terminal."""
    return os.environ.get("ZERO_APP_PATH", "")


def _login_item(enable: bool | None = None) -> bool:
    """Query (enable=None) or set the 'open at login' item for Zero.app."""
    app = _app_bundle()
    if not app:
        return False
    if enable is None:
        ok, out = mac.osascript('tell application "System Events" to get the name of every login item')
        return ok and "Zero" in [s.strip() for s in out.split(",")]
    if enable:
        mac.osascript('tell application "System Events" to make login item at end with properties '
                      f'{{path:{mac.as_quote(app)}, hidden:true, name:"Zero"}}')
    else:
        mac.osascript('tell application "System Events" to delete (every login item whose name is "Zero")')
    return _login_item(None)


class ZeroApp:
    def __init__(self) -> None:
        import rumps
        self.rumps = rumps
        self.cfg = load_config()
        self.orch = None
        self.error = ""
        self.window_proc = None
        self.hud_url = f"http://127.0.0.1:{self.cfg.hud.http_port}"

        hk = self.cfg.app.hotkey
        self.item_status = rumps.MenuItem("Starting — loading models…")
        self.item_talk = rumps.MenuItem(f"Talk  ({hk})", callback=self.talk)
        self.item_type = rumps.MenuItem("Type to Zero…", callback=self.type_prompt)
        self.item_mute = rumps.MenuItem("Mute microphone", callback=self.toggle_mute)
        self.item_stop = rumps.MenuItem("Stop speaking", callback=self.stop)
        self.item_hud = rumps.MenuItem("Open HUD", callback=self.open_hud)
        self.item_login = rumps.MenuItem("Open at login", callback=self.toggle_login)
        # Permissions submenu: ✓/✗ per privacy permission; click to request + open Settings
        self.item_perms = rumps.MenuItem("Permissions")
        self.perm_items = {}
        for name, (why, _) in permissions.PERMISSIONS.items():
            it = rumps.MenuItem(name, callback=self.fix_permission)
            self.perm_items[name] = it
            self.item_perms.add(it)
        self.item_perms.add(None)
        self.item_perms.add(rumps.MenuItem("Open Privacy & Security…",
                                           callback=lambda _: permissions.request("Automation")))
        self._perm_tick = 0
        self.app = rumps.App("Zero", title=ICONS["starting"], quit_button=None)
        self.app.menu = [self.item_status, None, self.item_talk, self.item_type,
                         self.item_mute, self.item_stop, None, self.item_hud,
                         self.item_perms, self.item_login, None,
                         rumps.MenuItem("Quit Zero", callback=self.quit)]
        self.item_login.state = _login_item(None)
        if not _app_bundle():
            self.item_login.set_callback(None)   # only meaningful for Zero.app
        self.timer = rumps.Timer(self.refresh, 0.3)

    # ── lifecycle ──
    def start_voice(self) -> None:
        try:
            from zero.orchestrator import Orchestrator
            self.orch = Orchestrator()
            self.orch.run()
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"
            traceback.print_exc()

    def run(self) -> None:
        try:  # menu-bar only: no Dock icon for the Python process
            from AppKit import NSApplication
            NSApplication.sharedApplication().setActivationPolicy_(1)  # Accessory
        except Exception:
            pass
        threading.Thread(target=self.start_voice, daemon=True).start()
        try:
            _install_hotkey(self.cfg.app.hotkey, self.talk)
        except ValueError as e:
            print(f"[app] hotkey disabled: {e}")
        self.timer.start()
        st = self.refresh_permissions()
        if permissions.missing(st):
            self.rumps.notification("Zero", "Permissions needed", permissions.summary(st))
        self.app.run()

    # ── UI refresh (main thread) ──
    def refresh_permissions(self) -> dict:
        st = permissions.status()
        marks = {permissions.GRANTED: "✓", permissions.MISSING: "✗"}
        for name, it in self.perm_items.items():
            why = permissions.PERMISSIONS[name][0]
            title = f"{marks.get(st[name], '·')} {name} — {why}"
            if it.title != title:
                it.title = title
        n = len(permissions.missing(st))
        want = f"Permissions ({n} needed)" if n else "Permissions"
        if self.item_perms.title != want:
            self.item_perms.title = want
        return st

    def fix_permission(self, sender) -> None:
        name = next((n for n, it in self.perm_items.items() if it is sender), None)
        if name:
            permissions.request(name)

    def refresh(self, _=None) -> None:
        self._perm_tick += 1
        if self._perm_tick % 10 == 0:          # every ~3 s: pick up grants made in Settings
            self.refresh_permissions()
        o = self.orch
        if self.error:
            self.app.title = ICONS["error"]
            self.item_status.title = "Error: " + self.error[:60]
            return
        if o is None or o.status == "starting":
            self.app.title = ICONS["starting"]
            return
        icon = "⊘" if o.muted and o.status == "idle" else ICONS.get(o.status, "◯")
        if self.app.title != icon:
            self.app.title = icon
        label = {"idle": "Muted — push-to-talk only" if o.muted else "Listening for “hey zero”",
                 "listening": "Listening…", "thinking": "Thinking…",
                 "speaking": "Speaking…"}.get(o.status, o.status.title())
        if self.item_status.title != label:
            self.item_status.title = label
        self.item_mute.state = o.muted

    # ── actions ──
    def _ready(self) -> bool:
        if self.orch is None or self.orch.brain is None:
            self.rumps.notification("Zero", "", "Still loading — give me a moment.")
            return False
        return True

    def talk(self, _=None) -> None:
        if self._ready():
            self.orch.push_to_talk()

    def type_prompt(self, _=None) -> None:
        if not self._ready():
            return
        w = self.rumps.Window(message="What can I do, Ahmad?", title="Zero",
                              default_text="", ok="Send", cancel="Cancel",
                              dimensions=(360, 60))
        r = w.run()
        if r.clicked and r.text.strip():
            self.orch.submit_text(r.text)

    def toggle_mute(self, _=None) -> None:
        if self.orch is not None:
            self.orch.set_muted(not self.orch.muted)

    def stop(self, _=None) -> None:
        if self.orch is not None:
            self.orch.stop_speaking()

    def open_hud(self, _=None) -> None:
        if self.window_proc is not None and self.window_proc.poll() is None:
            mac.osascript('tell application "System Events" to set frontmost of '
                          f'(first process whose unix id is {self.window_proc.pid}) to true')
            return
        try:
            import webview  # noqa: F401  (pywebview available → native window)
            self.window_proc = subprocess.Popen([sys.executable, "-m", "zero", "--window"])
        except Exception:
            webbrowser.open(self.hud_url)

    def toggle_login(self, sender) -> None:
        sender.state = _login_item(not sender.state)

    def quit(self, _=None) -> None:
        if self.window_proc is not None and self.window_proc.poll() is None:
            self.window_proc.terminate()
        self.rumps.quit_application()


def main() -> None:
    if not mac.IS_MAC:
        raise SystemExit("--app is macOS only; use `python -m zero` (voice) or `--text`.")
    ZeroApp().run()
