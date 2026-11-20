import json
import os
import re
import threading
import urllib.request
from pathlib import Path

import shutil
import subprocess
import urllib.error

import pytest

from embed_portal import embed, embed_all
from mock_portal_server import make_server

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "firmware" / "portal" / "index.html"
UPDATE_HTML = ROOT / "firmware" / "portal" / "update.html"
KEYS = {"input", "connected", "uptime_ms", "seq", "current", "history", "muted"}


def test_embed_writes_header_with_portal_markers(tmp_path):
    out = tmp_path / "portal.h"
    embed(HTML, out)
    text = out.read_text(encoding="utf-8")
    assert "PORTAL_HTML" in text and "PROGMEM" in text
    assert "Simulated input" in text
    assert "/api/state" in text


@pytest.mark.parametrize("page", [HTML, UPDATE_HTML])
def test_html_has_no_external_urls(page):
    assert not re.search(r"https?://|//cdn|@import", page.read_text(encoding="utf-8"))


def test_embed_all_has_both_pages(tmp_path):
    out = tmp_path / "portal.h"
    embed_all(out)
    text = out.read_text(encoding="utf-8")
    assert "PORTAL_HTML" in text and "UPDATE_HTML" in text
    assert "Install update" in text and "/update" in text


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


def _post_file(url, data: bytes, name="klarify-ota.bin"):
    boundary = "----klarifytest"
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode()
    body = head + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_mock_version_endpoint():
    srv, base = _serve()
    try:
        v = _get(base + "/api/version")
        assert set(v) == {"version"} and re.fullmatch(r"\d+\.\d+(\.\d+)?", v["version"])
    finally:
        srv.shutdown()


def test_mock_update_page_served():
    srv, base = _serve()
    try:
        page = urllib.request.urlopen(base + "/update", timeout=3).read().decode()
        assert "Install update" in page
    finally:
        srv.shutdown()


def test_mock_update_rejects_wrong_password():
    srv, base = _serve()
    try:
        code, body = _post_file(base + "/update?key=nope", b"\xe9" + b"\x00" * 100)
        assert code == 403 and body["ok"] is False
    finally:
        srv.shutdown()


def test_mock_update_rejects_full_usb_image_and_accepts_app_image():
    srv, base = _serve()
    try:
        code, body = _post_file(base + "/update?key=klarify", b"\xff" * 64)
        assert code == 500 and "agic" in body["error"]
        code, body = _post_file(base + "/update?key=klarify", b"\xe9" + b"\x00" * 100)
        assert code == 200 and body["ok"] is True
    finally:
        srv.shutdown()


@pytest.mark.skipif(not shutil.which("curl.exe") and not shutil.which("curl"), reason="curl not available")
def test_update_bat_flow_against_mock(tmp_path):
    srv, base = _serve()
    try:
        binf = tmp_path / "klarify-ota.bin"
        binf.write_bytes(b"\xe9" + b"\x00" * 200)
        bat = ROOT / "release" / "update.bat"
        env = dict(os.environ, KLARIFY_HOST=base.replace("http://", ""), KLARIFY_NOPAUSE="1")
        r = subprocess.run(["cmd", "/c", str(bat)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "Update installed" in r.stdout, r.stdout
        binf.write_bytes(b"\xff" * 200)
        r = subprocess.run(["cmd", "/c", str(bat)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
        assert r.returncode != 0 and "Update installed" not in r.stdout
    finally:
        srv.shutdown()
