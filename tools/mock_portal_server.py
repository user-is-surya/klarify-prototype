"""Serves the portal with a scripted fake /api/state so the UI can be developed and shown without the board.
It also fakes /api/version and the OTA endpoint (/update) the same way the firmware answers them.
Run: python tools/mock_portal_server.py [--port 8080]

Preview helpers (mock only, the firmware has no such routes):
  POST /mock/fire?sound=smoke_alarm&hold=600000   show an alert that stays for `hold` ms
  POST /mock/clear                                 clear the current alert and the history
  POST /mock/idle?on=1                             report "connected": false (feeder not running)"""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sounds import LEVELS, SOUNDS

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "firmware" / "portal" / "index.html"
UPDATE_HTML = ROOT / "firmware" / "portal" / "update.html"
VERSION = "1.2"
OTA_KEY = "klarify"
LABELS = {
    "cooker_whistle": "Cooker whistle", "doorbell": "Doorbell", "baby_cry": "Baby crying",
    "smoke_alarm": "Smoke alarm", "microwave_beep": "Microwave beep",
}
SCRIPT = ["cooker_whistle", "doorbell", "baby_cry", "smoke_alarm", "microwave_beep"]


class MockState:
    def __init__(self, auto: bool = True):
        self.t0 = time.monotonic()
        self.lock = threading.Lock()
        self.seq = 0
        self.cur = None  # (sound, t_ms, hold_ms)
        self.history: list[dict] = []
        self.muted: set[str] = set()
        self.connected = True
        self.auto = auto
        self.i = 0

    def now_ms(self) -> int:
        return int((time.monotonic() - self.t0) * 1000)

    def fire(self, sound: str, hold_ms: int = 6000) -> None:
        with self.lock:
            t = self.now_ms()
            is_muted = sound in self.muted
            if not is_muted:
                self.seq += 1
                self.cur = (sound, t, hold_ms)
            self.history.insert(0, {"t_ms": t, "sound": sound, "level": LEVELS[sound], "muted": is_muted})
            del self.history[20:]

    def clear(self) -> None:
        with self.lock:
            self.cur = None
            self.history = []

    def snapshot(self) -> dict:
        with self.lock:
            now = self.now_ms()
            cur = None
            if self.cur and now - self.cur[1] < self.cur[2]:
                s, t, _ = self.cur
                cur = {"sound": s, "label": LABELS[s], "level": LEVELS[s], "age_ms": now - t}
            return {
                "input": "synthetic", "connected": self.connected, "uptime_ms": now, "seq": self.seq,
                "current": cur, "history": list(self.history),
                "muted": [s for s in SOUNDS[1:] if s in self.muted],
            }

    def set_muted(self, sound: str, on: bool) -> None:
        with self.lock:
            (self.muted.add if on else self.muted.discard)(sound)


def _file_part(body: bytes) -> bytes | None:
    """Bytes of the first multipart file part (after the blank line that ends its headers)."""
    sep = bytes([13, 10, 13, 10])
    i = body.find(sep)
    return None if i < 0 else body[i + 4:]


def make_server(port: int = 0, auto: bool = False) -> ThreadingHTTPServer:
    state = MockState(auto)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj).encode())

        def do_GET(self):
            p = urlparse(self.path).path
            if p == "/":
                self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            elif p == "/update":
                self._send(200, UPDATE_HTML.read_bytes(), "text/html; charset=utf-8")
            elif p == "/api/state":
                self._json(200, state.snapshot())
            elif p == "/api/version":
                self._json(200, {"version": VERSION})
            else:
                self._json(404, {})

        def do_POST(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/api/mute":
                s = q.get("sound", [""])[0]
                if s in SOUNDS[1:]:
                    state.set_muted(s, q.get("on", ["0"])[0] == "1")
                    return self._json(200, {"ok": True})
                return self._json(400, {"ok": False})
            if u.path == "/update":  # behaves like the firmware: password first, then image check
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                if q.get("key", [""])[0] != OTA_KEY:
                    return self._json(403, {"ok": False, "error": "Wrong password"})
                data = _file_part(body)
                if not data:
                    return self._json(500, {"ok": False, "error": "No file received"})
                if data[0] != 0xE9:
                    return self._json(500, {"ok": False, "error": "Magic byte is wrong, not 0xE9"})
                return self._json(200, {"ok": True})
            if u.path == "/mock/fire":
                s = q.get("sound", [""])[0]
                if s in SOUNDS[1:]:
                    state.fire(s, int(q.get("hold", ["6000"])[0]))
                    return self._json(200, {"ok": True})
            if u.path == "/mock/clear":
                state.clear()
                return self._json(200, {"ok": True})
            if u.path == "/mock/idle":
                state.connected = q.get("on", ["0"])[0] != "1"
                return self._json(200, {"ok": True})
            self._json(400, {"ok": False})

    srv = ThreadingHTTPServer(("127.0.0.1" if port == 0 else "0.0.0.0", port), H)
    srv.state = state  # type: ignore[attr-defined]
    if auto:
        def loop():
            time.sleep(1.5)
            while True:
                state.fire(SCRIPT[state.i % len(SCRIPT)])
                state.i += 1
                time.sleep(7)
        threading.Thread(target=loop, daemon=True).start()
    return srv


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--no-auto", action="store_true", help="do not cycle through sounds by itself")
    a = ap.parse_args()
    srv = make_server(a.port, auto=not a.no_auto)
    print(f"Mock portal on http://localhost:{a.port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
