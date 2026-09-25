"""prefetch — download every model Zero needs, once, before first launch.

    python -m zero.prefetch

Otherwise the first wake would stall for minutes while Whisper, Kokoro, the
wake-word and embedding models download. Each step is independent: a failure
is reported and the rest still run. Exit code 1 if any step failed.
"""
from __future__ import annotations

import sys
import time

from zero.config import load_config


def _step(name, fn) -> bool:
    t = time.time()
    print(f"[prefetch] {name} …", flush=True)
    try:
        fn()
    except Exception as e:
        print(f"[prefetch] {name} FAILED: {type(e).__name__}: {e}", flush=True)
        return False
    print(f"[prefetch] {name} ready ({time.time() - t:.0f}s)", flush=True)
    return True


def main() -> int:
    cfg = load_config()

    def wake():
        import openwakeword.utils
        openwakeword.utils.download_models()   # feature models + hey_jarvis fallback

    def vad():
        from silero_vad import load_silero_vad
        load_silero_vad()

    def whisper():
        from faster_whisper import WhisperModel
        WhisperModel(cfg.stt.model, device="cpu", compute_type="int8")

    def kokoro():
        from kokoro import KPipeline
        pipe = KPipeline(lang_code=cfg.voice.lang_code)
        for _ in pipe("Ready.", voice=cfg.voice.voice, speed=cfg.voice.speed):
            pass                                   # also fetches the voice pack

    def embeddings():
        from sentence_transformers import SentenceTransformer
        SentenceTransformer("all-MiniLM-L6-v2")

    results = [_step("wake word", wake), _step("voice activity", vad),
               _step(f"whisper '{cfg.stt.model}'", whisper),
               _step(f"kokoro voice '{cfg.voice.voice}'", kokoro),
               _step("memory embeddings", embeddings)]
    ok = all(results)
    print("[prefetch] all models ready." if ok else "[prefetch] some models failed — see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
