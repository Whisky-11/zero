from __future__ import annotations
import asyncio, threading, queue, numpy as np
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

    def _confirm_aloud(self, question: str) -> bool:
        self._state("speaking", question); self.voice.speak(question)
        text = self._listen_once().lower()
        return any(w in text for w in ("yes", "do it", "proceed", "go ahead", "confirm"))

    def _listen_once(self) -> str:
        self.rec.reset()
        for chunk in self.mic.frames():
            utter = self.rec.feed(chunk)
            if utter is not None:
                return self.stt.transcribe(utter)
        return ""

    def run(self) -> None:
        self.mic.start(); self._state("idle")
        for chunk in self.mic.frames():
            for frame in self.fb.push(chunk):
                if self.wake.feed(frame):
                    self._handle_turn()
                    self._state("idle")

    def _handle_turn(self) -> None:
        self._state("listening")
        text = self._listen_once()
        if not text:
            self._state("idle"); return
        self.store.log_turn("user", text)
        self._state("thinking", text)
        try:
            reply = asyncio.run(self.brain.ask_text(text))
        except Exception as e:
            self.voice.speak("Apologies, Ahmad, I hit an error."); self._state("idle"); return
        self.store.log_turn("assistant", reply)
