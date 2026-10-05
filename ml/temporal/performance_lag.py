"""Same-creator cross-platform PERFORMANCE lag (PendingWork S1, the brand-facing question).

Question: when one creator does better than usual on platform X, do they do better than usual on
platform Y a day later? A brand could then judge a creator on combined growth, not on one platform.

Performance of a post is its comment count relative to the creator's own typical level on that
platform, after removing the effect of the post's age (older posts have collected more comments):
the standardised residual of log(1 + comments) regressed on log(1 + age in days), per creator and
platform. Posts on the same day are averaged. Lag k days: X on day d is paired with Y on day d + k,
so a positive lag means Y trails X. Pairs are pooled over creators and the pooled Pearson
correlation is tested against a placebo that circularly shifts one creator's Y dates (keeping the
values and their spacing, breaking only the alignment with X).

Statistical significance at this sample size is suggestive, not conclusive.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def performance_scores(comments, age_days, min_posts: int = 8) -> np.ndarray | None:
    """Standardised residual of log1p(comments) on log1p(age); None if too few posts or no spread."""
    y = np.log1p(np.asarray(comments, dtype=float))
    x = np.log1p(np.clip(np.asarray(age_days, dtype=float), 0, None))
    if len(y) < min_posts or y.std() == 0:
        return None
    if x.std() > 0:
        slope, intercept = np.polyfit(x, y, 1)
        y = y - (slope * x + intercept)
    return (y - y.mean()) / y.std() if y.std() > 0 else None


def daily_series(days: np.ndarray, scores: np.ndarray) -> dict[int, float]:
    """Mean score per integer day."""
    out: dict[int, list[float]] = {}
    for d, s in zip(np.asarray(days, dtype=int), scores):
        out.setdefault(int(d), []).append(float(s))
    return {d: float(np.mean(v)) for d, v in out.items()}


def lagged_pairs(x: dict[int, float], y: dict[int, float], lag: int) -> list[tuple[float, float]]:
    return [(v, y[d + lag]) for d, v in x.items() if d + lag in y]


def _pooled_corr(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 3:
        return float("nan")
    a = np.array(pairs)
    if a[:, 0].std() == 0 or a[:, 1].std() == 0:
        return float("nan")
    return float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])


@dataclass
class PerformanceLag:
    n_creators: int
    lags: list[int]
    n_pairs: list[int]
    corr: list[float]
    p_values: list[float]  # one-sided placebo p (correlation higher than chance)


def performance_lag_test(creators: list[tuple[dict[int, float], dict[int, float]]], lags=range(-3, 4),
                         n_placebo: int = 2000, seed: int = 0) -> PerformanceLag:
    """`creators` holds (x_series, y_series) per creator, each a dict day -> score."""
    lags = list(lags)
    creators = [(x, y) for x, y in creators if len(x) >= 3 and len(y) >= 3]
    obs, counts = [], []
    for k in lags:
        pairs = [p for x, y in creators for p in lagged_pairs(x, y, k)]
        obs.append(_pooled_corr(pairs))
        counts.append(len(pairs))
    rng = np.random.default_rng(seed)
    exceed = np.zeros(len(lags))
    valid = np.zeros(len(lags))
    for _ in range(n_placebo):
        shifted = []
        for x, y in creators:
            days = np.array(sorted(y))
            span = int(days[-1] - days[0]) + 1
            shift = int(rng.integers(1, max(2, span)))
            shifted.append((x, {int(days[0] + ((d - days[0] + shift) % span)): y[d] for d in days}))
        for i, k in enumerate(lags):
            c = _pooled_corr([p for x, y in shifted for p in lagged_pairs(x, y, k)])
            if not np.isnan(c) and not np.isnan(obs[i]):
                valid[i] += 1
                exceed[i] += c >= obs[i]
    p = [(1 + exceed[i]) / (1 + valid[i]) if valid[i] else float("nan") for i in range(len(lags))]
    return PerformanceLag(len(creators), lags, counts, obs, p)
