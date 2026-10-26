"""Snapshot-based event-study lag test (S1, version 2, written 2026-10-21 for the data collected since 2026-10-11).

The first lag scripts could only use one number per post and Instagram dates without a time of day. We now hold exact post
times and a growth reading every 2 hours for YouTube, so the question can be asked directly: around an event at time t0
(for example one of a creator's Instagram posts), does their activity on the OTHER platform rise in the hours after it?

Activity is a list of (time, weight) points:
  * YouTube attention: views GAINED between two consecutive readings of a video, placed at the middle of the interval
    (`gain_points`). Gains on a video's first 72 hours can be left out, so that the response is attention reaching the
    creator's older videos, not the new upload itself.
  * Posting: each post is a point of weight 1.

For every (event, creator) unit the rate in each window around t0 is compared with the unit's own rate in the pre-event windows,
and divided by the unit's mean rate overall, so a busy creator is not mistaken for a reacting one. The pooled excess is then
compared with a placebo: the same statistic with every event moved to a random time inside the creator's observed period,
which keeps each creator's rate and burstiness. One-sided p (activity higher than placebo) per window.

Limits, stated with the result: units from the same creator are not independent (the placebo is per unit, so p-values are
optimistic when a creator contributes many events; `n_creators` is reported next to `n_units`); the window of observation
is short while data is still being collected.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class WUnit:
    """One (event, creator) unit: the event time and the creator's weighted activity points on the response platform."""

    t0: float
    times: np.ndarray      # sorted, hours
    weights: np.ndarray    # same length as times
    lo: float              # first and last hour at which the creator's series is observed
    hi: float
    creator: str = ""


def window_sums(t0: float, times: np.ndarray, weights: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Total weight inside each window [t0+edges[i], t0+edges[i+1])."""
    cum = np.concatenate([[0.0], np.cumsum(weights)])
    idx = np.searchsorted(times, t0 + np.asarray(edges, dtype=float), side="left")
    return np.diff(cum[idx])


def usable(unit: WUnit, edges: np.ndarray, t0: float | None = None) -> bool:
    """The whole window must lie inside the observed period, and the creator must have some activity at all."""
    t = unit.t0 if t0 is None else t0
    return len(unit.times) >= 3 and unit.weights.sum() > 0 and unit.lo <= t + edges[0] and unit.hi >= t + edges[-1]


def excess_profile(unit: WUnit, edges: np.ndarray, n_pre: int, t0: float | None = None) -> np.ndarray:
    """(rate in each window minus the mean rate of the first n_pre windows) / the unit's mean rate over its whole period."""
    t = unit.t0 if t0 is None else t0
    width = np.diff(np.asarray(edges, dtype=float))
    rates = window_sums(t, unit.times, unit.weights, edges) / width
    scale = unit.weights.sum() / max(unit.hi - unit.lo, 1e-9)
    return (rates - rates[:n_pre].mean()) / scale


def pooled_excess(units: list[WUnit], edges: np.ndarray, n_pre: int, t0s: list[float] | None = None) -> np.ndarray:
    return np.mean([excess_profile(u, edges, n_pre, None if t0s is None else t0s[i]) for i, u in enumerate(units)], axis=0)


@dataclass
class WStudy:
    n_units: int
    n_creators: int
    excess: np.ndarray          # observed pooled excess per window
    p_values: np.ndarray        # one-sided placebo p per window
    placebo_mean: np.ndarray
    placebo_sd: np.ndarray


def placebo_t0(unit: WUnit, edges: np.ndarray, rng: np.random.Generator, guard: float, same_hour: bool = True) -> float | None:
    """A placebo event time with the whole window inside the observed period and at least `guard` hours from the real event.

    same_hour=True (the default) moves the event by whole days only, so it keeps its hour of day. This matters: people post and
    watch at habitual hours, so a placebo at a random hour would compare an evening post with a 4 a.m. one and report the daily
    rhythm as an "effect" (it even showed activity BEFORE the event). same_hour=False draws any time in the period."""
    if same_hour:
        k_lo = int(np.ceil((unit.lo - edges[0] - unit.t0) / 24.0))
        k_hi = int(np.floor((unit.hi - edges[-1] - unit.t0) / 24.0))
        ks = [k for k in range(k_lo, k_hi + 1) if abs(24.0 * k) >= guard]
        return float(unit.t0 + 24.0 * rng.choice(ks)) if ks else None
    lo, hi = unit.lo - edges[0], unit.hi - edges[-1]
    if hi <= lo:
        return None
    for _ in range(50):
        t = rng.uniform(lo, hi)
        if abs(t - unit.t0) >= guard:
            return float(t)
    return None


def weighted_event_study(units: list[WUnit], edges, n_pre: int, n_placebo: int = 1000, seed: int = 0, guard: float = 48.0,
                         same_hour: bool = True) -> WStudy | None:
    """Pooled excess around the events, and a placebo p-value per window. None when no unit is usable.
    Placebo events keep their hour of day by default (see placebo_t0)."""
    edges = np.asarray(edges, dtype=float)
    units = [u for u in units if usable(u, edges)]
    if same_hour:      # a unit with no other whole day to move to cannot be compared with a placebo: leave it out
        units = [u for u in units if placebo_t0(u, edges, np.random.default_rng(0), guard, True) is not None]
    if not units:
        return None
    observed = pooled_excess(units, edges, n_pre)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_placebo):
        t0s = [placebo_t0(u, edges, rng, guard, same_hour) for u in units]
        keep = [i for i, t in enumerate(t0s) if t is not None]
        if not keep:
            continue
        draws.append(pooled_excess([units[i] for i in keep], edges, n_pre, [t0s[i] for i in keep]))
    if not draws:
        return None
    draws = np.array(draws)
    p = (1 + (draws >= observed).sum(axis=0)) / (1 + len(draws))
    return WStudy(len(units), len({u.creator for u in units}), observed, p, draws.mean(axis=0), draws.std(axis=0))


def gain_points(readings: list[tuple[float, float]], published: float | None = None, min_age_hours: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """From one video's readings [(hour, view_count)] (any order) to (times, gains): the views gained between consecutive readings,
    placed at the middle of each interval. Negative changes (a count that fell) are dropped. When `published` is given, intervals
    whose middle falls within `min_age_hours` of publication are left out."""
    pts = sorted(readings)
    times, gains = [], []
    for (t1, v1), (t2, v2) in zip(pts, pts[1:]):
        mid, gain = (t1 + t2) / 2.0, v2 - v1
        if gain < 0 or t2 <= t1:
            continue
        if published is not None and mid - published < min_age_hours:
            continue
        times.append(mid)
        gains.append(float(gain))
    return np.array(times), np.array(gains)
