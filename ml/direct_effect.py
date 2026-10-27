"""Direct effect: how a creator's OWN audience responds to their sponsored posts.

ESTIMAND. For a sponsored post p by creator c on platform k:

    effect(p) = log( (eng(p) + 1) / (median eng of c's non-sponsored posts on k
                                      within +-window days of p) + 1 )

The baseline is the same creator (audience size, niche and style cancel) at
nearby dates (slow trends cancel). The identifying assumption: had p not been
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


def _day(d) -> date:
    return d.date() if isinstance(d, datetime) else d


def post_effect(post: Post, same_creator_platform: list[Post], window_days: int = 30,
                min_baseline: int = MIN_BASELINE_POSTS) -> float | None:
    """Log ratio of the post's engagement to the median of nearby ordinary posts."""
    lo, hi = post.day - timedelta(days=window_days), post.day + timedelta(days=window_days)
    base = [q.engagement for q in same_creator_platform
            if not q.sponsored and q.post_id != post.post_id and lo <= q.day <= hi]
    if len(base) < min_baseline:
        return None
    return math.log((max(post.engagement, 0) + 1) / (max(statistics.median(base), 0) + 1))


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


def shrink(effects: dict[str, list[float]]) -> dict[str, dict]:
    """Normal-normal empirical Bayes per creator.

    Within-creator variance is pooled across creators (one-post creators have
    none of their own); between-creator variance tau^2 by method of moments,
    floored at 0. Returns {creator: {n, raw, score, lo, hi}}.
    """
    creators = [c for c, v in effects.items() if v]
    if not creators:
        return {}
    means = {c: statistics.mean(effects[c]) for c in creators}
    resid = [x - means[c] for c in creators for x in effects[c]]
    n_tot = sum(len(effects[c]) for c in creators)
    dof = n_tot - len(creators)
    s2 = sum(r * r for r in resid) / dof if dof > 0 else statistics.pvariance([x for c in creators for x in effects[c]])
    se2 = {c: s2 / len(effects[c]) for c in creators}
    mu = sum(means[c] / se2[c] for c in creators) / sum(1 / se2[c] for c in creators)
    tau2 = max(0.0, statistics.mean([(means[c] - mu) ** 2 - se2[c] for c in creators])) if len(creators) > 1 else 0.0
    se_mu2 = 1 / sum(1 / se2[c] for c in creators)   # uncertainty of the overall mean
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
