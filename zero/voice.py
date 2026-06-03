from __future__ import annotations
import re
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

    def _synth(self, text: str) -> np.ndarray:
        chunks = [a for _, _, a in self._pipe(text, voice=self._voice, speed=self._speed)]
        return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(1, np.float32)

    def speak(self, text: str) -> None:
        """Speak sentence-by-sentence so long replies start fast."""
        for sentence in split_sentences(text):
            audio.play(self._synth(sentence), samplerate=24000, block=True)
