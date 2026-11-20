import numpy as np

from protocol import PCM, PING, encode_frame, encode_pcm, encode_ping


def test_encode_pcm_length_and_checksum():
    samples = np.arange(400, dtype=np.int16)
    b = encode_pcm(7, samples)
    assert len(b) == 5 + 2 + 2 * 400 + 1
    assert b[:2] == b"KL" and b[2] == PCM
    assert b[3] | (b[4] << 8) == 2 + 800
    assert b[5] | (b[6] << 8) == 7
    x = 0
    for v in b[2:-1]:
        x ^= v
    assert b[-1] == x


def test_ping_frame_bytes():
    assert encode_ping() == bytes([0x4B, 0x4C, PING, 0, 0, PING])
    assert encode_frame(PING, b"") == encode_ping()
