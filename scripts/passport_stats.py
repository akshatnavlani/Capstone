"""Pure statistics behind the Creator Passport (1 Nov 2026). No database, no I/O: scripts/build_creator_passport.py feeds these functions and tests/test_passport_stats.py checks them.

MOOD GAP      score is the average of P(positive) + 0.5 P(neutral) per comment, in 0..1. Only the mean and the number of comments are stored, so the standard error is bounded by the
              worst case 0.5 / sqrt(n); a gap is flagged only when it clears 1.96 standard errors AND is at least MIN_GAP. This is conservative on purpose.
PENALTY       sponsored-post response by platform: each sponsored post is compared with the same creator's ORGANIC posts of the same format within a time window (same creator, same format,
              nearby dates, so audience size, format and trend cancel). Per creator: the median difference in log engagement; pooled: the mean over creators with a bootstrap over creators.
              A placebo (fake sponsored posts drawn from organic ones) shows what the method gives when nothing is going on.
PREDICTION    leave-one-out ridge regression of a creator's Instagram level from YouTube features, scored against a subscriber-only baseline.
"""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np

MIN_GAP = 0.10
MIN_ORGANIC = 3


def mood_gap(yt: float, n_yt: int, ig: float, n_ig: int) -> dict:
    """Instagram minus YouTube comment mood. `significant` needs |gap| >= MIN_GAP and |z| >= 1.96 under the worst-case standard error."""
    gap = ig - yt
    se = math.sqrt(0.25 / max(n_yt, 1) + 0.25 / max(n_ig, 1))
    z = gap / se
    significant = abs(gap) >= MIN_GAP and abs(z) >= 1.96
    if not significant:
        label = "no clear gap"
    elif gap > 0:
        label = "warmer on Instagram than on YouTube"
    else:
        label = "warmer on YouTube than on Instagram"
    return {"gap": round(gap, 3), "se_worst_case": round(se, 3), "z": round(z, 2), "significant": significant, "label": label}


def matched_differences(sponsored: Sequence[tuple[float, str, float]], organic: Sequence[tuple[float, str, float]], window_days: float) -> list[float]:
    """One difference per sponsored post: its log engagement minus the median log engagement of the creator's organic posts of the same format within +/- window_days.
    Items are (day, format, log_engagement). Sponsored posts with fewer than MIN_ORGANIC matches are skipped."""
    out = []
    for day, fmt, y in sponsored:
        near = [oy for od, of, oy in organic if of == fmt and abs(od - day) <= window_days]
        if len(near) >= MIN_ORGANIC:
            out.append(y - float(np.median(near)))
    return out


def pooled(per_creator: Sequence[float], draws: int = 2000, seed: int = 0) -> dict:
    """Mean over creators with a 95% bootstrap interval over creators."""
    v = np.asarray(per_creator, float)
    if len(v) < 3:
        return {"creators": int(len(v)), "mean": None, "ci95": None}
    rng = np.random.default_rng(seed)
    boots = np.array([rng.choice(v, len(v), replace=True).mean() for _ in range(draws)])
    return {"creators": int(len(v)), "mean": round(float(v.mean()), 4), "ci95": [round(float(np.quantile(boots, 0.025)), 4), round(float(np.quantile(boots, 0.975)), 4)]}


def placebo_pooled(by_creator_organic: dict[str, list[tuple[float, str, float]]], by_creator_n_sponsored: dict[str, int], window_days: float, runs: int = 200, seed: int = 0) -> dict:
    """Fake sponsored posts: for each creator draw as many ORGANIC posts as the creator has sponsored ones, treat them as sponsored and the rest as organic. The pooled mean over many
    draws should centre on 0; its spread is the noise of the method."""
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(runs):
        per = []
        for c, org in by_creator_organic.items():
            k = by_creator_n_sponsored.get(c, 0)
            if k < 3 or len(org) < k + MIN_ORGANIC:
                continue
            idx = rng.choice(len(org), k, replace=False)
            fake = [org[i] for i in idx]
            rest = [o for i, o in enumerate(org) if i not in set(idx.tolist())]
            d = matched_differences(fake, rest, window_days)
            if len(d) >= 3:
                per.append(float(np.median(d)))
        if per:
            means.append(float(np.mean(per)))
    if not means:
        return {"runs": 0, "mean": None, "ci95": None}
    return {"runs": len(means), "mean": round(float(np.mean(means)), 4), "ci95": [round(float(np.quantile(means, 0.025)), 4), round(float(np.quantile(means, 0.975)), 4)]}


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    ra = np.argsort(np.argsort(np.asarray(a, float))).astype(float)
    rb = np.argsort(np.argsort(np.asarray(b, float))).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def _ridge_fit(X: np.ndarray, y: np.ndarray, lam: float):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    A = np.c_[np.ones(len(Z)), Z]
    eye = np.eye(A.shape[1])
    eye[0, 0] = 0.0
    beta = np.linalg.solve(A.T @ A + lam * eye, A.T @ y)
    return mu, sd, beta


def _ridge_predict(model, X: np.ndarray) -> np.ndarray:
    mu, sd, beta = model
    return np.c_[np.ones(len(X)), (X - mu) / sd] @ beta


def loo_ridge(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    """Leave-one-creator-out predictions."""
    out = np.zeros(len(y))
    for i in range(len(y)):
        keep = np.arange(len(y)) != i
        out[i] = _ridge_predict(_ridge_fit(X[keep], y[keep], lam), X[i:i + 1])[0]
    return out


def prediction_report(X: np.ndarray, y: np.ndarray, size_col: int, lam: float = 5.0) -> dict:
    """Leave-one-out accuracy of the full model against two baselines: the average, and a size-only ridge on one column (the creator's YouTube size)."""
    full = loo_ridge(X, y, lam)
    size = loo_ridge(X[:, [size_col]], y, 1e-6)
    mean = np.array([y[np.arange(len(y)) != i].mean() for i in range(len(y))])
    mae = lambda p: float(np.mean(np.abs(p - y)))  # noqa: E731
    return {"n": int(len(y)), "mae_average": round(mae(mean), 4), "mae_size_only": round(mae(size), 4), "mae_full": round(mae(full), 4),
            "spearman_size_only": round(spearman(size, y), 3), "spearman_full": round(spearman(full, y), 3),
            "beats_size_only": bool(mae(full) < mae(size) - 0.02), "residual_p10_p90": [round(float(np.quantile(y - full, 0.1)), 3), round(float(np.quantile(y - full, 0.9)), 3)]}
