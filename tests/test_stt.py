import numpy as np
from zero.stt import Recorder

def test_recorder_collects_between_start_and_end(monkeypatch):
    r = Recorder(min_silence_ms=300)
    # stub the vad to emit start, then audio, then end
    seq = [{"start": 0}, None, None, {"end": 1}]
    monkeypatch.setattr(r, "_vad_step", lambda chunk: seq.pop(0) if seq else None)
    out = None
    for _ in range(4):
        out = r.feed(np.zeros(512, dtype=np.int16))
        if out is not None:
            break
    assert out is not None and out.dtype == np.float32
