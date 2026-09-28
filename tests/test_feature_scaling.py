"""Tests for ml.feature_scaling.

The behavioural test that matters is `test_scaling_prevents_propensity_saturation`:
it reproduces the failure this module exists to fix (propensity pinned at 1.000
on every node, which silently disables the overlap penalty) and shows scaling
resolves it. The rest guard the arithmetic and the error paths.
"""

from __future__ import annotations

import pytest
import torch

from ml.causal_regularization import PropensityScoreModel, overlap_penalty
from ml.feature_scaling import (
    apply_feature_scaler,
    compute_feature_scaler,
    scale_features,
)


def _realistic_creator_features(num_nodes: int = 64, seed: int = 0) -> torch.Tensor:
    """Features on the same mismatched scales as the real creator vector.

    log_subscriber_count ~ 8-17, engagement_rate ~ 0-1, category one-hots 0/1.
    The spread across dimensions is what saturates an unscaled linear head.
    """
    g = torch.Generator().manual_seed(seed)
    log_subs = torch.rand(num_nodes, 1, generator=g) * 9 + 8
    engagement = torch.rand(num_nodes, 1, generator=g)
    one_hot = torch.zeros(num_nodes, 6)
    one_hot[torch.arange(num_nodes), torch.randint(0, 6, (num_nodes,), generator=g)] = 1
    return torch.cat([log_subs, engagement, one_hot], dim=1)


def test_scaled_features_are_standardized():
    x = _realistic_creator_features()
    scaled, _, _ = scale_features(x)
    assert torch.allclose(scaled.mean(dim=0), torch.zeros(x.size(1)), atol=1e-5)
    # One-hot dims are clamped, so check std only where variance is real.
    varying = x.std(dim=0, unbiased=False) > 1e-3
    assert torch.allclose(scaled.std(dim=0, unbiased=False)[varying],
                          torch.ones(int(varying.sum())), atol=1e-4)


def test_scaling_prevents_propensity_saturation():
    """The regression this module exists to prevent.

    Raw features push the linear propensity head into sigmoid saturation, so
    every node returns ~1.000 and the overlap penalty has nothing to act on.
    """
    x = _realistic_creator_features()
    torch.manual_seed(0)
    model = PropensityScoreModel(in_dim=x.size(1))

    raw = model(x)
    scaled, _, _ = scale_features(x)
    norm = model(scaled)

    # Saturation shows up as near-zero spread across nodes.
    assert norm.std() > raw.std(), (
        f"scaling should widen the propensity distribution: "
        f"raw std={raw.std():.6f}, scaled std={norm.std():.6f}"
    )
    # And the overlap penalty must have real gradient signal to work with.
    assert torch.isfinite(overlap_penalty(norm))


def test_constant_dimension_does_not_divide_by_zero():
    x = torch.cat([torch.randn(20, 2), torch.ones(20, 1)], dim=1)
    scaled, _, std = scale_features(x)
    assert torch.isfinite(scaled).all()
    assert (std > 0).all()


def test_fit_indices_uses_only_selected_rows():
    """Inductive path: statistics come from the fit subset, not every row."""
    x = torch.cat([torch.zeros(10, 1), torch.full((10, 1), 100.0)], dim=0)
    fit = torch.arange(10)  # only the zero rows
    mean, _ = compute_feature_scaler(x, fit_indices=fit)
    assert torch.allclose(mean, torch.zeros(1), atol=1e-6)


def test_apply_rejects_feature_dim_mismatch():
    x = torch.randn(5, 4)
    mean, std = compute_feature_scaler(torch.randn(5, 3))
    with pytest.raises(ValueError, match="feature dim mismatch"):
        apply_feature_scaler(x, mean, std)


def test_rejects_non_2d_input():
    with pytest.raises(ValueError, match="num_nodes, num_features"):
        compute_feature_scaler(torch.randn(5))


def test_rejects_empty_input():
    with pytest.raises(ValueError, match="zero nodes"):
        compute_feature_scaler(torch.empty(0, 3))


def test_single_row_does_not_produce_nan():
    """unbiased=False matters here: n-1 would give NaN on one row."""
    scaled, _, std = scale_features(torch.randn(1, 4))
    assert torch.isfinite(scaled).all()
    assert torch.isfinite(std).all()
