"""Granger causality (PendingWork S1).

Predictive only: asks whether past values of `cause` improve prediction of
`effect` beyond `effect`'s own history. It does not estimate a treatment
effect and does not need GAIL's identification assumptions; keep the two
separate in the write-up.

Implemented directly with numpy and scipy.special as the standard F-test on the
restricted (effect's own lags) vs unrestricted (plus cause's lags) regression,
the same test statsmodels reports as `ssr_ftest`. Written this way because
pandas, which statsmodels requires, is blocked by an Application Control
policy on the team's Windows machines. All lags are fitted on one shared
sample (trimmed by max_lag) so p-values are comparable across lags.
"""

from __future__ import annotations

import numpy as np


def _rss(X: np.ndarray, y: np.ndarray) -> float:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    return float(resid @ resid)


def granger_pvalues(cause, effect, max_lag: int, min_obs: int = 30) -> dict[int, float] | None:
    """F-test p-value per lag 1..max_lag, or None when the series are too
    short or constant to test (a short series gives a meaningless p-value).
    """
    from scipy.special import betainc

    cause = np.asarray(cause, dtype=float)
    effect = np.asarray(effect, dtype=float)
    ok = ~(np.isnan(cause) | np.isnan(effect))
    cause, effect = cause[ok], effect[ok]
    n_total = len(cause)
    if n_total < min_obs + 3 * max_lag or cause.std() == 0 or effect.std() == 0:
        return None

    y = effect[max_lag:]
    n = len(y)
    ones = np.ones((n, 1))
    pvalues = {}
    for lag in range(1, max_lag + 1):
        own = np.column_stack([effect[max_lag - k : n_total - k] for k in range(1, lag + 1)])
        other = np.column_stack([cause[max_lag - k : n_total - k] for k in range(1, lag + 1)])
        rss_restricted = _rss(np.hstack([ones, own]), y)
        unrestricted = np.hstack([ones, own, other])
        rss_unrestricted = _rss(unrestricted, y)
        df2 = n - unrestricted.shape[1]
        if rss_unrestricted <= 1e-12 or df2 <= 0:
            pvalues[lag] = 0.0
            continue
        F = ((rss_restricted - rss_unrestricted) / lag) / (rss_unrestricted / df2)
        # F survival function via the regularised incomplete beta function
        pvalues[lag] = float(betainc(df2 / 2.0, lag / 2.0, df2 / (df2 + lag * max(F, 0.0))))
    return pvalues


def best_lag_pvalue(pvalues: dict[int, float]) -> tuple[int, float]:
    """Smallest p-value over lags, Bonferroni-corrected for testing every lag."""
    lag = min(pvalues, key=pvalues.get)
    return lag, min(1.0, pvalues[lag] * len(pvalues))


def fisher_combine(pvalues: list[float]) -> float:
    """Combine independent per-creator p-values into one (Fisher's method)."""
    from scipy.special import gammaincc

    p = np.clip(np.asarray(pvalues, dtype=float), 1e-300, 1.0)
    # chi-square survival function via the regularised upper incomplete gamma function
    return float(gammaincc(len(p), -np.log(p).sum()))
