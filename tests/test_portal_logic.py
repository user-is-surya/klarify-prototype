import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

HTML = Path(__file__).resolve().parents[1] / "firmware" / "portal" / "index.html"


def hero_mode(state, fails):
    """Runs the portal's real heroMode() function under node."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    m = re.search(r"// BEGIN heroMode\n(.*?)// END heroMode", HTML.read_text(encoding="utf-8"), re.S)
    assert m, "heroMode block missing from portal"
    script = m.group(1) + "\nconsole.log(JSON.stringify(heroMode(%s, %d)));" % (json.dumps(state), fails)
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


ALERT = {"current": {"sound": "smoke_alarm", "level": "urgent"}, "connected": True}
QUIET = {"current": None, "connected": True}


def test_before_first_state_is_idle_not_lost():
    assert hero_mode(None, 0) == "idle"


def test_alert_shown_while_polls_succeed():
    assert hero_mode(ALERT, 0) == "alert"
    assert hero_mode(ALERT, 1) == "alert"


def test_alert_not_frozen_when_device_unreachable():
    assert hero_mode(ALERT, 2) == "lost"
    assert hero_mode(ALERT, 9) == "lost"


def test_quiet_state_is_idle():
    assert hero_mode(QUIET, 0) == "idle"


UPDATE = HTML.parent / "update.html"


def describe(status, text):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    m = re.search(r"// BEGIN describeResult\n(.*?)// END describeResult", UPDATE.read_text(encoding="utf-8"), re.S)
    assert m, "describeResult block missing from update page"
    script = m.group(1) + "\nconsole.log(JSON.stringify(describeResult(%d, %s)));" % (status, json.dumps(text))
    r = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_describe_success():
    assert describe(200, '{"ok":true}')["ok"] is True


def test_describe_network_failure_mentions_wifi():
    d = describe(0, "")
    assert d["ok"] is False and "Wi-Fi" in d["msg"]


def test_describe_wrong_password():
    d = describe(403, '{"ok":false,"error":"Wrong password"}')
    assert d == {"ok": False, "msg": "Wrong password."}


def test_describe_wrong_file_points_to_ota_bin():
    d = describe(500, '{"ok":false,"error":"Magic byte is wrong, not 0xE9"}')
    assert d["ok"] is False and "klarify-ota.bin" in d["msg"]


def test_describe_unknown_failure_includes_http_status():
    assert "HTTP 502" in describe(502, "")["msg"]
