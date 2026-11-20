"""Klarify feeder: generates synthetic sounds and streams them (raw 8 kHz PCM) to the ESP32 over USB serial.

  python tools/feed.py                      interactive: keys pick the sound (needs the board plugged in)
  python tools/feed.py --selftest           ping the board, print OK if it answers
  python tools/feed.py --script "doorbell:8,background:4"   scripted run (no keyboard)
  python tools/feed.py --sim sim_device.exe ...             talk to the PC simulator instead of a board
Keys: 0 background, 1 cooker whistle, 2 doorbell, 3 baby cry, 4 smoke alarm, 5 microwave beep,
      + / - noise level, a auto playlist, q quit.
"""
from __future__ import annotations

import argparse
import queue
import subprocess
import sys
import threading
import time

import numpy as np

from protocol import encode_pcm, encode_ping
from sounds import SAMPLE_RATE, SOUNDS, render

BLOCK = 400  # samples per frame (50 ms)
BAUD = 921600
NOISE_SNR_DB = [30, 20, 15, 10, 6, 3]
DEFAULT_NOISE_LEVEL = 2
HOLD_S = 10.0  # a key-triggered sound plays this long, then back to background
CHUNK_S = 10.0
KEYS = {"0": "background", "1": "cooker_whistle", "2": "doorbell", "3": "baby_cry", "4": "smoke_alarm", "5": "microwave_beep"}
AUTO_PLAYLIST = [(s, 8.0) if s != "background" else (s, 4.0) for s in ["background", "cooker_whistle", "background", "doorbell", "background",
                 "baby_cry", "background", "smoke_alarm", "background", "microwave_beep"]]


class SoundSource:
    """Endless synthetic audio for the currently selected sound, delivered in 400-sample blocks."""

    def __init__(self, seed: int | None = None, noise_level: int = DEFAULT_NOISE_LEVEL):
        self.rng = np.random.default_rng(seed)
        self.sound = "background"
        self.level = max(0, min(len(NOISE_SNR_DB) - 1, noise_level))
        self._buf = np.zeros(0, dtype=np.int16)

    @property
    def snr_db(self) -> int:
        return NOISE_SNR_DB[self.level]

    def set_sound(self, name: str) -> None:
        if name not in SOUNDS:
            raise ValueError(f"unknown sound {name!r}")
        if name != self.sound:
            self.sound = name
            self._buf = np.zeros(0, dtype=np.int16)

    def set_noise_level(self, level: int) -> None:
        level = max(0, min(len(NOISE_SNR_DB) - 1, int(level)))
        if level != self.level:
            self.level = level
            self._buf = np.zeros(0, dtype=np.int16)

    def next_block(self) -> np.ndarray:
        while len(self._buf) < BLOCK:
            self._buf = np.concatenate([self._buf, render(self.sound, CHUNK_S, self.snr_db, self.rng)])
        block, self._buf = self._buf[:BLOCK], self._buf[BLOCK:]
        return block


def parse_script(text: str) -> list[tuple[str, float]]:
    out = []
    for part in text.split(","):
        name, _, secs = part.strip().partition(":")
        if name not in SOUNDS:
            raise ValueError(f"unknown sound {name!r} in script (choose from {', '.join(SOUNDS)})")
        out.append((name, float(secs) if secs else 5.0))
    return out


def find_port() -> str | None:
    """First serial port that looks like a CP210x USB bridge, else None."""
    try:
        from serial.tools import list_ports
    except Exception:
        return None
    for p in list_ports.comports():
        desc = f"{p.description or ''} {p.hwid or ''}".upper()
        if "CP210" in desc or "10C4:EA60" in desc:
            return p.device
    return None


class Link:
    """A byte pipe to the device plus a queue of text lines coming back."""

    def __init__(self):
        self.lines: "queue.Queue[str]" = queue.Queue()
        self.alive = True

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class SimLink(Link):
    def __init__(self, exe: str):
        super().__init__()
        self.p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        self.t = threading.Thread(target=self._read, daemon=True)
        self.t.start()

    def _read(self):
        for raw in iter(self.p.stdout.readline, b""):
            self.lines.put(raw.decode("utf-8", "ignore").strip())

    def write(self, data: bytes) -> None:
        try:
            self.p.stdin.write(data)
        except (BrokenPipeError, OSError):
            self.alive = False

    def close(self) -> None:
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            self.p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.p.kill()
        self.t.join(timeout=5)


class SerialLink(Link):
    def __init__(self, port: str):
        super().__init__()
        import serial

        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = BAUD
        self.ser.timeout = 0.1
        self.ser.write_timeout = 2
        self.ser.dtr = False  # opening the port must not reset the board
        self.ser.rts = False
        self.ser.open()
        self._stop = False
        self.t = threading.Thread(target=self._read, daemon=True)
        self.t.start()

    def _read(self):
        buf = b""
        while not self._stop:
            try:
                data = self.ser.read(self.ser.in_waiting or 1)
            except Exception:
                self.alive = False
                return
            if not data:
                continue
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self.lines.put(line.decode("utf-8", "ignore").strip())  # boot garbage is expected: ignore errors

    def write(self, data: bytes) -> None:
        try:
            self.ser.write(data)
        except Exception:
            self.alive = False

    def close(self) -> None:
        self._stop = True
        self.t.join(timeout=2)
        try:
            self.ser.close()
        except Exception:
            pass


