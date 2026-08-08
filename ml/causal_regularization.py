"""Causal regularization terms for the GAIL branch (PROJECT_PLAN.md Section 3c
/ GAIL working-doc Step 10): overlap + doubly-robust correction (propensity
model), smoothness (graph Laplacian), and the consistency constraint.

These are standalone, tested primitives — pulled forward from Weeks 5-6 into
Weeks 3-4 since schema validation finished early. They are NOT yet wired into
a training loop, because there is no GAIL exposure/spillover predictor to
regularize yet (that's Weeks 11-13). Each function/class is validated here
against dummy data and hand-built small graphs; Weeks 11-13 combines them
with the prediction loss.
"""

from __future__ import annotations

import torch
from torch import nn


# --- Propensity model (overlap + doubly-robust correction) ------------------


class PropensityScoreModel(nn.Module):
    """Predicts P(treated | creator features). Logistic regression by default
    (hidden_dim=None); pass hidden_dim for a small one-hidden-layer MLP —
    PROJECT_PLAN.md Section 3c names both as acceptable.
    """

    def __init__(self, in_dim: int, hidden_dim: int | None = None):
        super().__init__()
        if hidden_dim:
            self.net = nn.Sequential(
                nn.Linear(in_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 1)
            )
        else:
            self.net = nn.Linear(in_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.net(x)).squeeze(-1)


def overlap_penalty(propensity: torch.Tensor, eps: float = 0.05) -> torch.Tensor:
    """GAIL doc Step 10 "Overlap": treatment probabilities shouldn't be
    extreme (0% or 100%). Penalizes propensity scores outside [eps, 1-eps].
    """
    lower_violation = (eps - propensity).clamp(min=0)
    upper_violation = (propensity - (1 - eps)).clamp(min=0)
    return (lower_violation.pow(2) + upper_violation.pow(2)).mean()


def doubly_robust_weights(
    treatment: torch.Tensor, propensity: torch.Tensor, clip_eps: float = 0.05
) -> torch.Tensor:
    """Inverse-propensity weights correcting for selection bias (brands
    favoring already-popular creators) — GAIL doc Step 10 "Doubly Robust
    Correction". `treatment` is 1 for sponsored nodes, 0 otherwise. Weeks
    11-13's training loop multiplies these into the outcome/exposure
    prediction loss; the outcome model itself (the "doubly robust" part
    proper) is the GAIL predictor, which doesn't exist yet.
    """
    p = propensity.clamp(min=clip_eps, max=1 - clip_eps)
    return treatment / p + (1 - treatment) / (1 - p)


# --- Smoothness (graph Laplacian) -------------------------------------------


def laplacian_smoothness_penalty(
    node_values: torch.Tensor, edge_index: torch.Tensor, edge_weight: torch.Tensor
) -> torch.Tensor:
    """GAIL doc Step 10 "Smoothness": similar creators (per the collaboration/
    co-occurrence graph) should have similar exposure. Computes the weighted
    graph-Laplacian quadratic form sum_(u,v) w_uv * (f_u - f_v)^2, meaned
    over edges. Expects `edge_index`/`edge_weight` for a single relation
    (e.g. collaborates_with) with both directions already populated per
    GRAPH_SCHEMA.md's symmetric-edge contract.
    """
    src, dst = edge_index
    diff = node_values[src] - node_values[dst]
    weight = edge_weight.squeeze(-1) if edge_weight.dim() > 1 else edge_weight
    return (weight * diff.pow(2)).mean()


# --- Consistency constraint --------------------------------------------------


def has_sponsored_neighbor(
    collab_edge_index: torch.Tensor, creator_is_sponsored: torch.Tensor
) -> torch.Tensor:
    """For each creator, whether any collaborator (per collab_edge_index) is
    sponsored. `creator_is_sponsored` is a bool/float tensor, 1 per creator.
    """
    src, dst = collab_edge_index
    sponsored_edges = creator_is_sponsored[src].bool()
    result = torch.zeros(creator_is_sponsored.size(0), dtype=torch.bool)
    result[dst[sponsored_edges]] = True
    return result


def consistency_penalty(exposure: torch.Tensor, has_sponsored_neighbor: torch.Tensor) -> torch.Tensor:
    """GAIL doc Step 10 "Consistency": no sponsored neighbors should result
    in zero exposure. Penalizes nonzero predicted exposure for creators with
    no sponsored collaborators.
    """
    unsponsored_mask = ~has_sponsored_neighbor
    if not unsponsored_mask.any():
        return torch.zeros((), dtype=exposure.dtype)
    return exposure[unsponsored_mask].pow(2).mean()
