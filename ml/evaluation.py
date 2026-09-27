"""Evaluation harness (PROJECT_PLAN.md Section 3c: "empirical — train/test
split on historical campaigns, held-out accuracy/calibration reporting").

No real campaigns exist yet to split on, so `train_val_split` in
ml/training.py is a plain random node split — this module scores whatever
held-out predictions/targets it's given, independent of how the split was
made, so it's ready to consume a real campaign-based split later without
changes here.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class EvaluationReport:
    mae: float
    rmse: float
    r2: float
    calibration_slope: float
    calibration_intercept: float
    n: int


def _linear_fit(x: torch.Tensor, y: torch.Tensor) -> tuple[float, float]:
    """Least-squares slope/intercept of y ~ x (actual ~ predicted). Ideal
    calibration is slope=1, intercept=0.
    """
    x_mean, y_mean = x.mean(), y.mean()
    denom = (x - x_mean).pow(2).sum()
    if denom.item() == 0.0:
        return float("nan"), float("nan")
    slope = ((x - x_mean) * (y - y_mean)).sum() / denom
    intercept = y_mean - slope * x_mean
    return slope.item(), intercept.item()


def evaluate_predictions(predictions: torch.Tensor, targets: torch.Tensor) -> EvaluationReport:
    if predictions.shape != targets.shape:
        raise ValueError(f"shape mismatch: predictions {predictions.shape} vs targets {targets.shape}")
    n = predictions.numel()
    if n == 0:
        return EvaluationReport(mae=float("nan"), rmse=float("nan"), r2=float("nan"),
                                 calibration_slope=float("nan"), calibration_intercept=float("nan"), n=0)

    residuals = predictions - targets
    mae = residuals.abs().mean().item()
    rmse = residuals.pow(2).mean().sqrt().item()

    ss_res = residuals.pow(2).sum()
    ss_tot = (targets - targets.mean()).pow(2).sum()
    r2 = (1 - ss_res / ss_tot).item() if ss_tot.item() != 0.0 else float("nan")

    slope, intercept = _linear_fit(predictions, targets)

    return EvaluationReport(mae=mae, rmse=rmse, r2=r2, calibration_slope=slope, calibration_intercept=intercept, n=n)
