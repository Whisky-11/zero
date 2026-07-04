from __future__ import annotations
import re
import threading
import numpy as np
from kokoro import KPipeline
from zero import audio

_SENT = re.compile(r".+?(?:[.!?](?:\s|$)|$)", re.S)

def split_sentences(text: str) -> list[str]:
    return [m.group().strip() for m in _SENT.finditer(text.strip()) if m.group().strip()]


class Voice:
    def __init__(self, lang_code: str = "b", voice: str = "bm_george", speed: float = 1.0) -> None:
        self._pipe = KPipeline(lang_code=lang_code)
        self._voice = voice; self._speed = speed
        self._stop = threading.Event()   # set by stop() to barge-in mid-speech

    def _synth(self, text: str) -> np.ndarray:
        chunks = [a for _, _, a in self._pipe(text, voice=self._voice, speed=self._speed)]
        return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(1, np.float32)

    def speak(self, text: str) -> None:
        """Speak sentence-by-sentence so long replies start fast. Abortable mid-way
        via stop() (barge-in): it stops at the next sentence boundary or cuts the
        current clip immediately."""
        self._stop.clear()
        for sentence in split_sentences(text):
            if self._stop.is_set():
                break
            if not audio.play_interruptible(self._synth(sentence), 24000, self._stop):
                break   # interrupted mid-clip

    def stop(self) -> None:
        """Interrupt any in-progress speech immediately (barge-in)."""
        self._stop.set()
        audio.stop_playback()
