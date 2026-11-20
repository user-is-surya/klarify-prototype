import numpy as np
import pytest

from sounds import LEVELS, SAMPLE_RATE, SOUNDS, render

EXPECTED = ["background", "cooker_whistle", "doorbell", "baby_cry", "smoke_alarm", "microwave_beep"]


def rng(seed=0):
    return np.random.default_rng(seed)


def test_sound_list_and_levels():
    assert SOUNDS == EXPECTED
    assert SAMPLE_RATE == 8000
    assert LEVELS == {
        "background": "none",
        "cooker_whistle": "urgent",
        "smoke_alarm": "urgent",
        "baby_cry": "important",
        "doorbell": "info",
        "microwave_beep": "info",
    }


def test_render_shape_dtype():
    x = render("doorbell", 2.0, 20, rng())
    assert x.shape == (16000,)
    assert x.dtype == np.int16


def test_render_is_deterministic_for_same_seed():
    a = render("baby_cry", 2.0, 15, rng(5))
    b = render("baby_cry", 2.0, 15, rng(5))
    assert np.array_equal(a, b)


@pytest.mark.parametrize("sound", EXPECTED)
@pytest.mark.parametrize("snr", [3, 30])
def test_no_clipping_any_sound_any_snr(sound, snr):
    x = render(sound, 3.0, snr, rng(1))
    assert np.abs(x.astype(np.int32)).max() < 32767
    assert np.abs(x).max() > 0


def _loudest_peak_hz(x, seg=800):
    xf = x.astype(np.float64)
    best, best_e = 0, -1
    for s in range(0, len(xf) - seg, seg // 2):
        e = np.sum(xf[s : s + seg] ** 2)
        if e > best_e:
            best_e, best = e, s
    chunk = xf[best : best + seg] * np.hanning(seg)
    spec = np.abs(np.fft.rfft(chunk, 8192))
    return np.argmax(spec) * SAMPLE_RATE / 8192


@pytest.mark.parametrize(
    "sound,lo,hi",
    [("cooker_whistle", 2500, 3500), ("smoke_alarm", 2900, 3300), ("microwave_beep", 2000, 2400)],
)
def test_dominant_frequency_ranges(sound, lo, hi):
    for seed in range(5):
        x = render(sound, 4.0, 30, rng(seed))
        f = _loudest_peak_hz(x)
        assert lo <= f <= hi, (sound, seed, f)


def test_doorbell_peak_is_one_of_the_two_notes():
    for seed in range(5):
        f = _loudest_peak_hz(render("doorbell", 4.0, 30, rng(seed)))
        assert min(abs(f - 523), abs(f - 659)) <= 20, f


def test_render_return_mask_shape_and_background_empty():
    x, mask = render("microwave_beep", 8.0, 20, rng(2), return_mask=True)
    assert mask.shape == x.shape and mask.dtype == bool
    assert mask.any() and (~mask).any()  # beeps and pauses both present
    _, bg = render("background", 2.0, 20, rng(2), return_mask=True)
    assert not bg.any()
