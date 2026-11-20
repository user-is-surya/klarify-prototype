"""Builds a labelled synthetic feature dataset from the sound generator."""
from __future__ import annotations

import numpy as np

from features import WINDOW, extract
from sounds import SOUNDS, render

CLIP_S = 4.0
MIN_AUDIBLE = 0.10  # a window needs >= 10 % audible samples to count as the sound


def window_label(label: int, mask_window: np.ndarray) -> int:
    """Class label for a window: silent gaps between beeps are background, not the sound."""
    if label != 0 and np.mean(mask_window) < MIN_AUDIBLE:
        return 0
    return label


def make_dataset(n_per_class: int, seed: int, snr_range=(3.0, 30.0)) -> tuple[np.ndarray, np.ndarray]:
    """Returns X (N, 10) float32 and y (N,) int64 (index into SOUNDS)."""
    rng = np.random.default_rng(seed)
    X, y = [], []
    clip_len = int(CLIP_S * 8000)
    for label, sound in enumerate(SOUNDS):
        for _ in range(n_per_class):
            snr = rng.uniform(*snr_range)
            clip, mask = render(sound, CLIP_S, snr, rng, return_mask=True)
            off = int(rng.integers(0, clip_len - WINDOW + 1))
            X.append(extract(clip[off : off + WINDOW]))
            y.append(window_label(label, mask[off : off + WINDOW]))
    return np.stack(X).astype(np.float32), np.array(y, dtype=np.int64)
