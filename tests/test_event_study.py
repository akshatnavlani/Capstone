"""Tests for ml/temporal/event_study.py (PendingWork S1 collaborator lag test).
Synthetic data only: a planted reaction must be found, a planted non-reaction must not.
"""

import numpy as np
import pytest

from ml.temporal.event_study import Unit, event_study, excess_profile, usable, window_counts

DAY = np.array([-72, -48, -24, 0, 24, 48, 72], dtype=float)  # windows 0-2 before, 3-5 after


def _unit(t0, times, lo=0.0, hi=24.0 * 200):
    return Unit(t0=float(t0), times=np.sort(np.asarray(times, dtype=float)), lo=lo, hi=hi)


def test_window_counts_uses_half_open_windows():
    times = np.array([-30.0, -24.0, 0.0, 10.0, 24.0])  # relative to t0 = 0
    counts = window_counts(0.0, times, DAY)
    assert counts.tolist() == [0, 1, 1, 2, 1, 0]  # -24 starts window 2; 0 and 10 in window 3; 24 starts window 4


def test_excess_subtracts_the_collaborators_own_pre_event_rate():
    # a busy creator: 3 posts per day before, 3 per day after -> no excess
    times = np.concatenate([[-70, -60, -50, -40, -30, -20, -10, 10, 20, 30, 50, 60, 70, 30.5]])
    u = _unit(0, times)
    prof = excess_profile(u, DAY, 3)
    assert prof[:3].mean() == pytest.approx(0.0)


def test_usable_requires_full_window_inside_observed_period_and_some_activity():
    times = np.arange(0, 100, 5.0)
    assert usable(_unit(100, times, lo=0, hi=200), DAY)
    assert not usable(_unit(100, times, lo=0, hi=150), DAY)       # window runs past the data
    assert not usable(_unit(30, times, lo=0, hi=200), DAY)        # window starts before the data
    assert not usable(_unit(100, times[:2], lo=0, hi=200), DAY)   # too few events


def _background(rng, hours=24.0 * 200, rate_per_day=2.0):
    n = rng.poisson(rate_per_day * hours / 24)
    return rng.uniform(0, hours, n)


def test_planted_next_day_reaction_is_detected():
    rng = np.random.default_rng(1)
    units = []
    for _ in range(25):
        t0 = rng.uniform(300, 4300)
        reaction = t0 + rng.uniform(24, 48, 6)  # 6 extra posts in the 24-48h window
        units.append(_unit(t0, np.concatenate([_background(rng), reaction])))
    res = event_study(units, DAY, 3, n_placebo=400, seed=2)
    assert res.n_units == 25
    assert res.excess[4] > 4.0         # window 24-48h after
    assert res.p_values[4] < 0.01
    assert res.p_values[3] > 0.05      # nothing planted in the first 24h


def test_no_reaction_gives_no_signal():
    rng = np.random.default_rng(3)
    units = [_unit(rng.uniform(300, 4300), _background(rng)) for _ in range(25)]
    res = event_study(units, DAY, 3, n_placebo=400, seed=4)
    assert res.p_values.min() > 0.01   # the whole window profile is consistent with chance
    assert abs(res.excess[3:]).max() < 1.5


def test_units_without_coverage_are_dropped_and_empty_returns_none():
    rng = np.random.default_rng(5)
    bad = _unit(10, _background(rng), lo=0, hi=50)  # window does not fit
    assert event_study([bad], DAY, 3, n_placebo=10) is None
