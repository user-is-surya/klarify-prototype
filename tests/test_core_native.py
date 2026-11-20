from pathlib import Path

from native_build import ROOT, build, run
from native_fixtures import write_feature_fixtures, write_protocol_stream

NATIVE = ROOT / "tests" / "native"


def test_features_and_model_parity(tmp_path):
    fixtures = tmp_path / "fx"
    write_feature_fixtures(fixtures, n=60, seed=1)
    exe = build(NATIVE / "test_features_model.cpp", tmp_path / "t_feat.exe", include_dirs=[fixtures])
    r = run(exe, str(fixtures))
    assert r.returncode == 0, r.stdout.decode() + r.stderr.decode()


def test_protocol_alert_pipeline(tmp_path):
    stream = tmp_path / "stream.bin"
    write_protocol_stream(stream)
    exe = build(NATIVE / "test_protocol_alert_pipeline.cpp", tmp_path / "t_pap.exe")
    r = run(exe, str(stream))
    assert r.returncode == 0, r.stdout.decode() + r.stderr.decode()


def test_state_and_led(tmp_path):
    exe = build(NATIVE / "test_state_led.cpp", tmp_path / "t_state.exe")
    r = run(exe)
    assert r.returncode == 0, r.stdout.decode() + r.stderr.decode()
