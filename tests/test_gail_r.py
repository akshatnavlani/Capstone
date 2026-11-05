import torch

from ml.gail_r import Observations, cluster_bootstrap, fit_gail_r, oof_ridge, uniform_share
from ml.semi_synthetic import EFFECT, fake_graph, make_world


def test_oof_ridge_never_uses_own_group():
    # Each group's target is a unique constant; a model that saw the group would
    # predict it exactly, an out-of-group model cannot.
    groups = torch.arange(20).repeat_interleave(3)
    X = torch.nn.functional.one_hot(groups).float()
    Y = groups.float() * 10
    pred = oof_ridge(X, Y, groups, k=5, lam=1e-6)
    assert (pred - Y).abs().min() > 1.0


def test_uniform_share():
    ei = torch.tensor([[0, 1, 2], [3, 3, 3]])
    t = torch.tensor([1.0, 0.0, 1.0, 0.0])
    s = uniform_share(ei, t, 4)
    assert torch.allclose(s, torch.tensor([0.0, 0.0, 0.0, 2 / 3]))


def _obs(world):
    n = len(world.y)
    return Observations(torch.arange(n), torch.zeros(n, dtype=torch.long), world.y, world.y_pre)


def test_recovers_collab_slope_and_zero_comention():
    world = make_world(fake_graph(), "clean", seed=0)
    out = fit_gail_r(world.data, [world.treatment], _obs(world), placebo_weight=0.0)
    assert abs(out["slopes"]["collaborates_with"] - EFFECT) < 0.3
    assert abs(out["slopes"]["co_occurs_with"]) < 0.3
    assert abs(out["ate"] - world.true_ate) < 0.1


def test_placebo_penalty_removes_pretrend_bias():
    world = make_world(fake_graph(), "pretrend", seed=0)
    off = fit_gail_r(world.data, [world.treatment], _obs(world), placebo_weight=0.0, uniform=True)
    on = fit_gail_r(world.data, [world.treatment], _obs(world), placebo_weight=30.0, uniform=True)
    assert abs(on["ate"] - world.true_ate) < 0.5 * abs(off["ate"] - world.true_ate)


def test_cluster_bootstrap_interval_contains_estimate():
    world = make_world(fake_graph(), "clean", seed=1)
    obs = _obs(world)
    est = fit_gail_r(world.data, [world.treatment], obs, uniform=True)["ate"]
    ci = cluster_bootstrap(world.data, [world.treatment], obs, B=20)
    assert ci["lo"] <= est <= ci["hi"]


def test_own_sponsorship_input_removes_its_confounding():
    # No spillover at all. Creators who ran their own sponsorship gain +1, and own
    # sponsorship is far more common among exposed creators, so ignoring it reads
    # the gain as spillover; giving it to the nuisance models removes the bias.
    world = make_world(fake_graph(), "clean", seed=0)
    n = len(world.y)
    g = torch.Generator().manual_seed(0)
    u = uniform_share(world.data["creator", "collaborates_with", "creator"].edge_index, world.treatment, n)
    own = (torch.rand(n, generator=g) < torch.where(u > 0, 0.8, 0.1)).float()
    y = own + 0.1 * torch.randn(n, generator=g)
    base = Observations(torch.arange(n), torch.zeros(n, dtype=torch.long), y, torch.full((n,), float("nan")))
    adj = Observations(base.node, base.window, base.y, base.pre, own)
    off = fit_gail_r(world.data, [world.treatment], base, placebo_weight=0.0, uniform=True)
    on = fit_gail_r(world.data, [world.treatment], adj, placebo_weight=0.0, uniform=True)
    assert off["slopes"]["collaborates_with"] > 0.3
    assert abs(on["slopes"]["collaborates_with"]) < 0.1
    assert adj.subset(torch.tensor([0, 2])).own.tolist() == own[[0, 2]].tolist()
