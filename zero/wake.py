from __future__ import annotations
from pathlib import Path
import numpy as np
from openwakeword.model import Model


class WakeListener:
    """Feed int16 audio; returns True on the frame the wake word is detected.

    `model` is either a built-in openWakeWord model name (e.g. "hey_jarvis")
    or a path to a custom .onnx model (e.g. "zero/models/hey_zero.onnx"); in the
    custom case the prediction key is the file stem (e.g. "hey_zero").
    """
    def __init__(self, model: str = "hey_jarvis", threshold: float = 0.5) -> None:
        self._threshold = threshold
        if model.endswith(".onnx") and not Path(model).exists():
            print(f"[zero] wake model {model} not found -> falling back to built-in 'hey_jarvis'")
            model = "hey_jarvis"
        if model.endswith(".onnx"):
            self._key = Path(model).stem
            self._model = Model(wakeword_models=[model], inference_framework="onnx")
        else:
            self._key = model
            self._model = Model(inference_framework="onnx")

    def feed(self, frame_int16: np.ndarray) -> bool:
        self._model.predict(frame_int16)
        score = float(self._model.prediction_buffer[self._key][-1])
        if score >= self._threshold:
            self._model.reset()
            return True
        return False

    def reset(self) -> None:
        """Clear the rolling buffer (e.g. before a fresh barge-in watch so audio
        from the previous phase can't carry a stale detection)."""
        self._model.reset()


class FrameBuffer:
    """Accumulate small chunks into fixed-size frames."""
    def __init__(self, size: int = 1280) -> None:
        self._size = size; self._buf = np.empty(0, dtype=np.int16)

    def push(self, chunk: np.ndarray):
        self._buf = np.concatenate([self._buf, chunk])
        while len(self._buf) >= self._size:
            out, self._buf = self._buf[:self._size], self._buf[self._size:]
            yield out
