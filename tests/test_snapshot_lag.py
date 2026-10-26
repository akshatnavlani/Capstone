"""Tests for ml/temporal/snapshot_lag.py: the method must find an effect that is planted and stay quiet when there is none."""
import numpy as np

from ml.temporal.snapshot_lag import (WUnit, gain_points, placebo_t0, usable, weighted_event_study, window_sums)

EDGES = np.array([-48, -36, -24, -12, 0, 12, 24, 36, 48], dtype=float)
N_PRE = 4


def test_window_sums_add_the_weight_inside_each_window():
    times = np.array([1.0, 5.0, 13.0, 30.0]); weights = np.array([2.0, 3.0, 4.0, 5.0])
    sums = window_sums(0.0, times, weights, np.array([0.0, 12.0, 24.0, 36.0]))
    assert list(sums) == [5.0, 4.0, 5.0]


def test_gain_points_use_the_middle_of_the_interval_and_skip_falling_counts():
    t, g = gain_points([(0, 100), (2, 160), (4, 150), (6, 200)])
    assert list(t) == [1.0, 5.0] and list(g) == [60.0, 50.0]      # 160->150 is dropped


def test_gain_points_can_leave_out_a_videos_first_hours():
    t, g = gain_points([(0, 0), (2, 500), (4, 520), (150, 700)], published=0, min_age_hours=72)
    assert list(t) == [77.0] and list(g) == [180.0]                # only the late interval, whose middle (hour 77) is past 72 h


def _units(n_creators=8, events_per=6, effect=0.0, seed=1):
    """Creators observed for 400 hours with a steady random activity; `effect` extra weight in the 12 h after each event."""
    rng = np.random.default_rng(seed)
    out = []
    for c in range(n_creators):
        times = np.sort(rng.uniform(0, 400, 800)); weights = np.ones(800)
        events = rng.uniform(60, 340, events_per)
        extra_t, extra_w = [], []
        for e in events:
            k = int(effect * 40)
            extra_t += list(rng.uniform(e, e + 12, k)); extra_w += [1.0] * k
        t = np.concatenate([times, extra_t]); w = np.concatenate([weights, extra_w])
        order = np.argsort(t)
        out += [WUnit(float(e), t[order], w[order], 0.0, 400.0, creator=f"c{c}") for e in events]
    return out


def test_a_planted_effect_is_found_in_the_right_window():
    study = weighted_event_study(_units(effect=1.0), EDGES, N_PRE, n_placebo=300, seed=2)
    assert study.p_values[4] < 0.01                                  # window 0-12 h after the event
    assert study.excess[4] > study.excess[0]
    assert study.n_creators == 8


def test_with_no_effect_the_false_alarm_rate_stays_near_the_chosen_level():
    """Over 6 random datasets x 8 windows (48 p-values) about 5% should fall below 0.05; far more would mean the placebo is biased."""
    p = np.concatenate([weighted_event_study(_units(effect=0.0, seed=s), EDGES, N_PRE, n_placebo=200, seed=s).p_values for s in range(10, 16)])
    assert (p < 0.05).mean() < 0.17
    assert np.median(p) > 0.3


def test_units_whose_window_leaves_the_observed_period_are_dropped():
    edge_unit = WUnit(10.0, np.arange(0, 400, 1.0), np.ones(400), 0.0, 400.0)
    assert not usable(edge_unit, EDGES)
    assert weighted_event_study([edge_unit], EDGES, N_PRE, n_placebo=10) is None


def test_placebo_times_keep_the_window_inside_and_away_from_the_real_event():
    unit = WUnit(200.0, np.arange(0, 400, 1.0), np.ones(400), 0.0, 400.0)
    rng = np.random.default_rng(0)
    for _ in range(200):
        t = placebo_t0(unit, EDGES, rng, guard=48.0, same_hour=False)
        assert 48.0 <= t <= 352.0 and abs(t - 200.0) >= 48.0


def test_same_hour_placebos_move_by_whole_days_only():
    unit = WUnit(200.0, np.arange(0, 400, 1.0), np.ones(400), 0.0, 400.0)
    rng = np.random.default_rng(1)
    for _ in range(200):
        t = placebo_t0(unit, EDGES, rng, guard=48.0)
        assert (t - 200.0) % 24.0 == 0 and abs(t - 200.0) >= 48.0 and 48.0 <= t <= 352.0


def _daily_rhythm_units(n_creators=10, seed=4):
    """Activity with a strong daily peak at 20:00 of each day, and events always at 06:00 that have NO effect of their own.
    The peak lands in the window just BEFORE each event (-12..0 h), so a placebo at a random hour calls it an effect."""
    rng = np.random.default_rng(seed)
    out = []
    for c in range(n_creators):
        t = np.sort(rng.uniform(0, 480, 4000))
        keep = rng.uniform(0, 1, len(t)) < np.where(np.abs(((t % 24) - 20 + 12) % 24 - 12) < 2.5, 1.0, 0.12)
        t = t[keep]
        for day in rng.choice(np.arange(4, 16), 5, replace=False):
            out.append(WUnit(float(day * 24 + 6), t, np.ones(len(t)), 0.0, 480.0, f"c{c}"))
    return out


def test_a_daily_rhythm_is_not_mistaken_for_an_effect_when_the_placebo_keeps_the_hour():
    units = _daily_rhythm_units()
    naive = weighted_event_study(units, EDGES, N_PRE, n_placebo=300, seed=1, same_hour=False)
    fair = weighted_event_study(units, EDGES, N_PRE, n_placebo=300, seed=1, same_hour=True)
    assert naive.p_values[3] < 0.01           # the naive placebo reports the rhythm (window -12..0 h) as an effect
    assert fair.p_values[3] > 0.1             # keeping the hour of day removes it
    assert np.median(fair.p_values) > 0.2
