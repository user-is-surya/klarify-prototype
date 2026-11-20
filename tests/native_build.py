"""Helpers to compile and run the header-only C++ core natively with g++."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_INCLUDE = ROOT / "firmware" / "include"


def gxx() -> str:
    found = shutil.which("g++")
    if found:
        return found
    fallback = Path(r"C:\msys64\ucrt64\bin\g++.exe")
    if fallback.exists():
        return str(fallback)
    raise RuntimeError("g++ not found")


def build(cpp: Path, exe: Path, include_dirs: list[Path] | None = None) -> Path:
    """Compile cpp -> exe. include_dirs are searched before firmware/include (e.g. a temp model.h)."""
    exe.parent.mkdir(parents=True, exist_ok=True)
    incs = [f"-I{d}" for d in (include_dirs or [])] + [f"-I{CORE_INCLUDE}"]
    cmd = [gxx(), "-std=c++17", "-O1", "-Wall", "-Wextra", *incs, str(cpp), "-o", str(exe)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"compile failed:\n{r.stderr}\n{r.stdout}")
    return exe


def run(exe: Path, *args: str, input: bytes | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([str(exe), *args], input=input, capture_output=True, timeout=timeout)
