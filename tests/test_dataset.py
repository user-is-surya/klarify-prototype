import numpy as np

from dataset import window_label


def test_window_label_background_when_window_is_silent_gap():
    mask = np.zeros(8000, dtype=bool)
    assert window_label(5, mask) == 0


def test_window_label_background_below_ten_percent_audible():
    mask = np.zeros(8000, dtype=bool)
    mask[:700] = True  # 8.75 %
    assert window_label(5, mask) == 0


def test_window_label_keeps_sound_when_enough_audible():
    mask = np.zeros(8000, dtype=bool)
    mask[:2000] = True  # 25 %, a single 0.25 s beep
    assert window_label(5, mask) == 5


def test_window_label_background_stays_background():
    assert window_label(0, np.zeros(8000, dtype=bool)) == 0
