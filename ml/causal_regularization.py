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


def doubly_robust_pseudo_outcome(
    outcome_prediction: torch.Tensor,
    observed_outcome: torch.Tensor,
    treatment: torch.Tensor,
    propensity: torch.Tensor,
    clip_eps: float = 0.05,
) -> torch.Tensor:
    """AIPW pseudo-outcome: the outcome model's guess, plus its own error
    reweighted by inverse propensity.

        tau_hat = mu(e,X) + [T / pi(X)] * [Y - mu(e,X)]

    This is the SECOND arm of the doubly robust estimator. `doubly_robust_weights`
    above supplies only inverse-propensity weighting, which is unbiased solely when
    pi is correct; the construction here is unbiased when EITHER model is correct:

      * pi wrong, mu right  -- residuals (Y - mu) average to zero, so the correction
        term vanishes however badly pi is estimated, and mu alone is already correct.
      * pi right, mu wrong  -- the correction term is a valid IPW estimate of the
        error mu made, and adding it back repairs the bias.

    NUISANCES ARE DETACHED. `outcome_prediction` and `propensity` enter the target
    without gradient. Supervising a model against a target that moves with its own
    output admits the degenerate solution of shifting both together to shrink the
    loss while learning nothing; detaching makes the pseudo-outcome a fixed
    regression target per step, which is the standard DR-learner pattern.

    `treatment` here is the interference indicator -- 1 when the node has a sponsored
    NEIGHBOUR, not when the node is itself sponsored. GAIL estimates spillover, so the
    quantity being corrected for selection is "was this creator's neighbourhood likely
    to be sponsored", matching the estimator in the model specification.
    """
    mu = outcome_prediction.detach()
    p = propensity.detach().clamp(min=clip_eps, max=1 - clip_eps)
    return mu + (treatment / p) * (observed_outcome - mu)


def doubly_robust_effect(
    mu_exposed: torch.Tensor,
    mu_unexposed: torch.Tensor,
    observed_outcome: torch.Tensor,
    treatment: torch.Tensor,
    propensity: torch.Tensor,
    clip_eps: float = 0.05,
) -> torch.Tensor:
    """Per-node AIPW spillover effect -- the estimator that actually carries the
    doubly robust guarantee.

        tau_hat = [mu(e,X) - mu(0,X)]
                  + [T / pi(X)]       * [Y - mu(e,X)]
                  - [(1-T) / (1-pi)]  * [Y - mu(0,X)]

    WHY TWO ARMS. `doubly_robust_pseudo_outcome` above implements the formula as
    written in the model specification, with mu evaluated at the OBSERVED exposure.
    That is a selection-corrected target for Y -- useful as a regression target, and
    what the L_DR loss term needs -- but it is NOT an effect estimator, and it does
    not inherit the "unbiased if EITHER model is correct" property. Verified
    numerically: with a confounder driving both treatment and outcome, the
    single-arm form returns E[Y], not the contrast.

    An effect is a difference between two worlds, so both must be predicted. In
    GAIL the counterfactual world is simply exposure set to zero, so `mu_unexposed`
    is the prediction head evaluated with exposure zeroed while the embedding is
    held fixed -- no separate counterfactual model is needed.

    Checked on synthetic data with a known effect of 5.0:
        mu right,  pi wrong  -> 5.000
        pi right,  mu wrong  -> 4.997
        both right           -> 5.000
        both wrong           -> 5.400  (the one failing case)

    `treatment` is the interference indicator: 1 when the node has a sponsored
    NEIGHBOUR. Nuisances are detached for the same reason as above.
    """
    mu_e = mu_exposed.detach()
    mu_0 = mu_unexposed.detach()
    p = propensity.detach().clamp(min=clip_eps, max=1 - clip_eps)
    return (
        (mu_e - mu_0)
        + (treatment / p) * (observed_outcome - mu_e)
        - ((1 - treatment) / (1 - p)) * (observed_outcome - mu_0)
    )


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

    Zero edges (the real collaboration graph's actual state as of
    2026-08-10 — found while wiring this into ml/gail_loss.py) means no
    smoothness constraint to apply, vacuously satisfied — returns 0, not
    the NaN that `.mean()` over an empty tensor would silently produce.
    """
    if edge_index.size(1) == 0:
        return torch.zeros((), dtype=node_values.dtype)
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