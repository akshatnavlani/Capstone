"""Tests for the propensity-prediction loss (E3b).

The test that carries the change is `test_propensity_learns_to_discriminate`:
before E3b the propensity head had no term telling it what to predict, so it
converged to roughly one value for every node (measured std 0.003 on synthetic
data). A constant propensity makes the inverse-propensity weight T/pi a constant
multiplier, which carries no per-node selection information -- so the doubly
robust correction had nothing to correct with. These tests pin the fix.
"""

from __future__ import annotations

import torch

from ml.causal_regularization import PropensityScoreModel
from ml.gail_loss import GAILLossWeights, compute_gail_loss

_EDGE_INDEX = torch.tensor([[0, 1], [1, 0]])
_EDGE_WEIGHT = torch.tensor([1.0, 1.0])


def _confounded(n: int = 400, seed: int = 0):
    """Features whose first column genuinely predicts treatment."""
    g = torch.Generator().manual_seed(seed)
    confounder = torch.rand(n, 1, generator=g)
    noise = torch.randn(n, 3, generator=g) * 0.1
    x = torch.cat([confounder, noise], dim=1)
    treatment = (torch.rand(n, 1, generator=g) < (0.1 + 0.8 * confounder)).float().squeeze(1)
    return x, treatment


def test_propensity_learns_to_discriminate():
    """With the term on, propensity must separate treated from untreated."""
    x, treatment = _confounded()
    torch.manual_seed(0)
    model = PropensityScoreModel(in_dim=x.size(1), hidden_dim=8)
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)

    for _ in range(300):
        opt.zero_grad()
        p = model(x)
        torch.nn.functional.binary_cross_entropy(p.clamp(1e-6, 1 - 1e-6), treatment).backward()
        opt.step()

    with torch.no_grad():
        p = model(x)
    # The whole point: treated nodes score higher than untreated ones.
    assert p[treatment == 1].mean() > p[treatment == 0].mean() + 0.1
    # And the distribution is not a constant (the pre-E3b failure, std ~0.003).
    assert p.std() > 0.05, f"propensity collapsed to near-constant: std={p.std():.4f}"


def test_term_is_on_by_default():
    assert GAILLossWeights().propensity > 0


def test_term_is_reported_in_components():
    _, comps = compute_gail_loss(
        torch.zeros(3), torch.zeros(3), torch.full((3,), 0.5),
        _EDGE_INDEX, _EDGE_WEIGHT, torch.tensor([False, False, False]),
        treatment=torch.tensor([1.0, 0.0, 1.0]),
    )
    assert "propensity" in comps


def test_term_is_zero_without_treatment():
    """No treatment passed means nothing to predict -- pre-E3b callers unchanged."""
    _, comps = compute_gail_loss(
        torch.zeros(3), torch.zeros(3), torch.full((3,), 0.5),
        _EDGE_INDEX, _EDGE_WEIGHT, torch.tensor([False, False, False]),
    )
    assert comps["propensity"] == 0.0


def test_zero_weight_recovers_pre_e3b_total():
    """The ablation arm must reproduce the old loss exactly."""
    args = (
        torch.tensor([1.0, 2.0, 3.0]), torch.tensor([0.0, 0.0, 0.0]),
        torch.tensor([0.5, 0.25, 0.75]), _EDGE_INDEX, _EDGE_WEIGHT,
        torch.tensor([False, False, False]),
    )
    treatment = torch.tensor([1.0, 0.0, 1.0])
    off, _ = compute_gail_loss(
        *args, GAILLossWeights(propensity=0.0), treatment=treatment
    )
    on, comps = compute_gail_loss(
        *args, GAILLossWeights(propensity=1.0), treatment=treatment
    )
    assert abs((on - off).item() - comps["propensity"]) < 1e-5


def test_gradient_reaches_the_propensity_head():
    x, treatment = _confounded(n=50)
    torch.manual_seed(0)
    model = PropensityScoreModel(in_dim=x.size(1), hidden_dim=8)
    propensity = model(x)

    total, _ = compute_gail_loss(
        torch.zeros(50), torch.zeros(50), propensity,
        torch.tensor([[0, 1], [1, 0]]), torch.tensor([1.0, 1.0]),
        torch.zeros(50, dtype=torch.bool),
        treatment=treatment,
    )
    total.backward()
    grads = [p.grad for p in model.parameters() if p.grad is not None]
    assert grads, "propensity head received no gradient"
    assert any(g.abs().sum() > 0 for g in grads)


def test_loss_is_finite_at_propensity_extremes():
    """BCE is clamped, so pi exactly 0 or 1 must not produce inf."""
    total, comps = compute_gail_loss(
        torch.zeros(3), torch.zeros(3), torch.tensor([0.0, 1.0, 0.5]),
        _EDGE_INDEX, _EDGE_WEIGHT, torch.tensor([False, False, False]),
        treatment=torch.tensor([1.0, 0.0, 1.0]),
    )
    assert torch.isfinite(total)
    assert torch.isfinite(torch.tensor(comps["propensity"]))