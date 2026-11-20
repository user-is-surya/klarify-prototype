"""Reference (Python) feature extraction. The C++ twin lives in firmware/include/core/features.h
and must follow exactly the same definition (see docs plan, Task 2)."""
from __future__ import annotations

import numpy as np

SAMPLE_RATE = 8000
WINDOW = 8000
FRAME = 512
STEP = 256
N_FRAMES = (WINDOW - FRAME) // STEP + 1  # 30
BIN_HZ = SAMPLE_RATE / FRAME  # 15.625
N_BINS = 255  # bins k = 1..255
SILENCE_RMS = 1e-4

FEATURE_NAMES = [
    "dom_freq", "centroid", "flatness", "bandwidth", "duty",
    "pulses", "freq_std", "peak_ratio", "rms_cv", "harm2",
]

_HANN = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(FRAME) / FRAME))
_K = np.arange(1, N_BINS + 1, dtype=np.float64)


def extract(window: np.ndarray) -> np.ndarray:
    """int16 window of 8000 samples -> float32 vector of 10 features."""
    x = np.asarray(window, dtype=np.float64) / 32768.0
    out = np.zeros(10, dtype=np.float64)
    out[2] = 1.0  # flatness default (silence)

    starts = np.arange(N_FRAMES) * STEP
    frames = np.stack([x[s : s + FRAME] for s in starts])
    rms = np.sqrt(np.mean(frames**2, axis=1))
    max_rms = rms.max()
    if max_rms < SILENCE_RMS:
        return out.astype(np.float32)

    mags = np.abs(np.fft.rfft(frames * _HANN, axis=1))[:, 1 : N_BINS + 1]  # k = 1..255
    active = rms >= 0.5 * max_rms
    idx = np.nonzero(active)[0]

    peaks = np.argmax(mags, axis=1) + 1  # bin number k
    cents, flats, bws, pratio, harm = [], [], [], [], []
    for i in idx:
        m = mags[i]
        tot = m.sum() + 1e-12
        c = float((_K * m).sum() / tot)
        cents.append(c)
        flats.append(float(np.exp(np.mean(np.log(m + 1e-9))) / (np.mean(m) + 1e-9)))
        bws.append(float(np.sqrt(((_K - c) ** 2 * m).sum() / tot)))
        p = int(peaks[i])
        pratio.append(float(m[p - 1] / tot))
        lo, hi = min(2 * p - 1, N_BINS), min(2 * p + 1, N_BINS)
        harm.append(float(m[lo - 1 : hi].max() / (m[p - 1] + 1e-9)))

    pk = peaks[idx].astype(np.float64)
    out[0] = np.sort(pk)[(len(pk) - 1) // 2] * BIN_HZ
    out[1] = np.mean(cents) * BIN_HZ
    out[2] = np.mean(flats)
    out[3] = np.mean(bws) * BIN_HZ
    out[4] = len(idx) / N_FRAMES
    out[5] = sum(1 for i in idx if i == 0 or not active[i - 1])
    out[6] = np.std(pk * BIN_HZ)
    out[7] = np.mean(pratio)
    out[8] = np.std(rms) / (np.mean(rms) + 1e-9)
    out[9] = np.mean(harm)
    return out.astype(np.float32)
