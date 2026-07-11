from __future__ import annotations
import numpy as np
from silero_vad import load_silero_vad, VADIterator
from faster_whisper import WhisperModel
from zero.audio import int16_to_float32


class Recorder:
    """Feed 512-sample int16 chunks AFTER wake. Returns the float32 utterance on end-of-speech, else None."""
    def __init__(self, min_silence_ms: int = 600) -> None:
        self._vad = VADIterator(load_silero_vad(), threshold=0.5,
                                sampling_rate=16000, min_silence_duration_ms=min_silence_ms)
        self._collecting = False
        self._buf: list[np.ndarray] = []

    def _vad_step(self, chunk_f32: np.ndarray):
        return self._vad(chunk_f32)

    def reset(self) -> None:
        self._vad.reset_states(); self._collecting = False; self._buf = []

    def feed(self, chunk_int16: np.ndarray):
        f32 = int16_to_float32(chunk_int16)
        evt = self._vad_step(f32)
        if evt and "start" in evt:
            self._collecting = True; self._buf = []
        if self._collecting:
            self._buf.append(f32)
        if evt and "end" in evt and self._collecting:
            self._collecting = False
            return np.concatenate(self._buf).astype(np.float32) if self._buf else None
        return None


class Transcriber:
    def __init__(self, model: str, device: str, compute_type: str,
                 no_speech_max: float = 0.6, logprob_min: float = -1.0) -> None:
        if device == "auto":
            try:
                import torch
                cuda = torch.cuda.is_available()
            except Exception:
                cuda = False
            device = "cuda" if cuda else "cpu"
            compute_type = "float16" if cuda else "int8"
        self._model = WhisperModel(model, device=device, compute_type=compute_type)
        self._no_speech_max = no_speech_max
        self._logprob_min = logprob_min

    def transcribe(self, audio_f32: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio_f32, language="en", beam_size=5, condition_on_previous_text=False)
        # Hallucination gate: Whisper confidently invents phrases from noise/music
        # ("I don't know if I can get a taste of this" over ambient audio). A real
        # utterance has low no_speech_prob and a sane avg_logprob; drop the rest so
        # noise never reaches the brain as a command.
        kept = [s for s in segments
                if s.no_speech_prob <= self._no_speech_max
                and s.avg_logprob >= self._logprob_min]
        return " ".join(s.text.strip() for s in kept).strip()
