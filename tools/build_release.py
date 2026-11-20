"""Builds dist/klarify-demo/ and dist/klarify-demo.zip for the friend's Windows laptop.
Run from the project root with the project venv:  .venv\\Scripts\\python tools\\build_release.py"""
from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)
SCRIPTS = PY.parent
DIST = ROOT / "dist"
OUT = DIST / "klarify-demo"
WORK = ROOT / "build" / "pyinstaller"
PIO_BUILD = ROOT / "firmware" / ".pio" / "build" / "esp32dev"


def sh(*cmd, **kw):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def find_boot_app0() -> Path:
    hits = list((Path.home() / ".platformio" / "packages").glob("framework-arduinoespressif32*/tools/partitions/boot_app0.bin"))
    if not hits:
        raise FileNotFoundError("boot_app0.bin not found under ~/.platformio/packages")
    return hits[0]


def pyinstaller(name: str, script: Path, *extra: str) -> Path:
    sh(PY, "-m", "PyInstaller", "--onefile", "--noconfirm", "--clean", "--name", name,
       "--distpath", WORK / "out", "--workpath", WORK / name, "--specpath", WORK, "--paths", ROOT / "tools", *extra, script)
    return WORK / "out" / f"{name}.exe"


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    sh(PY, ROOT / "tools" / "embed_portal.py")
    sh(SCRIPTS / "pio.exe", "run", "-d", ROOT / "firmware")
    sh(PY, "-m", "esptool", "--chip", "esp32", "merge-bin", "-o", OUT / "firmware.bin",
       "--flash-mode", "dio", "--flash-size", "4MB",
       "0x1000", PIO_BUILD / "bootloader.bin", "0x8000", PIO_BUILD / "partitions.bin",
       "0xe000", find_boot_app0(), "0x10000", PIO_BUILD / "firmware.bin")

    feeder = pyinstaller("klarify-feeder", ROOT / "tools" / "feed.py", "--exclude-module", "sklearn",
                         "--hidden-import", "serial.tools.list_ports_windows")
    shutil.copy2(feeder, OUT / "klarify-feeder.exe")
    esp = pyinstaller("esptool", ROOT / "tools" / "_esptool_launcher.py", "--collect-all", "esptool")
    shutil.copy2(esp, OUT / "esptool.exe")

    shutil.copy2(ROOT / "release" / "flash.bat", OUT / "flash.bat")
    shutil.copy2(ROOT / "release" / "README.txt", OUT / "README.txt")
    fb = OUT / "python-fallback"
    fb.mkdir()
    for f in ("feed.py", "sounds.py", "protocol.py"):
        shutil.copy2(ROOT / "tools" / f, fb / f)

    zip_path = DIST / "klarify-demo.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, Path("klarify-demo") / p.relative_to(OUT))
    print(f"\nBuilt {zip_path} ({zip_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
