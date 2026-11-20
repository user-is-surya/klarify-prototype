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
