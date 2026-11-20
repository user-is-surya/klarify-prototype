"""Synthetic household sound generator for the Klarify prototype.

All sounds are synthesised (no recordings). render() returns int16 mono audio at 8 kHz.
"""
from __future__ import annotations

import numpy as np

SAMPLE_RATE = 8000

SOUNDS = ["background", "cooker_whistle", "doorbell", "baby_cry", "smoke_alarm", "microwave_beep"]

LEVELS = {
    "background": "none",
    "cooker_whistle": "urgent",
    "smoke_alarm": "urgent",
    "baby_cry": "important",
    "doorbell": "info",
    "microwave_beep": "info",
}

_PEAK_LIMIT = 0.9  # fraction of full scale


def _pattern_env(n: int, segments: list[tuple[float, float]], rng: np.random.Generator) -> np.ndarray:
    """Cyclic on/off envelope from (duration_s, level) segments, random start phase, 5 ms edges."""
    cycle = sum(d for d, _ in segments)
    offset = rng.uniform(0, cycle)
    t = (np.arange(n) / SAMPLE_RATE + offset) % cycle
    env = np.zeros(n)
    start = 0.0
    for dur, level in segments:
        env[(t >= start) & (t < start + dur)] = level
        start += dur
    k = max(1, int(0.005 * SAMPLE_RATE))
    return np.convolve(env, np.ones(k) / k, mode="same")


def _noise(n: int, rng: np.random.Generator, tilt: float = 0.5) -> np.ndarray:
    """Unit-RMS coloured noise with a 1/f**tilt amplitude spectrum."""
    spec = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    f = np.maximum(np.arange(n // 2 + 1), 1)
    spec *= 1.0 / f**tilt
    x = np.fft.irfft(spec, n)
    return x / (np.sqrt(np.mean(x**2)) + 1e-12)


def _tone(f_inst: np.ndarray) -> np.ndarray:
    return np.sin(2 * np.pi * np.cumsum(f_inst) / SAMPLE_RATE)


def _beeps(n, f0, on, off, count, pause, rng):
    segs = []
    for i in range(count):
        segs.append((on, 1.0))
        segs.append((off if i < count - 1 else pause, 0.0))
    env = _pattern_env(n, segs, rng)
    return env * _tone(np.full(n, f0)), env


def _cooker_whistle(n, rng):
    f0 = rng.uniform(2650, 3350)
    t = np.arange(n) / SAMPLE_RATE
    wobble = 0.04 * np.sin(2 * np.pi * rng.uniform(5, 8) * t + rng.uniform(0, 6.28))
    env = _pattern_env(n, [(rng.uniform(1.2, 1.8), 1.0), (rng.uniform(0.4, 0.7), 0.0)], rng)
    sig = _tone(f0 * (1 + wobble)) + 0.15 * _noise(n, rng, tilt=0.0)
    return env * sig, env


def _smoke_alarm(n, rng):
    on = rng.uniform(0.18, 0.25)
    return _beeps(n, rng.uniform(2900, 3300), on, on, 3, 1.0 + on, rng)


def _microwave(n, rng):
    on = rng.uniform(0.22, 0.28)
    return _beeps(n, rng.uniform(2000, 2400), on, on, 3, 1.5, rng)


def _doorbell(n, rng):
    sig = np.zeros(n)
    env = np.zeros(n)
    cycle = rng.uniform(1.8, 2.3)
    t0 = -rng.uniform(0, cycle)
    while t0 < n / SAMPLE_RATE:
        for note_t, f in ((0.0, 659.0), (0.45, 523.0)):
            s = int(round((t0 + note_t) * SAMPLE_RATE))
            length = int(0.5 * SAMPLE_RATE)
            a, b = max(s, 0), min(s + length, n)
            if a >= b:
                continue
            tt = (np.arange(a, b) - s) / SAMPLE_RATE
            decay = np.exp(-tt / 0.18)
            attack = np.minimum(tt / 0.004, 1.0)
            note = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)
            sig[a:b] += note * decay * attack
            env[a:b] = np.maximum(env[a:b], decay * attack)
        t0 += cycle
    return sig, env


def _baby_cry(n, rng):
    f0 = rng.uniform(350, 550)
    t = np.arange(n) / SAMPLE_RATE
    on, off = rng.uniform(0.7, 0.95), rng.uniform(0.25, 0.4)
    env = _pattern_env(n, [(on, 1.0), (off, 0.0)], rng)
    phase_in_burst = (t + rng.uniform(0, on + off)) % (on + off)
    contour = 1.0 - 0.15 * np.clip(phase_in_burst / on, 0, 1)
    vibrato = 0.05 * np.sin(2 * np.pi * rng.uniform(5, 6) * t)
    f = f0 * contour * (1 + vibrato)
    phase = 2 * np.pi * np.cumsum(f) / SAMPLE_RATE
    sig = np.zeros(n)
    for k in range(1, rng.integers(6, 9)):
        sig += np.sin(k * phase) / k**0.8
    return env * sig, env


def _background(n, rng):
    rms = rng.uniform(0.01, 0.10)
    x = rms * _noise(n, rng, tilt=rng.uniform(0.3, 1.0))
    if rng.random() < 0.4:  # mains hum
        t = np.arange(n) / SAMPLE_RATE
        for k in (1, 2, 3):
            x += rng.uniform(0.005, 0.03) / k * np.sin(2 * np.pi * 50 * k * t + rng.uniform(0, 6.28))
    for _ in range(rng.poisson(0.4 * n / SAMPLE_RATE)):  # clatter-like clicks
        s = int(rng.integers(0, max(1, n - 200)))
        length = int(rng.uniform(0.005, 0.02) * SAMPLE_RATE)
        tt = np.arange(min(length, n - s))
        x[s : s + len(tt)] += rng.uniform(0.15, 0.5) * rng.standard_normal(len(tt)) * np.exp(-tt / (length / 4))
    return x


_GENERATORS = {
    "cooker_whistle": _cooker_whistle,
    "smoke_alarm": _smoke_alarm,
    "microwave_beep": _microwave,
    "doorbell": _doorbell,
    "baby_cry": _baby_cry,
}


def render(sound: str, duration_s: float, snr_db: float, rng: np.random.Generator, return_mask: bool = False):
    """Render `duration_s` seconds of `sound` plus ambient noise at `snr_db`. Returns int16 mono.
    With return_mask=True returns (audio, mask) where mask marks samples where the sound is audible."""
    if sound not in SOUNDS:
        raise ValueError(f"unknown sound {sound!r}")
    n = int(round(duration_s * SAMPLE_RATE))
    mask = np.zeros(n, dtype=bool)
    if sound == "background":
        x = _background(n, rng)
    else:
        sig, env = _GENERATORS[sound](n, rng)
        sig = sig / (np.max(np.abs(sig)) + 1e-12) * rng.uniform(0.25, 0.6)
        on = env > 0.5
        sig_rms = np.sqrt(np.mean(sig[on] ** 2)) if on.any() else np.sqrt(np.mean(sig**2)) + 1e-9
        noise = _noise(n, rng, tilt=0.5) * sig_rms / (10 ** (snr_db / 20))
        x = sig + noise
        mask = env > 0.1
    peak = np.max(np.abs(x))
    if peak > _PEAK_LIMIT:
        x = x * (_PEAK_LIMIT / peak)
    out = np.round(x * 32767).astype(np.int16)
    return (out, mask) if return_mask else out
