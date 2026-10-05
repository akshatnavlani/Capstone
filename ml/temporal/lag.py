"""Cross-platform lag detection (PendingWork S1; the 12-24 hour hypothesis).

`lag_profile` is the correlation between series x (e.g. YouTube activity) and
series y (e.g. Reddit activity) at each lag; a positive lag means y trails x.
Per-creator series are too sparse to test alone, so `pooled_lag_test` averages
the profile across creators and gets a p-value from a circular-shift null,
which keeps each series' own autocorrelation and needs no distribution
assumption. The statistic is the largest absolute pooled correlation over all
lags, so the p-value already accounts for having searched every lag.

Lags are in bins. Convert with bin_hours (lag of 1 bin at bin_hours=12 is 12h).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def lag_profile(x: np.ndarray, y: np.ndarray, max_lag: int) -> np.ndarray:
    """Correlation of x[t] with y[t + lag] for lag in -max_lag..max_lag."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    out = []
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            out.append(_corr(x[: n - lag], y[lag:]))
        else:
            out.append(_corr(x[-lag:], y[: n + lag]))
    return np.array(out)


def _pooled(pairs, max_lag: int, shifts=None) -> np.ndarray:
    profiles = []
    for k, (x, y) in enumerate(pairs):
        y_used = y if shifts is None else np.roll(y, shifts[k])
        profiles.append(lag_profile(x, y_used, max_lag))
    with np.errstate(all="ignore"):
        return np.nanmean(np.vstack(profiles), axis=0)


@dataclass
class LagResult:
    lags: np.ndarray
    profile: np.ndarray
    best_lag: int
    best_corr: float
    p_value: float
    n_pairs: int


def pooled_lag_test(
    pairs: list[tuple[np.ndarray, np.ndarray]],
    max_lag: int,
    n_perm: int = 500,
    seed: int = 0,
    min_len: int = 10,
) -> LagResult:
    """Pooled lag profile over (x, y) pairs plus a family-wise p-value."""
    usable = [
        (np.asarray(x, float), np.asarray(y, float))
        for x, y in pairs
        if len(x) == len(y) and len(x) >= min_len and np.std(x) > 0 and np.std(y) > 0
    ]
    if not usable:
        raise ValueError("no usable series pairs (need equal length, >= min_len, non-constant)")

    lags = np.arange(-max_lag, max_lag + 1)
    observed = _pooled(usable, max_lag)
    obs_stat = np.nanmax(np.abs(observed))

    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(n_perm):
        shifts = [int(rng.integers(1, len(y))) for _, y in usable]
        null = _pooled(usable, max_lag, shifts)
        if np.nanmax(np.abs(null)) >= obs_stat:
            exceed += 1
    p_value = (1 + exceed) / (1 + n_perm)

    best = int(np.nanargmax(np.abs(observed)))
    return LagResult(lags, observed, int(lags[best]), float(observed[best]), p_value, len(usable))
