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
    doubly_robust_pseudo_outcome,
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
    dr_mode: str = "ipw",
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

    `treatment` is the interference indicator (1 when the node has a
    sponsored NEIGHBOUR). Given it, `dr_mode` selects how selection bias is
    corrected in the supervised term:

      "ipw"  (default) -- weight the squared error by `doubly_robust_weights`.
               Unbiased only if the propensity model is correct. This is the
               historical behaviour and stays the default so existing callers
               and the ablation arm are unaffected.
      "aipw" -- regress onto the `doubly_robust_pseudo_outcome`, which adds
               the outcome-model arm. Unbiased if EITHER the propensity or the
               outcome model is correct, which is the actual doubly robust
               property; "ipw" alone never had it despite the function name.

    Without `treatment`, both modes fall back to plain unweighted MSE.
    """
    weights = weights or GAILLossWeights()
    if prediction_mask is None:
        prediction_mask = torch.ones_like(predicted_spillover, dtype=torch.bool)

    if dr_mode not in ("ipw", "aipw"):
        raise ValueError(f"dr_mode must be 'ipw' or 'aipw', got {dr_mode!r}")

    if treatment is None:
        prediction_loss = F.mse_loss(predicted_spillover[prediction_mask], target_spillover[prediction_mask])
    elif dr_mode == "aipw":
        # Full doubly robust: supervise against the selection-corrected target
        # rather than the raw observed one. The pseudo-outcome detaches its
        # nuisances, so this is an ordinary regression onto a fixed target.
        pseudo = doubly_robust_pseudo_outcome(
            predicted_spillover, target_spillover, treatment, propensity
        )
        prediction_loss = F.mse_loss(
            predicted_spillover[prediction_mask], pseudo[prediction_mask]
        )
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