"""mac — Zero's hands and eyes on macOS.

Exposes an in-process MCP server ("mac") so the brain can see the screen and
drive apps: screenshots, mouse/keyboard, the Accessibility tree, AppleScript,
Shortcuts, clipboard, volume and notifications.

Coordinates: every x/y Zero sees or uses is in the coordinate space of the LAST
screenshot (the image may be downscaled from the Retina display). ``click`` and
``ui_elements`` convert to/from real screen points using the scale recorded by
``screenshot``. Before any screenshot the scale is 1 (plain screen points).

Needs, on the Mac (granted to Zero.app, see README):
  Accessibility       — clicks, typing, key presses, reading UI elements
  Screen Recording    — screenshots
  Automation          — AppleScript control of other apps

Everything returns text errors instead of raising, so a missing permission is
something the brain can explain rather than a crash. The pure helpers at the
top are platform-independent and unit-tested on any OS.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile

IS_MAC = sys.platform == "darwin"
NOT_MAC = "Mac control is only available when Zero runs on macOS."

# ---------------------------------------------------------------------------
# Pure helpers (tested on every platform)
# ---------------------------------------------------------------------------

# macOS virtual key codes (ANSI layout) for keys that have no printable char.
KEY_CODES = {
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
    "backspace": 51, "escape": 53, "esc": 53, "forwarddelete": 117,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}
# printable keys → key codes (ANSI), used for the global hotkey.
CHAR_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25, "7": 26,
    "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38,
    "k": 40, "n": 45, "m": 46, ".": 47, ",": 43, "/": 44, ";": 41, "'": 39,
    "[": 33, "]": 30, "-": 27, "=": 24, "`": 50, "\\": 42,
}
_MODS = {
    "cmd": "command", "command": "command", "⌘": "command",
    "ctrl": "control", "control": "control", "⌃": "control",
    "alt": "option", "opt": "option", "option": "option", "⌥": "option",
    "shift": "shift", "⇧": "shift",
}


def parse_combo(combo: str) -> tuple[str, list[str]]:
    """'cmd+shift+t' -> ('t', ['command', 'shift']). Raises ValueError if empty
    or a modifier is unknown. The key is lower-cased unless it is a single
    character (so 'cmd+A' still means the A key)."""
    parts = [p.strip() for p in combo.replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise ValueError("empty key combo")
    *mods, key = parts
    out = []
    for m in mods:
        name = _MODS.get(m.lower())
        if not name:
            raise ValueError(f"unknown modifier: {m}")
        if name not in out:
            out.append(name)
    if len(key) > 1:
        key = key.lower()
    return key, out


def as_quote(s: str) -> str:
    """Quote a Python string as an AppleScript string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def key_script(combo: str) -> str:
    """AppleScript (System Events) that presses a key combo."""
    key, mods = parse_combo(combo)
    using = ""
    if mods:
        using = " using {" + ", ".join(f"{m} down" for m in mods) + "}"
    if key.lower() in KEY_CODES:
        action = f"key code {KEY_CODES[key.lower()]}"
    elif len(key) == 1:
        action = f"keystroke {as_quote(key.lower() if mods else key)}"
    else:
        raise ValueError(f"unknown key: {key}")
    return f'tell application "System Events" to {action}{using}'


def type_script(text: str) -> str:
    """AppleScript that types text; newlines become Return presses."""
    lines = text.split("\n")
    steps = []
    for i, line in enumerate(lines):
        if line:
            steps.append(f"keystroke {as_quote(line)}")
        if i < len(lines) - 1:
            steps.append("key code 36")
    body = "\n  ".join(steps) or "return"
    return f'tell application "System Events"\n  {body}\nend tell'


class Coords:
    """Maps between screenshot-image coordinates and real screen points."""

    def __init__(self) -> None:
        self.scale = 1.0  # screen points per image pixel

    def set_from(self, image_w: int, screen_w_points: float) -> None:
        if image_w > 0 and screen_w_points > 0:
            self.scale = screen_w_points / float(image_w)

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        return x * self.scale, y * self.scale

    def to_image(self, x: float, y: float) -> tuple[int, int]:
        return round(x / self.scale), round(y / self.scale)


COORDS = Coords()

# ---------------------------------------------------------------------------
# macOS plumbing
# ---------------------------------------------------------------------------


