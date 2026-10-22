"""Single definition of the engagement lift a sponsorship event is scored by.

WHY THIS IS SHARED. The formula lived in two places: `compute_training_pair_deltas.py`,
which writes `training_pair_deltas.json` for inspection, and `train_prod_model.py`,
which recomputes it from the database at training time. Nothing kept them in step, so
a fix applied to one left the model training on the other -- the same drift A1 removed
between `ml/` and `backend/app/gail/`. Both now import from here.

WHY THE MEDIAN. The original formula averaged engagement with the arithmetic mean:

    lift = (mean(after) - mean(before)) / (mean(before) + 1)

Engagement is heavy-tailed. A single video that takes off moves the mean of a dozen
enormously, so the resulting "lift" measures that one video rather than the
sponsorship. The live run on 2026-10-19 showed this directly:

  creator 767cd996, 8-18 posts on each side of every event -- so not thin data:
      mean-based   +3.074   +2.677   -0.754
      median-based -0.036   +0.527   -0.166

  creator c1dfc782, the largest value in the dataset:
      mean-based  +34.724   ->   median-based +1.759

  across all 26 rows:
      stdev   6.893 -> 1.495      max|lift|  34.724 -> 4.110

The median of the same window is unmoved by one viral post, so it measures what the
estimand asks about: whether the neighbour's TYPICAL post did better. Both statistics
are computed and stored; `TARGET_STATISTIC` selects the one that trains.

WHAT THIS DOES NOT FIX. A row computed from one post before and one after is noise
whichever statistic is used -- the median of a single value is that value. That is a
sample-size problem, and `well_measured` exists to filter those rows when a minimum
post count has been decided. It is NOT applied by default: filtering costs effective
sample size, so the threshold is a stated choice rather than a silent one.
"""

from __future__ import annotations

import statistics
from typing import Sequence

# Which statistic produces the training target. "median" per the evidence above;
# "mean" reproduces the pre-2026-10-19 behaviour exactly, for comparison runs.
TARGET_STATISTIC = "median"

# Minimum posts required on EACH side for a row to count as well measured. 1 means
# no filtering, which is the default: it keeps this module's introduction to a single
# change (mean -> median) so the effect of that change is attributable.
DEFAULT_MIN_POSTS = 1


def platform_lift(before: Sequence[float], after: Sequence[float]) -> dict:
    """Relative engagement lift on one platform, under both statistics.

    Args:
        before: engagement values from the window before the event. Non-empty.
        after: engagement values from the window after the event. Non-empty.

    Returns:
        A dict carrying the post counts, both central values, and both lifts.
        The `+ 1` in the denominator keeps the ratio finite when a creator's
        baseline engagement is zero.

    Raises:
        ValueError: if either side is empty. A lift needs both sides, and
            returning a sentinel would let an uncomputable row reach the model
            as a real zero.
    """
    if not before or not after:
        raise ValueError("relative lift needs values on both sides of the event")

    mean_before = statistics.mean(before)
    mean_after = statistics.mean(after)
    med_before = statistics.median(before)
    med_after = statistics.median(after)

    return {
        "n_before": len(before),
        "n_after": len(after),
        "avg_before": mean_before,
        "avg_after": mean_after,
        "lift": (mean_after - mean_before) / (mean_before + 1),
        "med_before": med_before,
        "med_after": med_after,
        "robust_lift": (med_after - med_before) / (med_before + 1),
    }


def _key(statistic: str) -> str:
    if statistic == "median":
        return "robust_lift"
    if statistic == "mean":
        return "lift"
    raise ValueError(f"statistic must be 'median' or 'mean', got {statistic!r}")


def row_target(platform_lifts: dict[str, dict], statistic: str = TARGET_STATISTIC) -> float:
    """One lift per (event, neighbour) row, averaged across its platforms.

    A neighbour measurable on both Instagram and Reddit contributes one lift per
    platform; those are averaged because they are two readings of the same event,
    not two events. This average stays arithmetic: it combines already-normalised
    ratios, not raw engagement counts, so the heavy tail that motivated the median
    is not present here.

    Raises:
        ValueError: if `platform_lifts` is empty -- a cross-platform-only straddle
            has no same-platform lift and must be reported, not averaged to zero.
    """
    if not platform_lifts:
        raise ValueError("no platform has both sides measured; this row has no lift")
    key = _key(statistic)
    return statistics.mean(v[key] for v in platform_lifts.values())


def well_measured(platform_lifts: dict[str, dict], min_posts: int = DEFAULT_MIN_POSTS) -> bool:
    """Whether every platform behind a row clears `min_posts` on both sides.

    The weakest platform decides: a row averaging a well-measured platform with a
    one-post platform is only as trustworthy as that one post.
    """
    if not platform_lifts:
        return False
    return all(
        v["n_before"] >= min_posts and v["n_after"] >= min_posts
        for v in platform_lifts.values()
    )