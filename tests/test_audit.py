import asyncio, json
from types import SimpleNamespace
from zero.audit import Audit
from zero.gate import build_pretooluse_hook


def test_audit_appends_clips_and_reads_back(tmp_path):
    a = Audit(tmp_path / "audit.ndjson")
    a.record({"tool": "type_text", "input": {"text": "x" * 1000}, "outcome": "allowed"})
    a.record({"tool": "click", "input": {"x": 1, "y": 2}, "outcome": "declined"})
    rows = a.recent()
    assert [r["tool"] for r in rows] == ["type_text", "click"]
    assert len(rows[0]["input"]["text"]) < 400 and "chars)" in rows[0]["input"]["text"]
    assert rows[1]["input"] == {"x": 1, "y": 2} and "ts" in rows[1]


def test_audit_rotates(tmp_path, monkeypatch):
    import zero.audit as au
    monkeypatch.setattr(au, "MAX_BYTES", 200)
    a = Audit(tmp_path / "audit.ndjson")
    for i in range(20):
        a.record({"tool": "click", "i": i})
    assert (tmp_path / "audit.ndjson.1").exists()
    assert a.recent(1)[0]["i"] == 19


def _cfg(confirm_input=False):
    return SimpleNamespace(
        gate=SimpleNamespace(confirm_patterns=["rm "], never_patterns=["rm -rf /"]),
        mac=SimpleNamespace(sensitive_apps=["Mail"], confirm_input=confirm_input))


def _run(hook, tool, inp):
    return asyncio.run(hook({"hook_event_name": "PreToolUse", "tool_name": tool,
                             "tool_input": inp}, "id", None))


def test_hook_reports_every_outcome():
    events = []
    answers = iter([True, False])
    hook = build_pretooluse_hook(_cfg(), confirm_aloud=lambda q: next(answers),
                                 frontmost_fn=lambda: "Mail", on_action=events.append)
    assert _run(hook, "mcp__mac__screenshot", {}) == {}
    assert _run(hook, "mcp__mac__click_element", {"name": "Send"}) == {}       # yes
    denied = _run(hook, "Bash", {"command": "rm a.txt"})                        # no
    assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
    _run(hook, "Bash", {"command": "rm -rf /"})
    assert [(e["tool"], e["outcome"]) for e in events] == [
        ("screenshot", "allowed"), ("click_element", "confirmed"),
        ("Bash", "declined"), ("Bash", "denied")]
    assert events[1]["summary"] == 'press "Send" in Mail' and events[1]["app"] == "Mail"
    assert events[0]["summary"] == "look at the screen"


def test_hook_survives_broken_reporter():
    def boom(e): raise RuntimeError("x")
    hook = build_pretooluse_hook(_cfg(), confirm_aloud=lambda q: True, on_action=boom)
    assert _run(hook, "Read", {"file_path": "a"}) == {}
