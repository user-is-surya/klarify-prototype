"""Smoke test of the packaged release (run after: python tools/build_release.py)."""
import re
import subprocess
import zipfile

import pytest

from native_build import ROOT

DIST = ROOT / "dist"
ZIP = DIST / "klarify-demo.zip"
NEEDED = {"firmware.bin", "esptool.exe", "klarify-feeder.exe", "flash.bat", "README.txt"}
SIM = ROOT / "build" / "sim_device.exe"


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    """Fresh extraction of the shipped zip: exactly what the friend gets."""
    assert ZIP.exists(), "run python tools/build_release.py first"
    out = tmp_path_factory.mktemp("kit")
    zipfile.ZipFile(ZIP).extractall(out)
    return out / "klarify-demo"


def test_zip_contains_everything_the_friend_needs():
    assert ZIP.exists(), "run python tools/build_release.py first"
    names = {n.split("/")[-1] for n in zipfile.ZipFile(ZIP).namelist()}
    assert NEEDED <= names, NEEDED - names
    assert any(n.endswith("python-fallback/feed.py") for n in zipfile.ZipFile(ZIP).namelist())


def test_packaged_feeder_selftest_and_script_against_sim(kit):
    exe = kit / "klarify-feeder.exe"
    assert exe.exists() and SIM.exists()
    r = subprocess.run([str(exe), "--sim", str(SIM), "--selftest"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and re.search(r"^OK klarify-fw", r.stdout, re.M), r.stdout + r.stderr
    r = subprocess.run([str(exe), "--sim", str(SIM), "--speed", "0", "--seed", "1", "--script", "background:3,cooker_whistle:8"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and re.search(r"^CLS cooker_whistle alert", r.stdout, re.M), r.stdout + r.stderr


def test_packaged_esptool_runs(kit):
    exe = kit / "esptool.exe"
    r = subprocess.run([str(exe), "version"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"\d+\.\d+", r.stdout + r.stderr)


def test_firmware_image_is_a_full_flash_image(kit):
    fw = kit / "firmware.bin"
    data = fw.read_bytes()
    assert 700_000 < len(data) < 4_194_304
    assert data[0x1000] == 0xE9  # ESP image magic at the bootloader offset
    assert data[0x10000] == 0xE9  # app image at 0x10000
