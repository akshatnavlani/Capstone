"""Event-study lag test (PendingWork S1, collaborator version of the 12-24 hour hypothesis).

Question: after creator A posts a sponsored / collaboration post at time t0, does their
collaborator B show more activity on some platform in the following hours or days than B
normally does?

For each (A's event, B) pair we count B's activity in windows laid out around t0, subtract
B's own average count in the pre-event windows (so a busy creator is not mistaken for a
reacting one), and average the excess over pairs. A placebo test gives the p-value: the same
statistic is recomputed with t0 replaced by random times inside B's own observed period, so
the null keeps each creator's activity rate and burstiness.

Times are in hours (any common epoch). `edges` are the window boundaries relative to t0, e.g.
[-72, -48, -24, 0, 24, 48, 72] for day windows: windows 0..2 are before, 3..5 are after.
Statistical significance at this sample size is suggestive, not conclusive.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Unit:
    """One (event, collaborator) pair: the event time and the collaborator's activity times."""

    t0: float
    times: np.ndarray  # sorted activity timestamps of B on the response platform
    lo: float          # first and last time B's series is observed
    hi: float


def window_counts(t0: float, times: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Number of activity times in each window [t0+edges[i], t0+edges[i+1])."""
    idx = np.searchsorted(times, t0 + np.asarray(edges, dtype=float), side="left")
    return np.diff(idx).astype(float)


def usable(unit: Unit, edges: np.ndarray, t0: float | None = None, min_events: int = 5) -> bool:
    """The whole window must lie inside B's observed period, and B must have activity at all."""
    t = unit.t0 if t0 is None else t0
    return len(unit.times) >= min_events and unit.lo <= t + edges[0] and unit.hi >= t + edges[-1]


def excess_profile(unit: Unit, edges: np.ndarray, n_pre: int, t0: float | None = None) -> np.ndarray:
    """Count in each window minus B's mean count over the first `n_pre` (pre-event) windows."""
    t = unit.t0 if t0 is None else t0
    counts = window_counts(t, unit.times, edges)
    return counts - counts[:n_pre].mean()


def pooled_excess(units: list[Unit], edges: np.ndarray, n_pre: int, t0s: list[float] | None = None) -> np.ndarray:
    """Mean excess profile over the units (use `t0s` to evaluate placebo event times)."""
    profiles = [excess_profile(u, edges, n_pre, None if t0s is None else t0s[i]) for i, u in enumerate(units)]
    return np.mean(profiles, axis=0)


@dataclass
class EventStudy:
    n_units: int
    excess: np.ndarray       # observed pooled excess per window
    p_values: np.ndarray     # one-sided placebo p per window (activity higher than placebo)
    placebo_mean: np.ndarray


def placebo_t0(unit: Unit, edges: np.ndarray, rng: np.random.Generator, guard: float) -> float | None:
    """Random event time inside B's observed period, whole window covered, away from the real event."""
    lo, hi = unit.lo - edges[0], unit.hi - edges[-1]
    if hi <= lo:
        return None
    for _ in range(50):
        t = rng.uniform(lo, hi)
        if abs(t - unit.t0) >= guard:
            return float(t)
    return None


def event_study(units: list[Unit], edges, n_pre: int, n_placebo: int = 2000, seed: int = 0, min_events: int = 5) -> EventStudy | None:
    edges = np.asarray(edges, dtype=float)
    units = [u for u in units if usable(u, edges, min_events=min_events)]
    if not units:
        return None
    observed = pooled_excess(units, edges, n_pre)
    rng = np.random.default_rng(seed)
    guard = float(edges[-1] - edges[0])
    sims = []
    for _ in range(n_placebo):
        t0s = []
        for u in units:
            t = placebo_t0(u, edges, rng, guard)
            t0s.append(u.t0 if t is None else t)  # no room for a placebo: fall back to the real time (conservative)
        sims.append(pooled_excess(units, edges, n_pre, t0s))
    sims = np.vstack(sims)
    p = (1 + (sims >= observed).sum(axis=0)) / (1 + n_placebo)
    return EventStudy(len(units), observed, p, sims.mean(axis=0))