def _run(cmd: list[str], input: str | None = None, timeout: float = 30) -> tuple[bool, str]:
    try:
        p = subprocess.run(cmd, input=input, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {int(timeout)}s"
    out = (p.stdout or "").strip()
    if p.returncode != 0:
        err = (p.stderr or out or f"exit {p.returncode}").strip()
        return False, _explain(err)
    return True, out


def _explain(err: str) -> str:
    """Turn cryptic TCC errors into something the brain can relay."""
    low = err.lower()
    if "-1719" in err or "-25211" in err or "assistive access" in low or "not allowed to send keystrokes" in low:
        return err + " (Zero needs Accessibility permission: System Settings > Privacy & Security > Accessibility > Zero)"
    if "-1743" in err or "not authorized to send apple events" in low:
        return err + " (Zero needs Automation permission for that app: System Settings > Privacy & Security > Automation > Zero)"
    return err


def osascript(script: str, *args: str, js: bool = False, timeout: float = 30) -> tuple[bool, str]:
    if not IS_MAC:
        return False, NOT_MAC
    cmd = ["osascript"] + (["-l", "JavaScript"] if js else []) + ["-e", script, *args]
    return _run(cmd, timeout=timeout)


def screen_size_points() -> tuple[float, float]:
    """Main display size in points (not Retina pixels)."""
    try:
        import Quartz  # pyobjc-framework-Quartz
        b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        return float(b.size.width), float(b.size.height)
    except Exception:
        pass
    ok, out = osascript('tell application "Finder" to get bounds of window of desktop')
    if ok:
        try:
            _, _, w, h = [float(v) for v in out.split(",")]
            return w, h
        except ValueError:
            pass
    return 0.0, 0.0


def screenshot(max_width: int = 1440) -> tuple[bool, str, str]:
    """Capture the main display. Returns (ok, base64_jpeg_or_error, note)."""
    if not IS_MAC:
        return False, NOT_MAC, ""
    fd, raw = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    small = raw[:-4] + ".jpg"
    try:
        ok, err = _run(["screencapture", "-x", "-m", "-t", "png", raw], timeout=15)
        if not ok or os.path.getsize(raw) == 0:
            return False, (err or "empty capture") + (
                " (Zero needs Screen Recording permission: System Settings > "
                "Privacy & Security > Screen Recording > Zero)"), ""
        ok, err = _run(["sips", "-Z", str(max_width), "-s", "format", "jpeg",
                        "-s", "formatOptions", "70", raw, "--out", small], timeout=15)
        if not ok:
            return False, err, ""
        ok, dims = _run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", small])
        w = h = 0
        for line in dims.splitlines():
            if "pixelWidth" in line:
                w = int(line.split(":")[1])
            elif "pixelHeight" in line:
                h = int(line.split(":")[1])
        sw, _ = screen_size_points()
        COORDS.set_from(w, sw)
        with open(small, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        note = (f"Screenshot is {w}x{h}. Use these image coordinates for click/scroll "
                f"(1 image px = {COORDS.scale:.3f} screen points).")
        return True, data, note
    finally:
        for p in (raw, small):
            try:
                os.remove(p)
            except OSError:
                pass


def _quartz():
    try:
        import Quartz
        return Quartz
    except Exception:
        return None


def click(x: float, y: float, button: str = "left", count: int = 1) -> tuple[bool, str]:
    if not IS_MAC:
        return False, NOT_MAC
    sx, sy = COORDS.to_screen(x, y)
    Q = _quartz()
    if Q is not None:
        kinds = {
            "left": (Q.kCGEventLeftMouseDown, Q.kCGEventLeftMouseUp, Q.kCGMouseButtonLeft),
            "right": (Q.kCGEventRightMouseDown, Q.kCGEventRightMouseUp, Q.kCGMouseButtonRight),
        }
        down, up, btn = kinds.get(button, kinds["left"])
        pt = (sx, sy)
        Q.CGEventPost(Q.kCGHIDEventTap, Q.CGEventCreateMouseEvent(None, Q.kCGEventMouseMoved, pt, btn))
        for i in range(1, max(1, count) + 1):
            for kind in (down, up):
                e = Q.CGEventCreateMouseEvent(None, kind, pt, btn)
                Q.CGEventSetIntegerValueField(e, Q.kCGMouseEventClickState, i)
                Q.CGEventPost(Q.kCGHIDEventTap, e)
        return True, f"{button} click x{count} at ({x:.0f}, {y:.0f})"
    if shutil.which("cliclick"):
        verb = {"right": "rc"}.get(button, "dc" if count >= 2 else "c")
        return _run(["cliclick", f"{verb}:{int(sx)},{int(sy)}"])
    return False, "no mouse backend: pip install pyobjc-framework-Quartz (or brew install cliclick)"


def move_mouse(x: float, y: float) -> tuple[bool, str]:
    if not IS_MAC:
        return False, NOT_MAC
    sx, sy = COORDS.to_screen(x, y)
    Q = _quartz()
    if Q is None:
        return False, "pyobjc-framework-Quartz is not installed"
    Q.CGEventPost(Q.kCGHIDEventTap, Q.CGEventCreateMouseEvent(
        None, Q.kCGEventMouseMoved, (sx, sy), Q.kCGMouseButtonLeft))
    return True, f"mouse at ({x:.0f}, {y:.0f})"


def scroll(dy: int, dx: int = 0, x: float | None = None, y: float | None = None) -> tuple[bool, str]:
    """dy>0 scrolls up, dy<0 scrolls down (lines)."""
    if not IS_MAC:
        return False, NOT_MAC
    Q = _quartz()
    if Q is None:
        return False, "pyobjc-framework-Quartz is not installed"
    if x is not None and y is not None:
        move_mouse(x, y)
    e = Q.CGEventCreateScrollWheelEvent(None, Q.kCGScrollEventUnitLine, 2, int(dy), int(dx))
    Q.CGEventPost(Q.kCGHIDEventTap, e)
    return True, f"scrolled dy={dy} dx={dx}"


def frontmost_app() -> str:
    ok, out = osascript('tell application "System Events" to get name of first '
                        'application process whose frontmost is true', timeout=5)
    return out if ok else ""


_UI_JS = r"""
function run(argv) {
  const WANT = ["AXButton","AXTextField","AXTextArea","AXCheckBox","AXRadioButton",
    "AXPopUpButton","AXMenuButton","AXComboBox","AXLink","AXSlider","AXTab",
    "AXMenuItem","AXCell","AXSearchField","AXDisclosureTriangle"];
  const se = Application("System Events");
  const appName = argv[0] || "";
  const needle = (argv[1] || "").toLowerCase();
  const max = parseInt(argv[2] || "80");
  const press = argv[3] === "press";
  const p = appName ? se.processes.byName(appName)
                    : se.processes.whose({frontmost: true})[0];
  const wins = p.windows();
  if (!wins.length) return JSON.stringify({app: p.name(), window: "", elements: []});
  const w = wins[0];
  const out = [];
  let hit = null;
  const els = w.entireContents();
  for (let i = 0; i < els.length && out.length < max; i++) {
    const e = els[i];
    try {
      const role = e.role();
      if (WANT.indexOf(role) < 0) continue;
      let name = "";
      try { name = e.name() || ""; } catch (x) {}
      if (!name) { try { name = e.description() || ""; } catch (x) {} }
      if (!name) { try { const v = e.value(); name = (typeof v === "string") ? v : ""; } catch (x) {} }
      const pos = e.position(), size = e.size();
      const item = {role: role.replace(/^AX/, ""), name: String(name).slice(0, 80),
                    x: pos[0] + size[0] / 2, y: pos[1] + size[1] / 2};
      if (needle) {
        if (String(name).toLowerCase().indexOf(needle) < 0) continue;
        hit = item;
        if (press) {
          try { e.actions.byName("AXPress").perform(); item.pressed = true; } catch (x) { item.pressed = false; }
        }
        break;
      }
      out.push(item);
    } catch (x) {}
  }
  return JSON.stringify({app: p.name(), window: w.name() || "", elements: out, hit: hit});
}
"""


def ui_elements(app: str = "", limit: int = 80) -> tuple[bool, str]:
    ok, out = osascript(_UI_JS, app, "", str(limit), "", js=True, timeout=25)
    if not ok:
        return ok, out
    try:
        d = json.loads(out)
    except ValueError:
        return False, out
    lines = [f"{d['app']} — window: {d['window'] or '(untitled)'}"]
    for e in d["elements"]:
        ix, iy = COORDS.to_image(e["x"], e["y"])
        lines.append(f"{e['role']} \"{e['name']}\" at ({ix}, {iy})")
    if len(lines) == 1:
        lines.append("(no interactive elements found — try a screenshot)")
    return True, "\n".join(lines)


def click_element(name: str, app: str = "") -> tuple[bool, str]:
    """Press the first UI element whose name contains `name` (AXPress, falling
    back to a real click at its centre)."""
    ok, out = osascript(_UI_JS, app, name, "5000", "press", js=True, timeout=25)
    if not ok:
        return ok, out
    try:
        d = json.loads(out)
    except ValueError:
        return False, out
    hit = d.get("hit")
    if not hit:
        return False, f"no element matching \"{name}\" in {d.get('app')}"
    if hit.get("pressed"):
        return True, f"pressed {hit['role']} \"{hit['name']}\" in {d['app']}"
    ix, iy = COORDS.to_image(hit["x"], hit["y"])
    return click(ix, iy)


def list_windows() -> tuple[bool, str]:
    js = r"""
    function run() {
      const se = Application("System Events");
      const out = [];
      se.processes.whose({backgroundOnly: false})().forEach(p => {
        try {
          const ws = p.windows().map(w => { try { return w.name() || "(untitled)"; } catch (e) { return "?"; } });
          out.push((p.frontmost() ? "* " : "  ") + p.name() + (ws.length ? ": " + ws.join(" | ") : ""));
        } catch (e) {}
      });
      return out.join("\n");
    }"""
    return osascript(js, js=True, timeout=20)


def open_app(name: str) -> tuple[bool, str]:
    if not IS_MAC:
        return False, NOT_MAC
    ok, out = _run(["open", "-a", name])
    return ok, (f"opened {name}" if ok else out)


def activate_app(name: str) -> tuple[bool, str]:
    ok, out = osascript(f"tell application {as_quote(name)} to activate")
    return ok, (f"{name} is frontmost" if ok else out)


def quit_app(name: str) -> tuple[bool, str]:
    ok, out = osascript(f"tell application {as_quote(name)} to quit")
    return ok, (f"quit {name}" if ok else out)


def open_target(target: str) -> tuple[bool, str]:
    """Open a URL, file or folder with its default app."""
    if not IS_MAC:
        return False, NOT_MAC
    ok, out = _run(["open", os.path.expanduser(target)])
    return ok, (f"opened {target}" if ok else out)


def type_text(text: str) -> tuple[bool, str]:
    ok, out = osascript(type_script(text))
    return ok, (f"typed {len(text)} characters" if ok else out)


def press_key(combo: str) -> tuple[bool, str]:
    try:
        script = key_script(combo)
    except ValueError as e:
        return False, str(e)
    ok, out = osascript(script)
    return ok, (f"pressed {combo}" if ok else out)


def run_applescript(script: str, javascript: bool = False) -> tuple[bool, str]:
    ok, out = osascript(script, js=javascript, timeout=60)
    return ok, (out or "done") if ok else out


def list_shortcuts() -> tuple[bool, str]:
    if not IS_MAC:
        return False, NOT_MAC
    return _run(["shortcuts", "list"])


def run_shortcut(name: str, text_input: str = "") -> tuple[bool, str]:
    if not IS_MAC:
        return False, NOT_MAC
    cmd = ["shortcuts", "run", name]
    path = None
    if text_input:
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text_input)
        cmd += ["--input-path", path]
    try:
        ok, out = _run(cmd, timeout=120)
    finally:
        if path:
            os.remove(path)
    return ok, (out or f"ran shortcut {name}") if ok else out


def get_clipboard() -> tuple[bool, str]:
    if not IS_MAC:
        return False, NOT_MAC
    return _run(["pbpaste"])


def set_clipboard(text: str) -> tuple[bool, str]:
    if not IS_MAC:
        return False, NOT_MAC
    ok, out = _run(["pbcopy"], input=text)
    return ok, ("clipboard set" if ok else out)


def set_volume(level: int) -> tuple[bool, str]:
    level = max(0, min(100, int(level)))
    ok, out = osascript(f"set volume output volume {level}")
    return ok, (f"volume {level}%" if ok else out)


def notify(text: str, title: str = "Zero") -> tuple[bool, str]:
    ok, out = osascript(f"display notification {as_quote(text)} with title {as_quote(title)}")
    return ok, ("notified" if ok else out)


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required}


