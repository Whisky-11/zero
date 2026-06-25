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


def play_interruptible(audio_f32: np.ndarray, samplerate: int, stop_event) -> bool:
    """Play audio but abort early if stop_event is set (barge-in).

    Polls the event over the clip's known duration instead of a single blocking
    wait, so a wake-word mid-speech can cut playback. Returns True if it played
    to completion, False if it was interrupted.
    """
    import time
    sd.play(audio_f32, samplerate=samplerate)
    end = time.monotonic() + len(audio_f32) / float(samplerate) + 0.05
    while time.monotonic() < end:
        if stop_event.is_set():
            sd.stop()
            return False
        time.sleep(0.02)
    return True


def stop_playback() -> None:
    sd.stop()
