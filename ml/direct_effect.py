"""Direct effect: how a creator's OWN audience responds to their sponsored posts.

ESTIMAND. For a sponsored post p by creator c on platform k:

    effect(p) = log(eng(p) + 1) - mean over B of log(eng(q) + 1)

where B is c's non-sponsored posts of the same format on k within +-window days
of p. Averaging on the log scale (a geometric mean) matters: engagement has a
long right tail even in logs, so a single post compared with its neighbours'
MEDIAN sits above it on average -- the 27 Oct run's placebo was +0.15 that way,
and the distortion differs by creator, which would bias a ranking toward
breakout-prone creators. Against the mean of logs, a random post is unbiased
whatever the skew.

The baseline is the same creator (audience size, niche and style cancel), the
same format (YouTube Shorts vs long videos; Instagram media type), at nearby
dates (slow trends cancel). Format matters: sponsorships sit mostly in long
videos while ordinary posts mix in Shorts, whose views differ hugely; without
format matching the placebo came out at +0.18 on the 27 Oct run. The identifying assumption: had p not been
sponsored, it would have performed like the creator's nearby ordinary posts.

PLACEBO. The same statistic for randomly chosen NON-sponsored posts. It should
be ~0; a clear non-zero value means the comparison itself is biased (for
example, posts that are compared to their neighbours systematically win).

PER-CREATOR SCORES are shrunk toward the overall mean (normal-normal empirical
Bayes), so a creator with one lucky sponsored post cannot top a ranking: the
fewer sponsored posts, the more the score leans on the average.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta

MIN_BASELINE_POSTS = 3
MIN_AGE_DAYS = 14   # younger posts are still accumulating views/likes


@dataclass
class Post:
    creator: str
    platform: str
    post_id: str
    day: date
    engagement: float
    sponsored: bool
    fmt: str = "any"   # format: YouTube short/long, Instagram media type


def _day(d) -> date:
    return d.date() if isinstance(d, datetime) else d


def post_effect(post: Post, same_creator_platform: list[Post], window_days: int = 30,
                min_baseline: int = MIN_BASELINE_POSTS) -> float | None:
    """Log engagement minus the mean log engagement of nearby ordinary posts
    of the SAME format (a long video is never compared with Shorts)."""
    lo, hi = post.day - timedelta(days=window_days), post.day + timedelta(days=window_days)
    base = [q.engagement for q in same_creator_platform
            if not q.sponsored and q.post_id != post.post_id and q.fmt == post.fmt and lo <= q.day <= hi]
    if len(base) < min_baseline:
        return None
    return math.log(max(post.engagement, 0) + 1) - statistics.mean(math.log(max(b, 0) + 1) for b in base)


def settled(posts: list[Post], today: date, min_age_days: int = MIN_AGE_DAYS) -> list[Post]:
    """Drop posts too recent for their counts to have settled."""
    cutoff = today - timedelta(days=min_age_days)
    return [p for p in posts if p.day <= cutoff]


def effects_by_creator(targets: list[Post], all_posts: list[Post], window_days: int = 30) -> dict[str, list[float]]:
    """Effect of each target post, grouped by creator; posts without a baseline are skipped."""
    by_cp: dict[tuple[str, str], list[Post]] = {}
    for p in all_posts:
        by_cp.setdefault((p.creator, p.platform), []).append(p)
    out: dict[str, list[float]] = {}
    for p in targets:
        e = post_effect(p, by_cp.get((p.creator, p.platform), []), window_days)
        if e is not None:
            out.setdefault(p.creator, []).append(e)
    return out


def placebo_targets(all_posts: list[Post], sponsored_counts: dict[str, int], seed: int = 0) -> list[Post]:
    """For each creator, as many random ordinary posts as they have sponsored ones."""
    rng = random.Random(seed)
    ordinary: dict[str, list[Post]] = {}
    for p in all_posts:
        if not p.sponsored:
            ordinary.setdefault(p.creator, []).append(p)
    picks = []
    for c, n in sponsored_counts.items():
        pool = ordinary.get(c, [])
        picks.extend(rng.sample(pool, min(n, len(pool))))
    return picks


def _pool(effects: dict[str, list[float]]):
    """Shared pieces of the empirical-Bayes model (see `shrink`)."""
    creators = [c for c, v in effects.items() if v]
    means = {c: statistics.mean(effects[c]) for c in creators}
    resid = [x - means[c] for c in creators for x in effects[c]]
    n_tot = sum(len(effects[c]) for c in creators)
    dof = n_tot - len(creators)
    s2 = sum(r * r for r in resid) / dof if dof > 0 else statistics.pvariance([x for c in creators for x in effects[c]])
    se2 = {c: s2 / len(effects[c]) for c in creators}
    mu = sum(means[c] / se2[c] for c in creators) / sum(1 / se2[c] for c in creators)
    tau2 = max(0.0, statistics.mean([(means[c] - mu) ** 2 - se2[c] for c in creators])) if len(creators) > 1 else 0.0
    se_mu2 = 1 / sum(1 / se2[c] for c in creators)   # uncertainty of the overall mean
    return creators, means, se2, mu, tau2, se_mu2


def shrink(effects: dict[str, list[float]]) -> dict[str, dict]:
    """Normal-normal empirical Bayes per creator.

    Within-creator variance is pooled across creators (one-post creators have
    none of their own); between-creator variance tau^2 by method of moments,
    floored at 0. Returns {creator: {n, raw, score, lo, hi}}.
    """
    if not any(effects.values()):
        return {}
    creators, means, se2, mu, tau2, se_mu2 = _pool(effects)
    out = {}
    for c in creators:
        w = tau2 / (tau2 + se2[c]) if tau2 + se2[c] > 0 else 0.0
        score = w * means[c] + (1 - w) * mu
        # Posterior variance of the creator's effect, plus the part of mu's
        # uncertainty it inherits through shrinkage.
        sd = math.sqrt(w * se2[c] + (1 - w) ** 2 * se_mu2)
        out[c] = {"n": len(effects[c]), "raw": means[c], "score": score,
                  "lo": score - 1.96 * sd, "hi": score + 1.96 * sd}
    return out


def prior(effects: dict[str, list[float]]) -> dict:
    """Score for a creator with NO measured sponsored posts: the overall mean,
    with an interval wide enough for any creator drawn from the population."""
    _, _, _, mu, tau2, se_mu2 = _pool(effects)
    sd = math.sqrt(tau2 + se_mu2)
    return {"n": 0, "raw": float("nan"), "score": mu, "lo": mu - 1.96 * sd, "hi": mu + 1.96 * sd}


def typical_log_engagement(recent: list[Post], preferred_fmt: str, min_posts: int = 3):
    """Mean log(engagement + 1) of recent ordinary posts in the preferred format,
    falling back to all formats when that format has too few.
    Returns (value, n_posts, format_used) or None."""
    ordinary = [p for p in recent if not p.sponsored]
    same = [p for p in ordinary if p.fmt == preferred_fmt]
    use, fmt = (same, preferred_fmt) if len(same) >= min_posts else (ordinary, "all")
    if len(use) < min_posts:
        return None
    return statistics.mean(math.log(max(p.engagement, 0) + 1) for p in use), len(use), fmt


def overall(effects: dict[str, list[float]], B: int = 1000, seed: int = 0) -> dict:
    """Mean effect over all posts, with a creator-level bootstrap interval."""
    creators = [c for c, v in effects.items() if v]
    flat = [x for c in creators for x in effects[c]]
    if not flat:
        return {"mean": float("nan"), "lo": float("nan"), "hi": float("nan"), "n_posts": 0, "n_creators": 0}
    rng = random.Random(seed)
    boots = []
    for _ in range(B):
        pick = [rng.choice(creators) for _ in creators]
        vals = [x for c in pick for x in effects[c]]
        boots.append(statistics.mean(vals))
    boots.sort()
    return {"mean": statistics.mean(flat), "median": statistics.median(flat),
            "share_positive": sum(x > 0 for x in flat) / len(flat),
            "lo": boots[int(0.025 * B)], "hi": boots[int(0.975 * B) - 1],
            "n_posts": len(flat), "n_creators": len(creators)}
