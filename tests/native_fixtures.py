"""Writes Python-computed reference data for the C++ parity tests."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from features import extract
from sounds import SOUNDS, render
from train import train


def write_protocol_stream(path: Path) -> None:
    """Byte stream for the parser test: garbage, a truncated PCM frame, a corrupt-checksum frame, then
    3 good frames: PING, PCM(seq=7), PCM(seq=8). Samples stay in [0, 200] so 'KL' never occurs by accident."""
    from protocol import encode_frame, encode_pcm, encode_ping, PING

    rng = np.random.default_rng(42)
    garbage = bytes(int(b) for b in rng.integers(0, 256, 80) if b != 0x4B)
    pcm_a = encode_pcm(1, rng.integers(0, 200, 400).astype(np.int16))
    truncated = pcm_a[:300]
    corrupt = bytearray(encode_frame(PING, b""))
    corrupt[-1] ^= 0xFF
    good = (
        encode_ping()
        + encode_pcm(7, rng.integers(0, 200, 400).astype(np.int16))
        + encode_pcm(8, rng.integers(0, 200, 400).astype(np.int16))
    )
    Path(path).write_bytes(garbage + truncated + bytes(corrupt) + garbage + good)


def write_feature_fixtures(out_dir: Path, n: int = 60, seed: int = 1) -> int:
    """Writes into out_dir: model.h (small tree), clips.bin (int16 x 8000 each), features.bin (float32 x 10),
    pred.bin (int32). The LAST TWO clips are a silent clip and a full-scale square wave. Returns clip count."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = train(out_dir / "model.h", seed=0, n_per_class=100)

    rng = np.random.default_rng(seed)
    clips = []
    for i in range(n):
        sound = SOUNDS[i % len(SOUNDS)]
        clip = render(sound, 4.0, rng.uniform(3, 30), rng)
        off = int(rng.integers(0, 3 * 8000 + 1))
        clips.append(clip[off : off + 8000])
    clips.append(np.zeros(8000, dtype=np.int16))
    clips.append(np.where((np.arange(8000) // 20) % 2 == 0, 32767, -32768).astype(np.int16))

    feats = np.stack([extract(c) for c in clips]).astype(np.float32)
    pred = result.tree.predict(feats).astype(np.int32)
    pred[feats[:, 4] == 0.0] = 0  # silence rule lives in classify()
    np.stack(clips).astype("<i2").tofile(out_dir / "clips.bin")
    feats.astype("<f4").tofile(out_dir / "features.bin")
    pred.astype("<i4").tofile(out_dir / "pred.bin")
    return len(clips)
