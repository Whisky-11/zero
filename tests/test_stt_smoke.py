import numpy as np, pytest
from zero.stt import Transcriber

@pytest.mark.manual
def test_transcriber_runs_on_silence():
    t = Transcriber("small", "cuda", "float16")
    out = t.transcribe(np.zeros(16000, dtype=np.float32))  # 1s silence
    assert isinstance(out, str)   # empty or near-empty, but no crash → CUDA OK
