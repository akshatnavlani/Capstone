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
