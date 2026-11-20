import json
import re
import threading
import urllib.request
from pathlib import Path

from embed_portal import embed
from mock_portal_server import make_server

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "firmware" / "portal" / "index.html"
KEYS = {"input", "connected", "uptime_ms", "seq", "current", "history", "muted"}


def test_embed_writes_header_with_portal_markers(tmp_path):
    out = tmp_path / "portal.h"
    embed(HTML, out)
    text = out.read_text(encoding="utf-8")
    assert "PORTAL_HTML" in text and "PROGMEM" in text
    assert "Simulated input" in text
    assert "/api/state" in text


def test_html_has_no_external_urls():
    assert not re.search(r"https?://|//cdn|@import", HTML.read_text(encoding="utf-8"))


def _serve():
    srv = make_server(port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _get(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.loads(r.read())


def test_mock_state_matches_schema():
    srv, base = _serve()
    try:
        st = _get(base + "/api/state")
        assert set(st) == KEYS
        assert st["input"] == "synthetic"
        assert isinstance(st["history"], list) and isinstance(st["muted"], list)
        page = urllib.request.urlopen(base + "/", timeout=3).read().decode()
        assert "Klarify" in page
    finally:
        srv.shutdown()


def test_mock_mute_roundtrip():
    srv, base = _serve()
    try:
        req = urllib.request.Request(base + "/api/mute?sound=doorbell&on=1", method="POST")
        urllib.request.urlopen(req, timeout=3).read()
        assert "doorbell" in _get(base + "/api/state")["muted"]
        req = urllib.request.Request(base + "/api/mute?sound=doorbell&on=0", method="POST")
        urllib.request.urlopen(req, timeout=3).read()
        assert "doorbell" not in _get(base + "/api/state")["muted"]
    finally:
        srv.shutdown()
