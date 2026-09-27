"""Combined GAIL loss (GAIL working-doc Step 11: "Update the Network" —
gradient descent minimizing prediction error + causal-regularization
penalties). Wires the individually-tested terms in
ml/causal_regularization.py to an actual prediction loss, with tunable
weights (PROJECT_PLAN.md Section 3c treats regularization strength as a
hyperparameter). No training loop existed before this to consume it —
see ml/training.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F

from ml.causal_regularization import (
    consistency_penalty,
    doubly_robust_weights,
    laplacian_smoothness_penalty,
    overlap_penalty,
)


@dataclass
class GAILLossWeights:
    prediction: float = 1.0
    overlap: float = 0.1
    smoothness: float = 0.1
    consistency: float = 0.1


def compute_gail_loss(
    predicted_spillover: torch.Tensor,
    target_spillover: torch.Tensor,
    propensity: torch.Tensor,
    collab_edge_index: torch.Tensor,
    collab_edge_weight: torch.Tensor,
    has_sponsored_neighbor_mask: torch.Tensor,
    weights: GAILLossWeights | None = None,
    prediction_mask: torch.Tensor | None = None,
    treatment: torch.Tensor | None = None,
) -> tuple[torch.Tensor, dict[str, float]]:
    """`predicted_spillover`/`target_spillover`/`propensity`/
    `has_sponsored_neighbor_mask` must all be over the SAME full node set
    that `collab_edge_index` indexes into — do not pre-subset them for a
    train/val split (found as a real bug wiring this into ml/training.py:
    subsetting before this call desyncs node indices from edge_index and
    crashes). Use `prediction_mask` instead to restrict which nodes
    contribute to the supervised MSE term; smoothness/consistency/overlap
    are structural/unsupervised and always use the full graph, standard
    practice for transductive GNN train/val splits.

    `treatment`, if given, applies `doubly_robust_weights` (inverse-
    propensity weighting) to the supervised term — the doubly-robust
    correction named in `ml/causal_regularization.py` but left unwired
    until now because no real outcome predictor/held-out data existed to
    apply it to. Optional and defaults to plain unweighted MSE so existing
    callers/tests are unaffected.
    """
    weights = weights or GAILLossWeights()
    if prediction_mask is None:
        prediction_mask = torch.ones_like(predicted_spillover, dtype=torch.bool)

    if treatment is None:
        prediction_loss = F.mse_loss(predicted_spillover[prediction_mask], target_spillover[prediction_mask])
    else:
        dr_weights = doubly_robust_weights(treatment, propensity)[prediction_mask]
        sq_err = (predicted_spillover[prediction_mask] - target_spillover[prediction_mask]).pow(2)
        prediction_loss = (dr_weights * sq_err).sum() / dr_weights.sum()
    overlap = overlap_penalty(propensity)
    smoothness = laplacian_smoothness_penalty(predicted_spillover, collab_edge_index, collab_edge_weight)
    # Applied to the PREDICTED spillover, not exposure: ml/exposure.py's
    # ExposureModule already guarantees exposure=0 for no-sponsored-neighbor
    # nodes *by construction* (treatment=0 for every term in the weighted
    # sum), so a penalty there would always be zero. The prediction head
    # still sees the creator embedding directly, though, so it could learn
    # a spurious nonzero spillover for such a node from embedding alone,
    # ignoring the (already-zero) exposure input -- that's the failure mode
    # this term actually guards against.
    consistency = consistency_penalty(predicted_spillover, has_sponsored_neighbor_mask)

    total = (
        weights.prediction * prediction_loss
        + weights.overlap * overlap
        + weights.smoothness * smoothness
        + weights.consistency * consistency
    )

    components = {
        "prediction": prediction_loss.item(),
        "overlap": overlap.item(),
        "smoothness": smoothness.item(),
        "consistency": consistency.item(),
        "total": total.item(),
    }
    return total, components
