"""Smoke test of the packaged release (run after: python tools/build_release.py)."""
import re
import subprocess
import zipfile

import pytest

from native_build import ROOT

DIST = ROOT / "dist"
ZIP = DIST / "klarify-demo.zip"
NEEDED = {"firmware.bin", "klarify-ota.bin", "esptool.exe", "klarify-feeder.exe", "flash.bat", "update.bat", "README.txt"}
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


def test_ota_image_and_partition_table_are_ota_ready(kit):
    import struct

    full = (kit / "firmware.bin").read_bytes()
    ota = (kit / "klarify-ota.bin").read_bytes()
    assert ota[0] == 0xE9, "OTA image must be an app image (starts with 0xE9), not the full USB image"
    assert full[0] != 0xE9 and full[0x10000:0x10000 + len(ota)] == ota, "USB image must contain the same app at 0x10000"
    ents = []
    for i in range(0, 0xC00, 32):
        e = full[0x8000 + i:0x8000 + i + 32]
        if e[:2] != b"\xaa\x50":
            break
        t, st = e[2], e[3]
        off, size = struct.unpack("<II", e[4:12])
        ents.append((t, st, off, size))
    ota_slots = [e for e in ents if e[0] == 0x00 and e[1] in (0x10, 0x11)]
    assert {e[1] for e in ota_slots} == {0x10, 0x11}, ents
    assert any(e[0] == 0x01 and e[1] == 0x00 for e in ents), "otadata partition missing"
    assert all(len(ota) < e[3] for e in ota_slots), "app does not fit an OTA slot"
