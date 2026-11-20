"""Host -> ESP32 serial framing.  Frame: 'K' 'L' type len_lo len_hi payload checksum
checksum = XOR of type, len_lo, len_hi and every payload byte."""
from __future__ import annotations

import struct

import numpy as np

MAGIC = b"KL"
PCM = 0x01
PING = 0x02


def encode_frame(ftype: int, payload: bytes) -> bytes:
    n = len(payload)
    head = bytes([ftype & 0xFF, n & 0xFF, (n >> 8) & 0xFF])
    cs = 0
    for b in head + payload:
        cs ^= b
    return MAGIC + head + payload + bytes([cs])


def encode_pcm(seq: int, samples: np.ndarray) -> bytes:
    payload = struct.pack("<H", seq & 0xFFFF) + np.asarray(samples).astype("<i2").tobytes()
    return encode_frame(PCM, payload)


def encode_ping() -> bytes:
    return encode_frame(PING, b"")
