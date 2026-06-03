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


class Orchestrator:
    def __init__(self) -> None:
        self.cfg = load_config("config.toml")
        self.hud = Hud(self.cfg.hud.ws_port, self.cfg.hud.http_port); self.hud.start()
        self.mic = Mic()
        self.wake = WakeListener(self.cfg.wake.model, self.cfg.wake.threshold)
        self.fb = FrameBuffer(1280)
        self.rec = Recorder(self.cfg.stt.min_silence_ms)
        self.stt = Transcriber(self.cfg.stt.model, self.cfg.stt.device, self.cfg.stt.compute_type)
        self.voice = Voice(self.cfg.voice.lang_code, self.cfg.voice.voice, self.cfg.voice.speed)
        self.store = Store()
        self._answer_q: queue.Queue[str] = queue.Queue()
        self.brain = Brain(self.cfg, self.store,
                           confirm_aloud=self._confirm_aloud,
                           on_text=lambda t: self.voice.speak(t))

    def _state(self, status, activity=""):
        self.hud.push_state({"status": status, "activity": activity})

    # ~31 frames/sec (512 samples @ 16 kHz). Idle-frame budgets:
    _IDLE_FIRST = 330      # ~10.5 s to start speaking after wake
    _IDLE_FOLLOWUP = 200   # ~6.5 s to answer / continue without re-waking
    _IDLE_CONFIRM = 200    # ~6.5 s to say yes/no, else treated as "no"

    def _confirm_aloud(self, question: str) -> bool:
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

    def run(self) -> None:
        self.mic.start(); self._state("idle")
        for chunk in self.mic.frames():
            for frame in self.fb.push(chunk):
                if self.wake.feed(frame):
                    self._handle_turn()

    def _handle_turn(self) -> None:
        """One wake opens a conversation: keep listening for follow-ups (no wake
        word) until Ahmad goes quiet, then return to wake-listening."""
        follow = False
        while True:
            self._state("listening")
            text = self._listen_once(self._IDLE_FOLLOWUP if follow else self._IDLE_FIRST)
            if not text:
                break
            self.store.log_turn("user", text)
            self._state("thinking", text)
            try:
                reply = self.brain.ask(text)
            except Exception:
                self.voice.speak("Apologies, Ahmad, I hit an error."); break
            self.store.log_turn("assistant", reply)
            follow = True
        self.mic.flush()            # drop audio captured during the turn
        self._state("idle")
