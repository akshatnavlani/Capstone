"""Per-dimension z-score scaling for creator features.

WHY THIS EXISTS. `PropensityScoreModel` is a linear head straight over the
creator feature vector. Those features are on wildly different scales:
`log_subscriber_count` runs to ~17, `engagement_rate` sits in [0, 1], and the
category one-hots are 0/1. Fed raw, the large-magnitude dimensions dominate
the logit, it saturates, and `sigmoid` returns values pinned at 1.000 for
every node. When that happens:

  * the overlap penalty (`L_overlap`) is in the loss but has nothing to push
    against -- positivity is violated, not enforced;
  * the inverse-propensity weights `T/pi` collapse to a constant, so the
    doubly robust correction degenerates into plain MSE;
  * any causal reading of the estimates is unsupported, because the overlap
    identification assumption is empirically unmet.

Z-scoring each dimension before the head fixes this. `train_prod_model.py`
already did so inline (propensity mean 0.61 in checkpoint c6488a6) while
`train_holdout_round3.py` did not, so the SERVED model was fine but every
EVALUATION number came from folds where propensity saturated. This module is
the single shared implementation so the two cannot drift apart again.

LEAKAGE NOTE. `apply_feature_scaler` is intended to be called over all creator
nodes, including any held out in cross-validation. That is deliberate and
matches the transductive design documented in `leave_one_out_eval`: a held-out
node's features and graph position are visible to the model (it participates
in message passing regardless), and only its LABEL is masked from the
supervised loss. Scaling therefore leaks no label information. If a future
inductive split is added -- where held-out nodes are genuinely absent from the
graph -- the scaler must instead be fit on training nodes only and applied to
the held-out ones, which is what `fit_indices` is for.
"""

from __future__ import annotations

import torch

# Guards against division by zero on constant dimensions. One-hot category
# columns legitimately have near-zero variance when a category is rare or
# absent; clamping leaves them effectively unscaled rather than exploding them
# into huge values that would re-introduce the saturation this module fixes.
_MIN_STD = 1e-6


def compute_feature_scaler(
    x: torch.Tensor,
    fit_indices: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Per-dimension mean and std over the node feature matrix.

    Args:
        x: ``[num_nodes, num_features]`` raw creator features.
        fit_indices: optional subset of rows to fit on. Leave as ``None`` for
            the transductive case (fit over every node). Pass training-node
            indices only if the split is inductive -- see the module docstring.

    Returns:
        ``(mean, std)``, each ``[num_features]``. ``std`` is clamped to
        ``_MIN_STD`` so constant dimensions cannot produce division by zero.
    """
    if x.ndim != 2:
        raise ValueError(f"expected [num_nodes, num_features], got shape {tuple(x.shape)}")
    if x.size(0) == 0:
        raise ValueError("cannot compute a scaler over zero nodes")

    source = x if fit_indices is None else x[fit_indices]
    if source.size(0) == 0:
        raise ValueError("fit_indices selected zero nodes")

    mean = source.mean(dim=0)
    # unbiased=False so a single fit row yields std 0 (then clamped) rather
    # than NaN from the n-1 denominator.
    std = source.std(dim=0, unbiased=False).clamp(min=_MIN_STD)
    return mean, std


def apply_feature_scaler(
    x: torch.Tensor,
    mean: torch.Tensor,
    std: torch.Tensor,
) -> torch.Tensor:
    """Return ``(x - mean) / std``, validating shapes first.

    Kept separate from :func:`compute_feature_scaler` because inference reloads
    a persisted scaler (``models/feature_scaler.json``) rather than recomputing
    one -- applying training-time statistics at serving time is the whole point
    of saving them.
    """
    if mean.shape != std.shape:
        raise ValueError(f"mean {tuple(mean.shape)} and std {tuple(std.shape)} must match")
    if x.size(-1) != mean.size(-1):
        raise ValueError(
            f"feature dim mismatch: x has {x.size(-1)}, scaler has {mean.size(-1)}"
        )
    return (x - mean) / std


def scale_features(
    x: torch.Tensor,
    fit_indices: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Convenience wrapper: fit and apply in one call.

    Returns ``(x_scaled, mean, std)``. The statistics come back so callers can
    persist them for inference.
    """
    mean, std = compute_feature_scaler(x, fit_indices=fit_indices)
    return apply_feature_scaler(x, mean, std), mean, std
