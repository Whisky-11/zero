import os
import numpy as np
import pytest
from zero.wake import WakeListener

def test_silence_does_not_trigger():
    w = WakeListener(model="hey_jarvis", threshold=0.5)
    triggered = False
    for _ in range(20):
        if w.feed(np.zeros(1280, dtype=np.int16)):
            triggered = True
    assert triggered is False

@pytest.mark.skipif(not os.path.exists("zero/models/hey_zero.onnx"),
                    reason="custom hey_zero model not present")
def test_custom_onnx_model_loads_and_keys():
    w = WakeListener(model="zero/models/hey_zero.onnx", threshold=0.7)
    assert w._key == "hey_zero"
    assert w.feed(np.zeros(1280, dtype=np.int16)) is False
