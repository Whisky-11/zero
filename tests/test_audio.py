import numpy as np
from zero.audio import int16_to_float32

def test_int16_to_float32_scales_to_unit_range():
    x = np.array([-32768, 0, 32767], dtype=np.int16)
    y = int16_to_float32(x)
    assert y.dtype == np.float32
    assert abs(y[0] + 1.0) < 1e-3 and abs(y[1]) < 1e-6 and abs(y[2] - 1.0) < 1e-3
