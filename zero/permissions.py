"""permissions — check and request the macOS privacy permissions Zero needs.

Checks run inside Zero.app's Python child, and macOS evaluates them against the
responsible app (Zero.app), so they report Zero's real grants. Used by the menu
bar's "Permissions" submenu and at startup.

    python -m zero.permissions          # print a status table
"""
from __future__ import annotations

import ctypes
import ctypes.util
import subprocess
import sys

IS_MAC = sys.platform == "darwin"

GRANTED, MISSING, UNKNOWN = "granted", "missing", "unknown"

_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_"

# name -> (what it's for, Settings pane anchor)
PERMISSIONS = {
    "Microphone": ("hearing you", "Microphone"),
    "Accessibility": ("clicks, typing, reading buttons, the hotkey", "Accessibility"),
    "Screen Recording": ("screenshots", "ScreenCapture"),
    "Automation": ("scripting other apps (asked per app)", "Automation"),
}


def settings_url(name: str) -> str:
    return _PANE + PERMISSIONS[name][1]


def _cfunc(framework: str, symbol: str):
    path = f"/System/Library/Frameworks/{framework}.framework/{framework}"
    try:
        lib = ctypes.cdll.LoadLibrary(path)
        f = getattr(lib, symbol)
        f.restype = ctypes.c_bool
        f.argtypes = []
        return f
    except (OSError, AttributeError):
        return None


def accessibility() -> str:
    f = _cfunc("ApplicationServices", "AXIsProcessTrusted")
    return UNKNOWN if f is None else (GRANTED if f() else MISSING)


def screen_recording() -> str:
    f = _cfunc("CoreGraphics", "CGPreflightScreenCaptureAccess")
    return UNKNOWN if f is None else (GRANTED if f() else MISSING)


def microphone() -> str:
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
    except Exception:
        return UNKNOWN
    status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeAudio)
    # 0 not determined, 1 restricted, 2 denied, 3 authorized
    return {3: GRANTED, 0: UNKNOWN}.get(int(status), MISSING)


def status() -> dict[str, str]:
    if not IS_MAC:
        return {n: UNKNOWN for n in PERMISSIONS}
    return {
        "Microphone": microphone(),
        "Accessibility": accessibility(),
        "Screen Recording": screen_recording(),
        "Automation": UNKNOWN,   # macOS asks per target app; nothing to preflight
    }


def missing(st: dict[str, str]) -> list[str]:
    return [n for n, s in st.items() if s == MISSING]


def summary(st: dict[str, str]) -> str:
    gone = missing(st)
    if not gone:
        return "All permissions granted."
    return "Zero needs " + ", ".join(gone) + " — open Permissions in the menu bar."


def request(name: str) -> None:
    """Trigger the system prompt where macOS offers one, and open the Settings
    pane so the switch is one click away."""
    if not IS_MAC:
        return
    try:
        if name == "Accessibility":
            from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
            AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
        elif name == "Screen Recording":
            f = _cfunc("CoreGraphics", "CGRequestScreenCaptureAccess")
            if f is not None:
                f()
        elif name == "Microphone":
            from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
            AVCaptureDevice.requestAccessForMediaType_completionHandler_(AVMediaTypeAudio, lambda ok: None)
    except Exception:
        pass
    subprocess.run(["open", settings_url(name)], check=False)


def _main() -> int:
    st = status()
    for n, s in st.items():
        mark = {GRANTED: "✓", MISSING: "✗"}.get(s, "?")
        print(f"{mark} {n:<17} {s:<8} {PERMISSIONS[n][0]}")
    print(summary(st))
    return 0 if not missing(st) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
