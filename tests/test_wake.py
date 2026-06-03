import numpy as np
from zero.wake import WakeListener

def test_silence_does_not_trigger():
    w = WakeListener(model="hey_jarvis", threshold=0.5)
    triggered = False
    for _ in range(20):
        if w.feed(np.zeros(1280, dtype=np.int16)):
            triggered = True
    assert triggered is False
