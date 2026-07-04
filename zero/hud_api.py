"""hud_api.py — read-only HTTP handler for the Zero HUD.

Serves the static HUD from ui/ AND a small read-only API the HUD uses:
  GET /api/vault                      → JSON list of every memory + wiki file
  GET /api/vault/file?scope=&p=       → raw markdown of one file (path-sandboxed)
  GET /api/connections                → the OS topology graph + live-ish counts

Pure stdlib (no torch/whisper) so it runs under system python3 for a HUD-only
preview, and is also used by zero/hud.py in full voice mode. All reads are
sandboxed to two roots and to *.md — nothing else is reachable.
"""
from __future__ import annotations
import json
import os
import urllib.parse
from http.server import SimpleHTTPRequestHandler

HOME = os.path.expanduser("~")
ROOTS = {
    "memory": os.path.join(HOME, ".claude/projects/-Users-ahmadsharaf/memory"),
    "vault":  os.path.join(HOME, "Desktop/projects/calude code meomry/wiki"),
}
UI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")


def _list_files():
    out = []
    for scope, root in ROOTS.items():
        if not os.path.isdir(root):
            continue
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                ap = os.path.join(base, fn)
                rel = os.path.relpath(ap, root)
                try:
                    stt = os.stat(ap)
                except OSError:
                    continue
                # first non-empty, non-frontmatter line as a hint
                hint = ""
                try:
                    with open(ap, encoding="utf-8", errors="replace") as f:
                        infm = False
                        for ln in f:
                            s = ln.strip()
                            if s == "---":
                                infm = not infm
                                continue
                            if infm or not s or s.startswith("#"):
                                if s.startswith("# "):
                                    hint = s[2:]; break
                                continue
                            hint = s; break
                except OSError:
                    pass
                out.append({
                    "scope": scope,
                    "name": fn,
                    "path": rel.replace(os.sep, "/"),
                    "size": stt.st_size,
                    "mtime": int(stt.st_mtime),
                    "hint": hint[:120],
                })
    out.sort(key=lambda e: (-e["mtime"]))
    return out


def _read_file(scope, rel):
    root = ROOTS.get(scope)
    if not root:
        return None
    # sandbox: resolve and confirm it stays under the root, .md only
    ap = os.path.realpath(os.path.join(root, rel))
    if not ap.startswith(os.path.realpath(root) + os.sep) or not ap.endswith(".md"):
        return None
    if not os.path.isfile(ap):
        return None
    try:
        with open(ap, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


# the OS topology — structure is static; the UI lights nodes from /api/state (7717)
CONNECTIONS = {
    "nodes": [
        {"id": "ahmad", "label": "Ahmad", "group": "human", "x": 50, "y": 8},
        {"id": "zero", "label": "Zero — voice (ears/mouth)", "group": "zero", "x": 50, "y": 30},
        {"id": "bus", "label": "State bus  ~/.whisky-os-state", "group": "bus", "x": 50, "y": 54},
        {"id": "foundation", "label": "force-ai-foundation — eyes/hands", "group": "os", "x": 22, "y": 78},
        {"id": "memory", "label": "Memory + vault — brain", "group": "memory", "x": 78, "y": 78},
        {"id": "dream", "label": "dream cycle + audit fleet", "group": "os", "x": 22, "y": 95},
        {"id": "dash", "label": "dashboard :7717", "group": "os", "x": 50, "y": 78},
        {"id": "recall", "label": "graphify recall", "group": "memory", "x": 78, "y": 95},
    ],
    "edges": [
        ["ahmad", "zero", "speaks / hears"],
        ["zero", "bus", "reads status + inbox"],
        ["zero", "memory", "recalls"],
        ["foundation", "bus", "emit_event / emit_inbox"],
        ["dream", "foundation", "scans → findings"],
        ["dash", "bus", "renders"],
        ["memory", "recall", "graphify"],
        ["foundation", "memory", "encoded detectors ← lessons"],
    ],
}


class HudApiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=UI_DIR, **kw)

    # NOTE: deliberately NO Access-Control-Allow-Origin. The HUD page is served
    # from this same origin, so it needs no CORS. A wildcard here would let ANY
    # website open in the browser fetch + read the private vault/memory files
    # cross-origin (data exfiltration). Without CORS the browser makes such a
    # cross-origin response opaque/unreadable, so contents stay protected.
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, s, code=200):
        body = s.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/vault":
            return self._json({"files": _list_files()})
        if parsed.path == "/api/vault/file":
            q = urllib.parse.parse_qs(parsed.query)
            scope = (q.get("scope") or [""])[0]
            rel = (q.get("p") or [""])[0]
            content = _read_file(scope, rel)
            if content is None:
                return self._text("not found / not allowed", 404)
            return self._text(content)
        if parsed.path == "/api/connections":
            return self._json(CONNECTIONS)
        return super().do_GET()

    def log_message(self, *a):  # quiet
        pass
