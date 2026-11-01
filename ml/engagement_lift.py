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

import math
import statistics
from typing import Sequence

from ml.target_clustering import DEFAULT_WINDOW_DAYS, windowed_engagement

# Which table, date column and two engagement columns each platform uses.
# Shared for the same reason as the formula below: this lived in both scripts,
# and a change to one did not reach the other.
PLATFORM_TABLES = {
    "instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
    "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
    "reddit": ("reddit_posts", "posted_at", "score", "num_comments"),
}

# Which statistic produces the training target. "median" per the evidence above;
# "mean" reproduces the pre-2026-10-19 behaviour exactly, for comparison runs.
TARGET_STATISTIC = "median"

# Minimum posts required on EACH side for a row to count as well measured. 1 means
# no filtering, which is the default: it keeps this module's introduction to a single
# change (mean -> median) so the effect of that change is attributable.
DEFAULT_MIN_POSTS = 1


def platform_engagement(
    cur,
    creator_id: str,
    platform: str,
    event_date,
    window_days: int = DEFAULT_WINDOW_DAYS,
    before_days: int | None = None,
) -> tuple[list[float], list[float]]:
    """Fully-measured engagement either side of an event, in a BOUNDED window.

    WHY SHARED. This query existed in `compute_training_pair_deltas.py` and
    `train_prod_model.py` with identical SQL and DIFFERENT windowing: the deltas
    script bounded to +/- 30 days (E2), the training script did not. The model
    therefore trained on unbounded windows -- the exact bug E2 removed -- while
    the script used to inspect the data showed the fixed version. Measured
    2026-10-22: 26 lift-computable rows bounded, 51 unbounded, with one creator
    contributing 17 of them at a lift of +14.86.

    BOTH ENGAGEMENT COLUMNS MUST BE NON-NULL. Two layers of missingness, both
    found live. Coalescing NULL to 0 treats "never measured" as "measured zero"
    and fabricates million-percent lifts; 28% of instagram_posts have
    like_count and 39% have comment_count, and the missingness is skewed in
    time. Excluding only both-NULL rows is not enough either: posts carrying
    just the smaller metric (comment_count present, like_count NULL) still bias
    whichever side holds more of them. So a post counts only when fully
    measured.

    Args:
        cur: an open database cursor.
        creator_id: the NEIGHBOUR whose engagement is being measured.
        platform: a key of `PLATFORM_TABLES`.
        event_date: when the sponsorship event happened.
        window_days: half-width of the window. The event day itself falls in
            neither side -- a post made that day may be the sponsored post.
        before_days: baseline width, if wider than the after side (see
            `windowed_engagement`). None keeps the symmetric window.

    Returns:
        (before, after), each a list of summed engagement values.
    """
    table, date_col, e1, e2 = PLATFORM_TABLES[platform]
    cur.execute(
        f"select {date_col}, {e1}, {e2} "
        f"from {table} where creator_id::text = %s and {date_col} is not null "
        f"and {e1} is not null and {e2} is not null order by {date_col}",
        (creator_id,),
    )
    rows = cur.fetchall()
    return windowed_engagement(
        [(d, e1v + e2v) for d, e1v, e2v in rows], event_date, window_days, before_days
    )


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
        # P3b. Log-ratio of the medians. `robust_lift` is a RATIO minus one, so
        # it is bounded below by -1 and unbounded above: a creator going from a
        # median of 0 to 118 scores +118, while the worst possible fall scores
        # -1. On the 2026-10-25 run one control at +118.9 carried most of the
        # squared error over 459 observations. On the log scale halving and
        # doubling are equal and opposite (-0.69 / +0.69). Engagement is clamped
        # at 0 first because Reddit scores can be negative, which would put the
        # denominator at or below zero.
        "log_lift": math.log((max(med_after, 0) + 1) / (max(med_before, 0) + 1)),
    }


def _key(statistic: str) -> str:
    if statistic == "median":
        return "robust_lift"
    if statistic == "mean":
        return "lift"
    if statistic == "log":
        return "log_lift"
    raise ValueError(f"statistic must be 'median', 'mean' or 'log', got {statistic!r}")


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

# --- P3: bulk access for control observations --------------------------------
#
# Control observations need a lift for hundreds of creators at each treated
# window's event dates. `platform_engagement` issues one query per (creator,
# platform, date), which over the Supabase pooler would be tens of thousands of
# round trips. These two functions fetch every platform's posts once and compute
# the SAME lift from memory: same "both columns non-null" filter, same summed
# engagement, same bounded window, same per-platform median lift averaged across
# platforms. Treated and control lifts must be measured identically or their
# difference measures the method, not the spillover.


def load_platform_posts(cur, platform: str) -> dict[str, list[tuple]]:
    """All fully-measured posts on one platform: creator_id -> [(date, engagement)]."""
    table, date_col, e1, e2 = PLATFORM_TABLES[platform]
    cur.execute(
        f"select creator_id::text, {date_col}, {e1}, {e2} "
        f"from {table} where creator_id is not null and {date_col} is not null "
        f"and {e1} is not null and {e2} is not null order by {date_col}"
    )
    out: dict[str, list[tuple]] = {}
    for creator_id, d, e1v, e2v in cur.fetchall():
        out.setdefault(creator_id, []).append((d, e1v + e2v))
    return out


def lift_from_posts(
    posts_by_platform: dict[str, dict[str, list[tuple]]],
    creator_id: str,
    event_date,
    window_days: int = DEFAULT_WINDOW_DAYS,
    statistic: str = TARGET_STATISTIC,
    before_days: int | None = None,
) -> float | None:
    """`row_target` for one (creator, event date) from prefetched posts.

    Returns None when no platform has posts on both sides -- the same rows the
    treated path skips -- rather than a fabricated zero.
    """
    platform_lifts = {}
    for platform, by_creator in posts_by_platform.items():
        before, after = windowed_engagement(
            by_creator.get(creator_id, ()), event_date, window_days, before_days
        )
        if before and after:
            platform_lifts[platform] = platform_lift(before, after)
    if not platform_lifts:
        return None
    return row_target(platform_lifts, statistic=statistic)
