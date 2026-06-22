import json

import zero.os_bridge as ob


def _status(tmp, name, ok, summary=""):
    (tmp / f"{name}-status.json").write_text(
        json.dumps({"ok": ok, "summary": summary, "detail": {}}), encoding="utf-8"
    )


def _inbox(tmp, *items):
    tmp.joinpath("zero-inbox.ndjson").write_text(
        "".join(json.dumps(it) + "\n" for it in items), encoding="utf-8"
    )


def test_status_all_green(tmp_path, monkeypatch):
    monkeypatch.setattr(ob, "STATE_DIR", tmp_path)
    _status(tmp_path, "dream", "true")
    _status(tmp_path, "ci", "true")
    assert ob.status_summary() == "All two subsystems are green."


def test_status_flags_failing(tmp_path, monkeypatch):
    monkeypatch.setattr(ob, "STATE_DIR", tmp_path)
    _status(tmp_path, "dream", "true")
    _status(tmp_path, "wbs", "warn", "WBS reads empty")
    s = ob.status_summary()
    assert "one of two subsystems are green" in s
    assert "warning" in s and "WBS reads empty" in s


def test_status_no_state(tmp_path, monkeypatch):
    monkeypatch.setattr(ob, "STATE_DIR", tmp_path)
    assert "not reported" in ob.status_summary()


def test_inbox_returns_unspoken_only(tmp_path, monkeypatch):
    monkeypatch.setattr(ob, "STATE_DIR", tmp_path)
    _inbox(
        tmp_path,
        {"summary": "build red", "spoken": False},
        {"summary": "already told", "spoken": True},
        {"summary": "deploy drift", "spoken": False},
    )
    assert ob.read_inbox() == ["build red", "deploy drift"]


def test_inbox_drain_marks_spoken(tmp_path, monkeypatch):
    monkeypatch.setattr(ob, "STATE_DIR", tmp_path)
    _inbox(tmp_path, {"summary": "x", "spoken": False})
    ob.read_inbox(drain=True)
    # after draining, nothing is unspoken
    assert ob.read_inbox() == []
    lines = [json.loads(l) for l in (tmp_path / "zero-inbox.ndjson").read_text().splitlines() if l.strip()]
    assert all(it["spoken"] is True for it in lines)


def test_inbox_spoken_text_all_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(ob, "STATE_DIR", tmp_path)
    _inbox(tmp_path)
    assert "Nothing needs your attention" in ob.inbox_spoken_text()


def test_inbox_malformed_line_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(ob, "STATE_DIR", tmp_path)
    tmp_path.joinpath("zero-inbox.ndjson").write_text(
        '{"summary":"ok","spoken":false}\nNOT JSON\n', encoding="utf-8"
    )
    assert ob.read_inbox() == ["ok"]
