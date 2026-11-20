import numpy as np

from sounds import SOUNDS
from train import train


def test_train_meets_accuracy_on_synthetic(tmp_path):
    r = train(tmp_path / "model.h", seed=0, n_per_class=300)
    assert r.metrics["accuracy"] >= 0.90
    for name in SOUNDS:
        assert r.metrics["recall"][name] >= 0.80, (name, r.metrics["recall"])


def test_header_written_and_contains_model_predict(tmp_path):
    out = tmp_path / "model.h"
    train(out, seed=0, n_per_class=100)
    text = out.read_text()
    assert "model_predict" in text
    assert "static inline int model_predict(const float* f)" in text


def test_training_is_deterministic_for_seed(tmp_path):
    a = tmp_path / "a.h"
    b = tmp_path / "b.h"
    train(a, seed=3, n_per_class=100)
    train(b, seed=3, n_per_class=100)
    assert a.read_text() == b.read_text()
