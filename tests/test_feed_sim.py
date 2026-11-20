import re
import subprocess
import sys

import numpy as np
import pytest

from native_build import ROOT, build
from sounds import SOUNDS

FEED = ROOT / "tools" / "feed.py"
FIVE = SOUNDS[1:]


@pytest.fixture(scope="module")
def sim_exe(tmp_path_factory):
    return build(ROOT / "tests" / "native" / "sim_device.cpp", tmp_path_factory.mktemp("sim") / "sim_device.exe")


def feed(sim_exe, *args, timeout=300):
    r = subprocess.run(
        [sys.executable, str(FEED), "--sim", str(sim_exe), "--speed", "0", *args],
        capture_output=True, text=True, timeout=timeout,
    )
    return r


def cls_lines(stdout):
    out = []
    for m in re.finditer(r"^CLS (\w+) (none|alert|muted) (\d+)\s*$", stdout, re.M):
        out.append((m.group(1), m.group(2), int(m.group(3))))
    return out


def test_selftest_against_sim_prints_ok(sim_exe):
    r = feed(sim_exe, "--selftest")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"^OK klarify-fw", r.stdout, re.M)


def test_each_sound_detected_at_default_noise(sim_exe):
    script = "background:4," + ",".join(f"{s}:8,background:4" for s in FIVE)
    r = feed(sim_exe, "--script", script, "--seed", "7")
    assert r.returncode == 0, r.stdout + r.stderr
    lines = cls_lines(r.stdout)
    t = 4000
    for s in FIVE:
        start, end = t, t + 8000
        hits = [x for x in lines if x[0] == s and x[1] == "alert" and start <= x[2] <= end + 1000]
        assert hits, f"{s} not detected in [{start},{end}] ms; lines={[l for l in lines if l[1]=='alert']}"
        t += 12000


def test_no_false_alerts_in_30s_background_at_default_noise(sim_exe):
    r = feed(sim_exe, "--script", "background:30", "--seed", "3")
    assert r.returncode == 0, r.stdout + r.stderr
    lines = cls_lines(r.stdout)
    assert len(lines) >= 50
    assert not [l for l in lines if l[1] == "alert"], lines


def test_worst_noise_level_does_not_crash(sim_exe):
    script = ",".join(f"{s}:6" for s in FIVE)
    r = feed(sim_exe, "--script", script, "--noise-level", "5", "--seed", "1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(cls_lines(r.stdout)) >= 1


def test_find_port_returns_none_without_device_or_a_string():
    from feed import find_port

    p = find_port()
    assert p is None or isinstance(p, str)


def test_soundsource_block_is_400_int16():
    from feed import SoundSource

    s = SoundSource(seed=1)
    for name in SOUNDS:
        s.set_sound(name)
        b = s.next_block()
        assert b.shape == (400,) and b.dtype == np.int16
    s.set_noise_level(99)  # clamps
    assert s.next_block().shape == (400,)


def test_parse_script():
    from feed import parse_script

    assert parse_script("doorbell:8,background:4") == [("doorbell", 8.0), ("background", 4.0)]
    with pytest.raises(ValueError):
        parse_script("toaster:3")
