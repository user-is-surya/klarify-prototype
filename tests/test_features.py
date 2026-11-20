import numpy as np

from features import FEATURE_NAMES, extract

FS = 8000
N = 8000
IDX = {n: i for i, n in enumerate(FEATURE_NAMES)}


def tone(f, amp=0.5):
    t = np.arange(N) / FS
    return (amp * 32767 * np.sin(2 * np.pi * f * t)).astype(np.int16)


def test_feature_names_order():
    assert FEATURE_NAMES == [
        "dom_freq", "centroid", "flatness", "bandwidth", "duty",
        "pulses", "freq_std", "peak_ratio", "rms_cv", "harm2",
    ]


def test_output_dtype_and_len():
    f = extract(tone(1000))
    assert f.dtype == np.float32 and f.shape == (10,)


def test_silence_gives_zeros_and_flatness_one_no_nan():
    f = extract(np.zeros(N, dtype=np.int16))
    assert np.all(np.isfinite(f))
    expected = np.zeros(10, dtype=np.float32)
    expected[IDX["flatness"]] = 1.0
    assert np.array_equal(f, expected)


def test_pure_3khz_tone():
    f = extract(tone(3000))
    assert abs(f[IDX["dom_freq"]] - 3000) <= 16
    assert f[IDX["duty"]] == 1.0
    assert f[IDX["pulses"]] == 1
    assert f[IDX["peak_ratio"]] > 0.3


def test_pulsed_tone_has_multiple_pulses():
    x = tone(3000)
    gate = ((np.arange(N) / FS) % 0.4) < 0.2
    f = extract((x * gate).astype(np.int16))
    assert f[IDX["pulses"]] >= 2


def test_white_noise_is_flat():
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(N) * 3000).astype(np.int16)
    assert extract(x)[IDX["flatness"]] > 0.5


def test_full_scale_square_wave_is_finite():
    x = np.where((np.arange(N) // 20) % 2 == 0, 32767, -32768).astype(np.int16)
    assert np.all(np.isfinite(extract(x)))
