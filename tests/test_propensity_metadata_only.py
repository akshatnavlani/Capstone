"""Metadata-only propensity head (fix for 0/1 saturation, 2026-10-26 run).

The full-feature head (1289-d input, hidden layer) can separate a few hundred
creators perfectly, so its propensities collapse to 0 and 1 and the overlap
assumption fails. `propensity_metadata_only=True` fits a logistic regression on
the creator metadata tail instead.
"""

from __future__ import annotations

import torch

from ml.causal_regularization import PropensityScoreModel
from ml.dummy_data import make_dummy_hetero_data
from ml.gail_model import GAILModel
from ml.schema import CREATOR_FEATURE_DIM, CREATOR_METADATA_DIM


def test_default_head_is_unchanged():
    """Old checkpoints load into the default model, so its head must not change."""
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM)
    first = model.propensity_model.net[0]
    assert first.in_features == CREATOR_FEATURE_DIM


def test_metadata_head_reads_only_the_metadata_tail():
    data = make_dummy_hetero_data()
    n = data["creator"].x.size(0)
    model = GAILModel(creator_feature_dim=data["creator"].x.size(1), propensity_metadata_only=True)
    model.eval()
    t = torch.zeros(n)
    with torch.no_grad():
        _, _, p0 = model(data, t)
        # Scramble the embedding columns: propensity must not move.
        data["creator"].x[:, :-CREATOR_METADATA_DIM] = torch.randn(n, data["creator"].x.size(1) - CREATOR_METADATA_DIM)
        _, _, p1 = model(data, t)
        # Change the metadata columns: propensity must move.
        data["creator"].x[:, -CREATOR_METADATA_DIM:] += 1.0
        _, _, p2 = model(data, t)
    assert torch.allclose(p0, p1)
    assert not torch.allclose(p1, p2)


def test_metadata_head_does_not_saturate_where_full_head_does():
    """Reproduces the real failure: 390 creators, treatment driven by metadata."""
    torch.manual_seed(0)
    n = 390
    x = torch.randn(n, CREATOR_FEATURE_DIM)
    logit = -2.0 + 1.2 * x[:, -CREATOR_METADATA_DIM] + 0.8 * x[:, -CREATOR_METADATA_DIM + 3]
    t = (torch.rand(n) < torch.sigmoid(logit)).float()

    def saturated_share(model, xin):
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        for _ in range(100):
            opt.zero_grad()
            p = model(xin)
            torch.nn.functional.binary_cross_entropy(p.clamp(1e-6, 1 - 1e-6), t).backward()
            opt.step()
        with torch.no_grad():
            p = model(xin)
        return ((p < 0.01) | (p > 0.99)).float().mean().item()

    torch.manual_seed(1)
    full = saturated_share(PropensityScoreModel(CREATOR_FEATURE_DIM, 16), x)
    torch.manual_seed(1)
    meta = saturated_share(PropensityScoreModel(CREATOR_METADATA_DIM), x[:, -CREATOR_METADATA_DIM:])
    assert full > 0.5, f"expected the full head to saturate, got {full:.0%}"
    assert meta < 0.05, f"metadata head saturated on {meta:.0%} of nodes"
