"""Placebo (pre-trend) check: a sponsorship cannot cause engagement change that
happened BEFORE it.

For each observation we measure a second lift, the PLACEBO lift, with the event
date moved back by one full window: the baseline and outcome windows then both
fall before the real sponsorship. Any effect the model attributes to exposure
in that period is spurious -- shared trends, seasonality, or similar creators
moving together -- because the treatment had not happened yet.

Two uses:

  1. A model-free pre-trend test: run the same matched DiD on placebo lifts.
     A clearly non-zero result means exposed and control creators were already
     diverging before the sponsorship, so the real DiD is confounded.
  2. A training penalty (`placebo_penalty`): the exposure-driven part of the
     prediction, mu(e, X) - mu(0, X), should not track the placebo lift. The
     penalty is the squared covariance between the two, scaled by the placebo
     lift's variance. Its gradient reaches the attention weights and beta
     through the exposure, so links whose exposure "explains" pre-period change
     are pushed down.

Limits: it catches confounding that is already visible before the event. A
common shock that starts exactly at the sponsorship date (a brand campaign
across a whole niche) passes the test.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Callable, Sequence

import torch


def placebo_anchor(event_date, window_days: int):
    """Event date moved back far enough that both windows end before the event.

    The outcome side of `windowed_engagement` is (anchor, anchor + window], so an
    anchor of event - (window + 1) days ends the outcome side the day before the
    event and keeps the event day itself out of both sides.
    """
    return event_date - timedelta(days=window_days + 1)


def placebo_lift(
    event_dates: Sequence,
    lift_at: Callable[[object], float | None],
    window_days: int,
) -> float | None:
    """Mean lift over the shifted anchors of an observation's event dates.

    `lift_at(anchor)` computes the lift around one anchor date, exactly as the
    real lift is computed (same window, same statistic). Returns None when no
    anchor has data on both sides -- never a fabricated zero.
    """
    lifts = [
        v for v in (lift_at(placebo_anchor(d, window_days)) for d in event_dates)
        if v is not None
    ]
    if not lifts:
        return None
    return sum(lifts) / len(lifts)


def placebo_penalty(gap: torch.Tensor, pre_lift: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """Squared covariance between the exposure-driven prediction and the
    placebo lift, divided by the placebo lift's variance.

    Args:
        gap: mu(e, X) - mu(0, X) per observation (carries gradient).
        pre_lift: placebo lift per observation (a fixed target).

    Returns 0 when there are fewer than 2 observations or the placebo lift does
    not vary, since there is then no association to penalise.
    """
    if gap.numel() < 2:
        return gap.sum() * 0.0
    pre = pre_lift.detach().to(gap.dtype)
    var_pre = pre.var(unbiased=False)
    if float(var_pre) < eps:
        return gap.sum() * 0.0
    cov = ((gap - gap.mean()) * (pre - pre.mean())).mean()
    return cov.pow(2) / (var_pre + eps)
