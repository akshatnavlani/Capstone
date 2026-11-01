import pytest
import torch

pytest.importorskip("ml.gail_r")  # Eesha's GAIL-R arrives with the merge-eesha-ml branch

from ml.gail_r import Observations
from ml.gail_r_ext import drop_labels, fit_gail_r_supervised, simex_gail_r
from ml.semi_synthetic import EFFECT, fake_graph, make_world


def _obs(world):
    n = len(world.y)
    return Observations(torch.arange(n), torch.zeros(n, dtype=torch.long), world.y, world.y_pre)


def test_drop_labels_only_removes_ones():
    t = torch.tensor([1.0, 0.0, 1.0, 1.0, 0.0] * 200)
    out = drop_labels([t], 0.5, torch.Generator().manual_seed(0))[0]
    assert (out[t == 0] == 0).all()
    assert 0.4 < out[t == 1].mean() < 0.6
    assert (drop_labels([t], 1.0, torch.Generator().manual_seed(0))[0] == t).all()


def test_supervision_switch_runs_and_validates():
    world = make_world(fake_graph(), "clean", seed=0)
    for mode in ("causal", "plain"):
        out = fit_gail_r_supervised(world.data, [world.treatment], _obs(world), supervision=mode, placebo_weight=0.0, epochs=40)
        assert set(out["slopes"]) == {"collaborates_with", "co_occurs_with"}
    with pytest.raises(ValueError):
        fit_gail_r_supervised(world.data, [world.treatment], _obs(world), supervision="other")


def test_simex_recall_one_changes_nothing():
    world = make_world(fake_graph(), "clean", seed=0)
    out = simex_gail_r(world.data, [world.treatment], _obs(world), recall=1.0, draws=2, epochs=60)
    assert out["corrected"]["ate"] == pytest.approx(out["naive"]["ate"], abs=1e-3)


def test_simex_moves_estimate_away_from_zero_when_labels_are_missed():
    world = make_world(fake_graph(), "clean", seed=0)
    keep = 0.7
    seen = drop_labels([world.treatment], keep, torch.Generator().manual_seed(5))
    out = simex_gail_r(world.data, seen, _obs(world), recall=keep, draws=4, epochs=100, placebo_weight=0.0)
    assert abs(out["corrected"]["ate"]) > abs(out["naive"]["ate"])
    assert abs(out["corrected"]["ate"] - world.true_ate) < abs(out["naive"]["ate"] - world.true_ate)
