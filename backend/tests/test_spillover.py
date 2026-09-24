"""A1/A2: spillover must resolve to canonical ml/ and never crash.

- When ml/inference imports, the served loader must BE ml.inference
  (guards against re-vendoring model code under backend/app).
- When ml is missing (backend-only deploy, no torch), get_spillover and
  get_spillover_batch fall back to placeholder/isolated instead of raising.
"""

import importlib
import sys

import pytest

import app.spillover as sp


def test_served_loader_is_canonical_ml():
    if not sp.is_gail_available():
        pytest.skip("torch/ml unavailable here; fallback path covered below")
    assert sp._load_predict.__module__ == "ml.inference"
    assert "app.gail" not in sys.modules


def test_placeholder_when_ml_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "ml", None)
    monkeypatch.setitem(sys.modules, "ml.inference", None)
    mod = importlib.reload(sp)
    try:
        assert mod.is_gail_available() is False
        assert mod.gail_unavailable_reason() is not None
        cid = "00000000-0000-0000-0000-000000000000"
        res = mod.get_spillover(cid)
        assert res["creator_id"] == cid
        assert res["basis"] == "placeholder"
        assert res["spillover_score"] == 0.5
        batch = mod.get_spillover_batch([cid, cid])
        assert set(batch) == {cid}
        assert all(v["basis"] == "placeholder" for v in batch.values())
        assert mod.get_spillover_batch([]) == {}
    finally:
        monkeypatch.undo()
        importlib.reload(sp)
