from __future__ import annotations
import threading, queue, numpy as np
from zero.config import load_config
from zero.audio import Mic
from zero.wake import WakeListener, FrameBuffer
from zero.stt import Recorder, Transcriber
from zero.voice import Voice
from zero.memory import Store
from zero.brain import Brain
from zero.hud import Hud
from zero import mac


class Orchestrator:
    def __init__(self) -> None:
        # control state first: the HUD starts accepting commands before the
        # (slow) models below have loaded
        self.status, self.activity = "starting", ""
        self.muted = False                  # mic muted = wake word ignored (push-to-talk still works)
        self.brain = None
        self._turn_lock = threading.Lock()  # one turn at a time (voice or typed)
        self._ptt = threading.Event()       # push-to-talk request from HUD / hotkey / menu
        self._typed = False                 # current turn came from text → confirm on screen, not mic
        self._confirm_evt = threading.Event(); self._confirm_ok = False
        self._interrupt = threading.Event()
        self.voice = None
        self.cfg = load_config()
        self.hud = Hud(self.cfg.hud.ws_port, self.cfg.hud.http_port, on_command=self.handle_command)
        self.hud.start(); self._state("starting", "loading models")
        self.mic = Mic()
        self.wake = WakeListener(self.cfg.wake.model, self.cfg.wake.threshold)
        self.fb = FrameBuffer(1280)
        self.rec = Recorder(self.cfg.stt.min_silence_ms)
        self.stt = Transcriber(self.cfg.stt.model, self.cfg.stt.device, self.cfg.stt.compute_type,
                               self.cfg.stt.no_speech_max, self.cfg.stt.logprob_min)
        self.voice = Voice(self.cfg.voice.lang_code, self.cfg.voice.voice, self.cfg.voice.speed)
        self.store = Store()
        self._answer_q: queue.Queue[str] = queue.Queue()
        self.brain = Brain(self.cfg, self.store,
                           confirm_aloud=self._confirm_aloud,
                           on_text=lambda t: self.voice.speak(t))
        # Barge-in: a SECOND wake detector that runs while Zero is thinking/speaking,
        # so saying "zero" mid-reply cuts it off and re-arms listening.
        self.barge = WakeListener(self.cfg.wake.model, self.cfg.wake.threshold)
        self._barge_stop = threading.Event()
        self._barge_thread = None

    def _state(self, status, activity=""):
        self.status, self.activity = status, activity
        self.hud.push_state({"status": status, "activity": activity, "muted": self.muted})

    def _push(self, msg: dict) -> None:
        self.hud.push_state(msg)

    # ── controls (HUD WebSocket, menu bar, global hotkey) ──────────────────
    def handle_command(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "say":
            self.submit_text(str(msg.get("text", "")))
        elif kind == "ptt":
            self.push_to_talk()
        elif kind == "mute":
            self.set_muted(bool(msg.get("on", not self.muted)))
        elif kind == "stop":
            self.stop_speaking()
        elif kind == "confirm":
            self._confirm_ok = bool(msg.get("ok"))
            self._confirm_evt.set()

    @property
    def busy(self) -> bool:
        return self._turn_lock.locked()

    def push_to_talk(self) -> None:
        """Start listening now, no wake word. While busy it acts as 'stop'."""
        if self.busy:
            self.stop_speaking()
        else:
            self._ptt.set()

    def set_muted(self, on: bool) -> None:
        self.muted = on
        self._state(self.status, self.activity)

    def stop_speaking(self) -> None:
        self._interrupt.set()
        if self.voice is not None:
            self.voice.stop()
        if self.brain is not None:
            self.brain.interrupt()

    def submit_text(self, text: str) -> None:
        """A typed request (HUD box / menu bar). Runs as its own turn."""
        text = text.strip()
        if not text:
            return
        if self.brain is None:
            self._push({"type": "reply", "text": "Still warming up, Ahmad. One moment."})
            return
        threading.Thread(target=self._typed_turn, args=(text,), daemon=True).start()

    def _typed_turn(self, text: str) -> None:
        with self._turn_lock:
            self._typed = True
            self._interrupt.clear()
            try:
                self._push({"type": "user", "text": text})
                self.store.log_turn("user", text)
                self._state("thinking", text)
                try:
                    reply = self.brain.ask(text)
                except Exception as e:
                    reply = ""
                    self._push({"type": "error", "text": f"{type(e).__name__}: {e}"})
                self.store.log_turn("assistant", reply or "")
                self._push({"type": "reply", "text": reply})
            finally:
                self._typed = False
                self._state("idle")

    def _confirm_on_screen(self, question: str) -> bool:
        """Typed turns can't use the mic (the wake loop owns it), so ask on screen:
        the HUD if one is open, else a native dialog."""
        if self.hud.has_clients:
            self._confirm_ok = False; self._confirm_evt.clear()
            self._push({"type": "confirm", "question": question})
            got = self._confirm_evt.wait(timeout=90)
            self._push({"type": "confirm_done"})
            return got and self._confirm_ok
        if mac.IS_MAC:
            ok, out = mac.osascript(
                f"display dialog {mac.as_quote(question)} buttons {{\"No\", \"Yes\"}} "
                f"default button \"No\" with title \"Zero\" giving up after 90", timeout=100)
            return ok and "button returned:Yes" in out
        return False

    # ~31 frames/sec (512 samples @ 16 kHz). Idle-frame budgets:
    _IDLE_FIRST = 330      # ~10.5 s to start speaking after wake
    _IDLE_FOLLOWUP = 200   # ~6.5 s to answer / continue without re-waking
    _IDLE_CONFIRM = 200    # ~6.5 s to say yes/no, else treated as "no"

    def _confirm_aloud(self, question: str) -> bool:
        if self._typed:
            return self._confirm_on_screen(question)
        self._state("speaking", question); self.voice.speak(question)
        text = self._listen_once(self._IDLE_CONFIRM).lower()   # silence/timeout -> deny
        return any(w in text for w in ("yes", "do it", "proceed", "go ahead", "confirm"))

    def _listen_once(self, max_idle_frames: int = 0) -> str:
        """Capture one utterance. Flushes stale audio first so it hears *fresh*
        speech. If max_idle_frames>0, return '' when no speech starts in time."""
        self.rec.reset()
        self.mic.flush()
        idle = 0
        for chunk in self.mic.frames():
            utter = self.rec.feed(chunk)
            if utter is not None:
                return self.stt.transcribe(utter)
            if max_idle_frames:
                if self.rec._collecting:
                    idle = 0
                else:
                    idle += 1
                    if idle >= max_idle_frames:
                        return ""
        return ""

    def _start_barge_monitor(self) -> None:
        """Watch the mic for the wake word while Zero is busy (thinking/speaking).
        On a hit: cut playback, interrupt the brain so ask() returns, flag it.
        Sole mic consumer during this window (the run loop / _listen_once are not
        reading), so no frames are stolen."""
        self._interrupt.clear()
        self._barge_stop.clear()
        self.barge.reset()
        fb = FrameBuffer(1280)

        def _monitor():
            for chunk in self.mic.frames():
                if self._barge_stop.is_set():
                    return
                for frame in fb.push(chunk):
                    if self.barge.feed(frame):
                        self._interrupt.set()
                        self.voice.stop()       # cut speech immediately
                        self.brain.interrupt()  # end generation so ask() unblocks
                        return

        self._barge_thread = threading.Thread(target=_monitor, daemon=True)
        self._barge_thread.start()

    def _stop_barge_monitor(self) -> None:
        self._barge_stop.set()
        t = self._barge_thread
        if t is not None:
            t.join(timeout=1.5)
            self._barge_thread = None

    def run(self) -> None:
        self.mic.start(); self._state("idle")
        for chunk in self.mic.frames():
            if self._ptt.is_set():
                self._ptt.clear()
                self._handle_turn()
                continue
            if self.muted:
                continue
            for frame in self.fb.push(chunk):
                if self.wake.feed(frame):
                    self._handle_turn()

    def _handle_turn(self) -> None:
        with self._turn_lock:
            self._voice_turn()

    def _voice_turn(self) -> None:
        """One wake opens a conversation: keep listening for follow-ups (no wake
        word) until Ahmad goes quiet, then return to wake-listening."""
        follow = False
        while True:
            self._state("listening")
            text = self._listen_once(self._IDLE_FOLLOWUP if follow else self._IDLE_FIRST)
            if not text:
                break
            # Hard exit phrases close the conversation window immediately — no brain
            # call, no reply, back to wake-listening. Added 2026-07-11 after Zero kept
            # interfering while Ahmad thought aloud ("stop... don't interfere me again").
            low = text.lower()
            if any(p in low for p in ("stop", "go to sleep", "that's all",
                                      "don't interfere", "do not interfere", "leave me")):
                self.store.log_turn("user", text)
                break
            self.store.log_turn("user", text)
            self._push({"type": "user", "text": text})
            self._state("thinking", text)
            self._start_barge_monitor()     # listen for "zero" during thinking + speaking
            try:
                reply = self.brain.ask(text)
            except Exception:
                self._stop_barge_monitor()
                if not self._interrupt.is_set():
                    self.voice.speak("Apologies, Ahmad, I hit an error.")
                    break
                reply = ""
            else:
                self._stop_barge_monitor()
            if self._interrupt.is_set():
                # Ahmad said "zero" mid-reply → drop the rest, re-arm and listen now.
                self.voice.stop()
                self._state("listening")
                follow = False              # fresh window, as if just woken
                continue
            self.store.log_turn("assistant", reply or "")
            self._push({"type": "reply", "text": reply or ""})
            follow = True
        self.mic.flush()            # drop audio captured during the turn
        self._state("idle")