def drain(link: Link, echo: bool) -> str | None:
    """Take every pending device line; return the last CLS line. Echo to stdout when asked."""
    last = None
    while True:
        try:
            line = link.lines.get_nowait()
        except queue.Empty:
            return last
        if not line:
            continue
        if line.startswith(("CLS ", "PONG ")):
            last = line
            if echo:
                print(line, flush=True)


def selftest(link: Link) -> int:
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        link.write(encode_ping())
        t_end = time.monotonic() + 0.5
        while time.monotonic() < t_end:
            try:
                line = link.lines.get(timeout=0.1)
            except queue.Empty:
                continue
            if line.startswith("PONG "):
                print("OK " + line[5:], flush=True)
                return 0
    print("FAIL: the board did not answer. Check the USB cable, that klarify firmware is flashed, "
          "and that no other program (Arduino monitor) is using the port.", flush=True)
    return 1


def pace(next_t: float, period: float) -> float:
    if period > 0:
        next_t += period
        delay = next_t - time.monotonic()
        if delay > 0:
            time.sleep(delay)
    return next_t


def run_script(link: Link, source: SoundSource, segments, speed: float) -> int:
    period = 0.05 / speed if speed > 0 else 0.0
    seq, next_t = 0, time.monotonic()
    for name, secs in segments:
        source.set_sound(name)
        for _ in range(int(round(secs * SAMPLE_RATE / BLOCK))):
            link.write(encode_pcm(seq, source.next_block()))
            seq += 1
            next_t = pace(next_t, period)
            drain(link, echo=True)
    link.close()
    drain(link, echo=True)
    return 0


def interactive(link: Link, source: SoundSource, auto: bool) -> int:
    try:
        import msvcrt
    except ImportError:
        print("Interactive mode needs Windows; use --script instead.")
        return 2
    print(__doc__.split("Keys:")[1].strip().join(["Keys: ", ""]))
    seq, next_t = 0, time.monotonic()
    revert_at, last_cls, last_print = None, "-", 0.0
    auto_i, auto_until = 0, 0.0
    while True:
        now = time.monotonic()
        while msvcrt.kbhit():
            ch = msvcrt.getwch().lower()
            if ch == "q":
                link.close()
                print("\nbye")
                return 0
            if ch in KEYS:
                auto = False
                source.set_sound(KEYS[ch])
                revert_at = now + HOLD_S if ch != "0" else None
            elif ch in "+=":
                source.set_noise_level(source.level + 1)
            elif ch in "-_":
                source.set_noise_level(source.level - 1)
            elif ch == "a":
                auto = not auto
                auto_until = 0.0
        if auto and now >= auto_until:
            name, secs = AUTO_PLAYLIST[auto_i % len(AUTO_PLAYLIST)]
            source.set_sound(name)
            auto_i += 1
            auto_until = now + secs
        elif not auto and revert_at and now >= revert_at:
            source.set_sound("background")
            revert_at = None
        link.write(encode_pcm(seq, source.next_block()))
        seq += 1
        next_t = pace(next_t, 0.05)
        got = drain(link, echo=False)
        if got:
            last_cls = got
        if not link.alive:
            print("\nLost the connection to the board (cable unplugged?).")
            return 1
        if now - last_print > 0.25:
            last_print = now
            msg = (f"\r[{source.sound:14s}] noise {source.level} ({source.snr_db:2d} dB){' AUTO' if auto else '     '} | "
                   f"device: {last_cls}")
            print(msg.ljust(100)[:100], end="", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Klarify synthetic sound feeder")
    ap.add_argument("--port", help="serial port, e.g. COM5 (default: auto-detect a CP210x board)")
    ap.add_argument("--sim", help="path to sim_device.exe: talk to the PC simulator instead of a board")
    ap.add_argument("--selftest", action="store_true", help="ping the device and exit")
    ap.add_argument("--script", help='scripted run, e.g. "doorbell:8,background:4"')
    ap.add_argument("--speed", type=float, default=1.0, help="1 = real time, 0 = as fast as possible (tests)")
    ap.add_argument("--auto", action="store_true", help="start with the auto playlist running")
    ap.add_argument("--noise-level", type=int, default=DEFAULT_NOISE_LEVEL, help="0 (quiet) .. 5 (very noisy)")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args(argv)

    if a.sim:
        link: Link = SimLink(a.sim)
    else:
        port = a.port or find_port()
        if not port:
            print("No ESP32 found. Plug the board in with a data USB cable (and check the CP210x driver), "
                  "or pass --port COMx.")
            return 2
        try:
            link = SerialLink(port)
        except Exception as e:
            print(f"Could not open {port}: {e}\nClose any other program using it (Arduino serial monitor).")
            return 2
        print(f"Connected to {port}")

    source = SoundSource(seed=a.seed, noise_level=a.noise_level)
    try:
        if a.selftest:
            rc = selftest(link)
            link.close()
            return rc
        if a.script:
            return run_script(link, source, parse_script(a.script), a.speed)
        return interactive(link, source, a.auto)
    except KeyboardInterrupt:
        link.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
