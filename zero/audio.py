from __future__ import annotations
import queue
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 512          # 32 ms — matches silero-vad chunk size


def int16_to_float32(x: np.ndarray) -> np.ndarray:
    return (x.astype(np.float32) / 32768.0)


class Mic:
    """Always-on 16 kHz mono input. .frames() yields int16 numpy chunks of BLOCK."""
    def __init__(self) -> None:
        self._q: queue.Queue[np.ndarray] = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, blocksize=BLOCK, channels=1,
            dtype="int16", callback=self._cb,
        )

    def _cb(self, indata, frames, time, status) -> None:
        self._q.put(indata[:, 0].copy())

    def start(self) -> None: self._stream.start()
    def stop(self) -> None: self._stream.stop()

    def frames(self):
        while True:
            yield self._q.get()

    def flush(self) -> None:
        """Drop buffered audio captured while we weren't actively listening
        (the command tail, Zero's own voice, silence during thinking)."""
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass


def play(audio_f32: np.ndarray, samplerate: int = 24000, block: bool = True) -> None:
    sd.play(audio_f32, samplerate=samplerate)
    if block:
        sd.wait()


def stop_playback() -> None:
    sd.stop()