_S = {"type": "string"}
_N = {"type": "number"}
_I = {"type": "integer"}

# name -> (description, schema, handler(args) -> (ok, text))
TOOLS: dict[str, tuple[str, dict, object]] = {
    "screenshot": (
        "See the main screen. Returns an image; x/y for click/scroll use this image's coordinates.",
        _schema({}, []), None),
    "frontmost_app": ("Name of the app currently in front.", _schema({}, []),
                      lambda a: (True, frontmost_app() or "unknown")),
    "list_windows": ("Running apps and their window titles (* = frontmost).", _schema({}, []),
                     lambda a: list_windows()),
    "ui_elements": (
        "List clickable/typeable elements (buttons, fields, links…) in the front window of an app "
        "(default: frontmost app), with centre coordinates in screenshot space. Prefer this over "
        "guessing from a screenshot.",
        _schema({"app": _S, "limit": _I}, []),
        lambda a: ui_elements(a.get("app", ""), int(a.get("limit", 80)))),
    "click_element": (
        "Press the first UI element whose name contains `name` in the front window of `app` "
        "(default: frontmost app). The most reliable way to press a button.",
        _schema({"name": _S, "app": _S}, ["name"]),
        lambda a: click_element(a["name"], a.get("app", ""))),
    "click": (
        "Click at x,y (screenshot coordinates). button: left|right. count: 2 for double-click.",
        _schema({"x": _N, "y": _N, "button": {"type": "string", "enum": ["left", "right"]},
                 "count": _I}, ["x", "y"]),
        lambda a: click(a["x"], a["y"], a.get("button", "left"), int(a.get("count", 1)))),
    "scroll": (
        "Scroll by lines: dy>0 up, dy<0 down; optional x,y to scroll over a spot.",
        _schema({"dy": _I, "dx": _I, "x": _N, "y": _N}, ["dy"]),
        lambda a: scroll(a["dy"], a.get("dx", 0), a.get("x"), a.get("y"))),
    "type_text": ("Type text into the focused field (newlines press Return).",
                  _schema({"text": _S}, ["text"]), lambda a: type_text(a["text"])),
    "press_key": (
        "Press a key or combo, e.g. 'return', 'cmd+c', 'cmd+shift+t', 'esc', 'down'.",
        _schema({"combo": _S}, ["combo"]), lambda a: press_key(a["combo"])),
    "open_app": ("Launch (or focus) an app by name, e.g. 'Safari'.",
                 _schema({"name": _S}, ["name"]), lambda a: open_app(a["name"])),
    "activate_app": ("Bring a running app to the front.",
                     _schema({"name": _S}, ["name"]), lambda a: activate_app(a["name"])),
    "quit_app": ("Quit an app (it may prompt to save).",
                 _schema({"name": _S}, ["name"]), lambda a: quit_app(a["name"])),
    "open": ("Open a URL, file or folder with its default app.",
             _schema({"target": _S}, ["target"]), lambda a: open_target(a["target"])),
    "run_applescript": (
        "Run AppleScript (or JXA with javascript=true) and return its result. Best for scripting "
        "apps directly: Music, Mail, Calendar, Finder, Safari, Notes, Reminders, System Events.",
        _schema({"script": _S, "javascript": {"type": "boolean"}}, ["script"]),
        lambda a: run_applescript(a["script"], bool(a.get("javascript", False)))),
    "list_shortcuts": ("List the user's Shortcuts.app shortcuts.", _schema({}, []),
                       lambda a: list_shortcuts()),
    "run_shortcut": ("Run a Shortcuts.app shortcut by name, with optional text input.",
                     _schema({"name": _S, "input": _S}, ["name"]),
                     lambda a: run_shortcut(a["name"], a.get("input", ""))),
    "get_clipboard": ("Read the clipboard text.", _schema({}, []), lambda a: get_clipboard()),
    "set_clipboard": ("Put text on the clipboard.", _schema({"text": _S}, ["text"]),
                      lambda a: set_clipboard(a["text"])),
    "set_volume": ("Set output volume 0-100.", _schema({"level": _I}, ["level"]),
                   lambda a: set_volume(a["level"])),
    "notify": ("Show a macOS notification.", _schema({"text": _S, "title": _S}, ["text"]),
               lambda a: notify(a["text"], a.get("title", "Zero"))),
}

