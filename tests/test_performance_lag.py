"""Tests for ml/temporal/performance_lag.py (same-creator cross-platform performance lag)."""

import numpy as np
import pytest

from ml.temporal.performance_lag import daily_series, lagged_pairs, performance_lag_test, performance_scores


def test_performance_scores_remove_the_age_effect():
    rng = np.random.default_rng(0)
    age = np.linspace(1, 300, 60)
    comments = np.exp(0.8 * np.log1p(age) + rng.normal(0, 0.3, 60))  # older posts simply have more
    z = performance_scores(comments, age)
    assert z.mean() == pytest.approx(0.0, abs=1e-9) and z.std() == pytest.approx(1.0)
    assert abs(np.corrcoef(z, np.log1p(age))[0, 1]) < 0.05  # age explains nothing after adjustment


def test_performance_scores_need_enough_posts_and_spread():
    assert performance_scores([5, 6, 7], [1, 2, 3]) is None
    assert performance_scores([4] * 20, list(range(20))) is None


def test_daily_series_averages_posts_on_the_same_day():
    assert daily_series(np.array([3, 3, 4]), np.array([1.0, 3.0, 5.0])) == {3: 2.0, 4: 5.0}


def test_lagged_pairs_pairs_x_on_day_d_with_y_on_day_d_plus_k():
    x = {1: 1.0, 2: 2.0}
    y = {2: 10.0, 4: 20.0}
    assert lagged_pairs(x, y, 1) == [(1.0, 10.0)]
    assert lagged_pairs(x, y, 2) == [(2.0, 20.0)]
    assert lagged_pairs(x, y, 0) == [(2.0, 10.0)]


def _creators(rng, n=10, days=80, effect=0.0, lag=1):
    out = []
    for _ in range(n):
        x = {int(d): float(rng.normal()) for d in rng.choice(days, 30, replace=False)}
        y = {}
        for d in rng.choice(days, 30, replace=False):
            y[int(d)] = float(rng.normal())
        for d, v in x.items():  # plant: Y trails X by `lag` days
            if effect and d + lag < days + 5:
                y[d + lag] = effect * v + float(rng.normal(0, 0.3))
        out.append((x, y))
    return out


def test_planted_next_day_lag_is_found_at_lag_one_only():
    res = performance_lag_test(_creators(np.random.default_rng(1), effect=0.9, lag=1), n_placebo=300, seed=2)
    i1, i0 = res.lags.index(1), res.lags.index(0)
    assert res.corr[i1] > 0.5 and res.p_values[i1] < 0.02
    assert res.p_values[i0] > 0.05  # the same-day window is not special


def test_independent_series_show_no_lag():
    res = performance_lag_test(_creators(np.random.default_rng(3)), n_placebo=300, seed=4)
    assert min(res.p_values) > 0.01
    assert max(abs(c) for c in res.corr if not np.isnan(c)) < 0.35
