"""Control plane of the orchestrator (typed turns, push-to-talk, mute, on-screen
confirm) with the audio/ML stack stubbed out — no mic, models or Claude."""
import sys, threading, time, types
import pytest


@pytest.fixture
def orch_cls(monkeypatch):
    stubs = {}
    for name, attrs in {
        "numpy": {}, "zero.audio": {"Mic": object}, "zero.wake": {"WakeListener": object, "FrameBuffer": object},
        "zero.stt": {"Recorder": object, "Transcriber": object}, "zero.voice": {"Voice": object},
        "zero.memory": {"Store": object}, "zero.brain": {"Brain": object},
    }.items():
        if name == "numpy" and "numpy" in sys.modules:
            continue
        m = types.ModuleType(name); m.__dict__.update(attrs); stubs[name] = m
    monkeypatch.delitem(sys.modules, "zero.orchestrator", raising=False)
    for k, v in stubs.items():
        monkeypatch.setitem(sys.modules, k, v)
    from zero.orchestrator import Orchestrator
    yield Orchestrator
    sys.modules.pop("zero.orchestrator", None)


class FakeHud:
    def __init__(self, clients=True): self.msgs = []; self.has_clients = clients
    def push_state(self, m): self.msgs.append(m)


class FakeBrain:
    def __init__(self, orch, confirm=False):
        self.orch, self.confirm, self.asked, self.answer = orch, confirm, [], None
    def ask(self, t):
        self.asked.append(t)
        if self.confirm:
            self.answer = self.orch._confirm_aloud("This will quit Xcode. Shall I proceed, Ahmad?")
        return "done"
    def interrupt(self): pass


class FakeStore:
    def __init__(self): self.turns = []
    def log_turn(self, r, t): self.turns.append((r, t))


class FakeVoice:
    def __init__(self): self.stopped = 0
    def stop(self): self.stopped += 1


def make(cls, clients=True, confirm=False):
    o = cls.__new__(cls)
    o.status, o.activity, o.muted = "idle", "", False
    o._turn_lock = threading.Lock(); o._ptt = threading.Event(); o._typed = False
    o._confirm_evt = threading.Event(); o._confirm_ok = False; o._interrupt = threading.Event()
    o.hud, o.store, o.voice = FakeHud(clients), FakeStore(), FakeVoice()
    o.brain = FakeBrain(o, confirm)
    return o


def wait_idle(o):
    for _ in range(200):
        if not o.busy and o.brain.asked:
            return
        time.sleep(0.01)


def test_typed_turn_logs_and_pushes_reply(orch_cls):
    o = make(orch_cls)
    o.handle_command({"type": "say", "text": "  open safari "})
    wait_idle(o)
    assert o.brain.asked == ["open safari"]
    assert ("assistant", "done") in o.store.turns
    assert {"type": "reply", "text": "done"} in o.hud.msgs
    assert o.status == "idle" and o._typed is False


def test_typed_turn_confirms_via_hud(orch_cls):
    o = make(orch_cls, confirm=True)
    o.submit_text("quit xcode")
    for _ in range(200):
        if any(m.get("type") == "confirm" for m in o.hud.msgs): break
        time.sleep(0.01)
    o.handle_command({"type": "confirm", "ok": True})
    wait_idle(o)
    assert o.brain.answer is True
    assert {"type": "confirm_done"} in o.hud.msgs


def test_typed_confirm_without_hud_off_mac_is_denied(orch_cls, monkeypatch):
    from zero import mac
    monkeypatch.setattr(mac, "IS_MAC", False)
    o = make(orch_cls, clients=False, confirm=True)
    o.submit_text("quit xcode"); wait_idle(o)
    assert o.brain.answer is False


def test_ptt_mute_and_stop(orch_cls):
    o = make(orch_cls)
    o.handle_command({"type": "ptt"})
    assert o._ptt.is_set()
    o.handle_command({"type": "mute", "on": True})
    assert o.muted and o.hud.msgs[-1]["muted"] is True
    with o._turn_lock:                   # busy → push-to-talk means stop
        o._ptt.clear(); o.push_to_talk()
        assert not o._ptt.is_set() and o.voice.stopped == 1 and o._interrupt.is_set()


def test_typed_before_ready(orch_cls):
    o = make(orch_cls); o.brain = None
    o.submit_text("hello")
    assert o.hud.msgs[-1]["type"] == "reply" and "warming" in o.hud.msgs[-1]["text"]