TOOL_NAMES = [f"mcp__mac__{n}" for n in TOOLS]


def _text(ok: bool, msg: str) -> dict:
    out = {"content": [{"type": "text", "text": msg or ("ok" if ok else "failed")}]}
    if not ok:
        out["is_error"] = True
    return out


def build_tools():
    """The SDK tool objects (separate from the server so tests can call them)."""
    import asyncio
    from claude_agent_sdk import tool

    def make(name, desc, schema, fn):
        @tool(name, desc, schema)
        async def _t(args):
            if name == "screenshot":
                ok, data, note = await asyncio.to_thread(screenshot)
                if not ok:
                    return _text(False, data)
                return {"content": [{"type": "image", "data": data, "mimeType": "image/jpeg"},
                                    {"type": "text", "text": note}]}
            try:
                ok, msg = await asyncio.to_thread(fn, args)
            except Exception as e:  # never crash the brain over one tool
                ok, msg = False, f"{type(e).__name__}: {e}"
            return _text(ok, msg)
        return _t

    return [make(n, d, s, f) for n, (d, s, f) in TOOLS.items()]


def build_mac_mcp():
    from claude_agent_sdk import create_sdk_mcp_server
    return create_sdk_mcp_server(name="mac", version="1.0.0", tools=build_tools())
