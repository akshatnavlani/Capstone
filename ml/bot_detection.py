"""Heuristic bot/fake-account detection (PROJECT_PLAN.md Section 2).

Deliberately heuristic, not a trained classifier — no labeled ground truth
exists to train/validate one reliably (an intentional simplification per
Section 2, not an oversight). Produces the `bot_score` (float, 0-1) and
`is_bot_flagged` (bool) values Track A's SCHEMA.md reserves on profile
tables (`is_bot_flagged boolean` / `bot_score real`, nullable, populated by
this module). Pulled forward from Weeks 7-8 since Weeks 1-4 finished early —
thresholds below are reasonable defaults, not fit to real data (none exists
yet); revisit once real profiles land.

Signals used match exactly what Track A's SCHEMA.md confirms it supplies:
follower_count/following_count ratio, account_created_at (YouTube/Reddit
only — Instagram doesn't expose this), and posting frequency from
posted_at/published_at timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def follower_following_ratio_score(
    follower_count: int, following_count: int, ratio_threshold: float = 3.0
) -> float:
    """High following:follower ratio is a common mass-following bot signal."""
    if follower_count < 0 or following_count < 0:
        raise ValueError("counts must be non-negative")
    ratio = following_count / max(follower_count, 1)
    return _clip01(ratio / ratio_threshold)


def account_age_score(account_age_days: float | None, young_threshold_days: float = 30.0) -> float:
    """Younger accounts are more suspicious. Returns 0 (not 1) when age data
    isn't available — e.g. Instagram, which doesn't expose
    account_created_at per Track A's SCHEMA.md — rather than guessing high.
    """
    if account_age_days is None:
        return 0.0
    if account_age_days < 0:
        raise ValueError("account_age_days must be non-negative")
    return _clip01(1.0 - account_age_days / young_threshold_days)


def posting_frequency_score(posts_per_day: float, spam_threshold: float = 10.0) -> float:
    """Sustained very-high posting frequency is a spam/bot signal."""
    if posts_per_day < 0:
        raise ValueError("posts_per_day must be non-negative")
    return _clip01(posts_per_day / spam_threshold)


def engagement_mismatch_score(
    engagement_rate: float, follower_count: int, low_engagement_threshold: float = 0.005
) -> float:
    """Very low engagement rate relative to a large follower count suggests
    purchased/fake followers. Only checked above a minimum follower floor —
    small accounts naturally have noisy engagement rates, not a bot signal.
    """
    if engagement_rate < 0:
        raise ValueError("engagement_rate must be non-negative")
    if follower_count < 1000:
        return 0.0
    if engagement_rate >= low_engagement_threshold:
        return 0.0
    return _clip01(1.0 - engagement_rate / low_engagement_threshold)


@dataclass
class BotSignals:
    follower_count: int
    following_count: int
    account_age_days: float | None  # None if unavailable (e.g. Instagram)
    posts_per_day: float
    engagement_rate: float


DEFAULT_COMPONENT_WEIGHTS = {
    "follower_following_ratio": 0.3,
    "account_age": 0.25,
    "posting_frequency": 0.2,
    "engagement_mismatch": 0.25,
}


def compute_bot_score(
    signals: BotSignals, weights: dict[str, float] | None = None
) -> float:
    """Weighted average of the four heuristic component scores, each in
    [0, 1]. When account_age is unavailable, its score is 0 (not
    suspicious) rather than excluded — a missing signal shouldn't inflate
    the score, only the other three signals can flag an Instagram account.
    """
    weights = weights or DEFAULT_COMPONENT_WEIGHTS
    component_scores = {
        "follower_following_ratio": follower_following_ratio_score(
            signals.follower_count, signals.following_count
        ),
        "account_age": account_age_score(signals.account_age_days),
        "posting_frequency": posting_frequency_score(signals.posts_per_day),
        "engagement_mismatch": engagement_mismatch_score(
            signals.engagement_rate, signals.follower_count
        ),
    }
    total_weight = sum(weights[k] for k in component_scores)
    return sum(weights[k] * component_scores[k] for k in component_scores) / total_weight


def is_bot_flagged(bot_score: float, threshold: float = 0.6) -> bool:
    return bot_score >= threshold


# --- loading signals from the live schema (E10) ------------------------------


def _columns(cur, table: str) -> set[str]:
    """Column names of a table, read from the server rather than assumed.

    Track A's schema has moved during the project and guessing has cost real
    runs -- `creator_sponsorship_events` has no `id`, found the hard way. The
    bot-signal loader below needs columns that may or may not exist on a given
    platform's profile table, so it asks first.
    """
    cur.execute(f"select * from {table} limit 0")
    return {d[0] for d in cur.description}


def load_bot_scores(cur, id_to_index: dict[str, int]) -> dict[str, dict]:
    """E10. Heuristic bot score per creator, from whatever signals exist.

    `ml/bot_detection.py` was written, tested (14 tests) and never connected to
    anything -- the thresholds were set against no real profiles because none
    existed then. This reads the signals it needs from the live schema, skipping
    any the tables do not carry: a missing signal scores 0 (not suspicious)
    rather than inflating the score, matching `compute_bot_score`'s contract.

    NOTHING IS EXCLUDED HERE. The scores are reported and saved so the flagged
    creators can be looked at, but no training pair is dropped on their account.
    With 19 independent observations, removing a creator is a decision worth
    making deliberately and stating in the write-up, not a side effect of
    wiring a module in.
    """
    available = _columns(cur, "instagram_profiles")
    wanted = ["creator_id::text"]
    for col in ("follower_count", "following_count", "post_count"):
        if col in available:
            wanted.append(col)

    cur.execute(f"select {', '.join(wanted)} from instagram_profiles")
    names = [w.split("::")[0] for w in wanted]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]

    # Posts per day, from the span of a creator's Instagram activity.
    cur.execute(
        "select creator_id::text, count(*), min(posted_at), max(posted_at) "
        "from instagram_posts where posted_at is not null group by creator_id"
    )
    cadence = {}
    for cid, n, first, last in cur.fetchall():
        span_days = max((last - first).days, 1) if first and last else 1
        cadence[cid] = n / span_days

    scores: dict[str, dict] = {}
    for row in rows:
        cid = row["creator_id"]
        if cid not in id_to_index:
            continue
        followers = int(row.get("follower_count") or 0)
        following = int(row.get("following_count") or 0)
        signals = BotSignals(
            follower_count=followers,
            following_count=following,
            # Instagram does not expose account creation, per Track A's SCHEMA.md.
            account_age_days=None,
            posts_per_day=cadence.get(cid, 0.0),
            # Engagement is scored elsewhere; 0 here means "no mismatch signal".
            engagement_rate=0.0 if followers < 1000 else 1.0,
        )
        score = compute_bot_score(signals)
        scores[cid] = {"bot_score": score, "is_bot_flagged": is_bot_flagged(score)}
    return scores