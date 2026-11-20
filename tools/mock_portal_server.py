"""Serves the portal with a scripted fake /api/state so the UI can be developed and shown without the board.
Run: python tools/mock_portal_server.py [--port 8080]"""
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
        self.cur = None  # (sound, t_ms)
        self.history: list[dict] = []
        self.muted: set[str] = set()
        self.auto = auto
        self.i = 0

    def now_ms(self) -> int:
        return int((time.monotonic() - self.t0) * 1000)

    def fire(self, sound: str) -> None:
        with self.lock:
            t = self.now_ms()
            is_muted = sound in self.muted
            if not is_muted:
                self.seq += 1
                self.cur = (sound, t)
            self.history.insert(0, {"t_ms": t, "sound": sound, "level": LEVELS[sound], "muted": is_muted})
            del self.history[20:]

    def snapshot(self) -> dict:
        with self.lock:
            now = self.now_ms()
            cur = None
            if self.cur and now - self.cur[1] < 6000:
                s, t = self.cur
                cur = {"sound": s, "label": LABELS[s], "level": LEVELS[s], "age_ms": now - t}
            return {
                "input": "synthetic", "connected": True, "uptime_ms": now, "seq": self.seq,
                "current": cur, "history": list(self.history),
                "muted": [s for s in SOUNDS[1:] if s in self.muted],
            }

    def set_muted(self, sound: str, on: bool) -> None:
        with self.lock:
            (self.muted.add if on else self.muted.discard)(sound)


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

        def do_GET(self):
            p = urlparse(self.path).path
            if p == "/":
                self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            elif p == "/api/state":
                self._send(200, json.dumps(state.snapshot()).encode())
            else:
                self._send(404, b"{}")

        def do_POST(self):
            u = urlparse(self.path)
            if u.path == "/api/mute":
                q = parse_qs(u.query)
                s = q.get("sound", [""])[0]
                if s in SOUNDS[1:]:
                    state.set_muted(s, q.get("on", ["0"])[0] == "1")
                    return self._send(200, b'{"ok":true}')
            self._send(400, b'{"ok":false}')

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
    a = ap.parse_args()
    srv = make_server(a.port, auto=True)
    print(f"Mock portal on http://localhost:{a.port}  (cycles through every sound every 7 s; Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
