from __future__ import annotations
import numpy as np
from openwakeword.model import Model


class WakeListener:
    """Feed int16 audio; returns True on the frame the wake word is detected."""
    def __init__(self, model: str = "hey_jarvis", threshold: float = 0.5) -> None:
        self._key = model
        self._threshold = threshold
        # built-in models load by default; a custom path also works via wakeword_models=[...]
        self._model = Model(inference_framework="onnx")

    def feed(self, frame_int16: np.ndarray) -> bool:
        self._model.predict(frame_int16)
        score = float(self._model.prediction_buffer[self._key][-1])
        if score >= self._threshold:
            self._model.reset()
            return True
        return False


class FrameBuffer:
    """Accumulate small chunks into fixed-size frames."""
    def __init__(self, size: int = 1280) -> None:
        self._size = size; self._buf = np.empty(0, dtype=np.int16)

    def push(self, chunk: np.ndarray):
        self._buf = np.concatenate([self._buf, chunk])
        while len(self._buf) >= self._size:
            out, self._buf = self._buf[:self._size], self._buf[self._size:]
            yield out
