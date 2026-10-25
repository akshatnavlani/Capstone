"""Treatment that matches the time of the outcome it is supposed to explain.

P2 -- TIME-INDEXED TREATMENT. `load_treatment` marked a creator sponsored if
they had a sponsorship event at ANY point in the data (up to ~1,650 days). Each
training target, though, is an engagement lift measured in a +/-30-day window
around one event. A neighbour sponsored two years earlier contributed exposure
to a lift it could not have caused. Here, an observation's exposure counts only
creators with a sponsorship event inside the span that observation measures.

P2b -- NO SELF-SPONSORSHIP IN THE WINDOW. The lift is meant to be SPILLOVER:
the change in a neighbour's engagement caused by someone ELSE's sponsorship. If
the neighbour ran their own sponsored post inside the same window, the lift
mixes in their direct effect. Seen in the data: LeBron James and Cristiano
Ronaldo posted the same Nike campaign on the same day, so each was the other's
"spillover"; Karan Johar ran six campaigns in four weeks. Such rows are dropped
and counted, not reweighted -- there is no clean way to subtract a direct
effect we do not model.

OBSERVATIONS. Rows are clustered exactly as in `ml.target_clustering` (events on
the same neighbour whose windows overlap measure the same engagement change).
Each cluster becomes one `Observation`, carrying the span its measurements
cover, from the first event's window start to the last event's window end. That
span is what its treatment vector is built from. Observations, not creators, are
now the unit of supervision: a creator measured in March and again in August
has two observations with two different treatment vectors, which a single
per-creator target could not represent.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Iterable, Sequence

import torch

from ml.target_clustering import DEFAULT_WINDOW_DAYS, _parse_date, cluster_events


@dataclass(frozen=True)
class Observation:
    """One independent engagement-change measurement on one neighbour."""

    neighbour_id: str
    value: float
    start: date  # earliest day any of its measurement windows covers
    end: date  # latest day any of its measurement windows covers
    n_rows: int
    cluster_id: str
    # P3. The dates the lift was measured around, so controls can be measured
    # around the SAME dates; and whether this is an exposed (treated) or a
    # control observation.
    event_dates: tuple[date, ...] = ()
    exposed: bool = True

    @property
    def span(self) -> tuple[date, date]:
        return (self.start, self.end)


def sponsorship_dates(rows: Iterable[tuple[str, object]]) -> dict[str, list[date]]:
    """(creator_id, posted_at) rows -> sorted sponsorship dates per creator.

    Undated rows are skipped: without a date an event cannot be placed in any
    window, which is the same rule `pair_count` applies to events.
    """
    out: dict[str, list[date]] = defaultdict(list)
    for creator_id, posted_at in rows:
        d = _parse_date(posted_at)
        if creator_id is not None and d is not None:
            out[str(creator_id)].append(d)
    return {k: sorted(v) for k, v in out.items()}


def treatment_in_span(
    dates_by_creator: dict[str, Sequence[date]],
    id_to_index: dict[str, int],
    num_nodes: int,
    start: date,
    end: date,
) -> torch.Tensor:
    """(num_nodes,) float: 1.0 for creators with a sponsorship in [start, end]."""
    t = torch.zeros(num_nodes, dtype=torch.float32)
    for creator_id, dates in dates_by_creator.items():
        idx = id_to_index.get(creator_id)
        if idx is not None and any(start <= d <= end for d in dates):
            t[idx] = 1.0
    return t


def own_sponsorship_in_window(
    dates_by_creator: dict[str, Sequence[date]],
    creator_id: str,
    event_date,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> bool:
    """Did `creator_id` run their own sponsorship within +/-window of the event?

    Inclusive of the event day itself: the LeBron/Ronaldo case is two posts on
    the same day.
    """
    anchor = _parse_date(event_date)
    if anchor is None:
        return False
    lo, hi = anchor - timedelta(days=window_days), anchor + timedelta(days=window_days)
    return any(lo <= d <= hi for d in dates_by_creator.get(str(creator_id), ()))


def drop_self_sponsored(
    rows: Sequence[dict],
    dates_by_creator: dict[str, Sequence[date]],
    window_days: int = DEFAULT_WINDOW_DAYS,
    neighbour_key: str = "neighbour_id",
    date_key: str = "event_date",
) -> tuple[list[dict], list[dict]]:
    """Split rows into (kept, dropped) by the P2b rule."""
    kept, dropped = [], []
    for row in rows:
        if own_sponsorship_in_window(
            dates_by_creator, row.get(neighbour_key), row.get(date_key), window_days
        ):
            dropped.append(row)
        else:
            kept.append(row)
    return kept, dropped


def build_observations(
    rows: Sequence[dict],
    window_days: int = DEFAULT_WINDOW_DAYS,
    value_key: str = "robust_lift",
    neighbour_key: str = "neighbour_id",
    date_key: str = "event_date",
) -> list[Observation]:
    """Cluster rows (same rule as E2) and return one Observation per cluster.

    The value is the mean of the cluster's rows: they are repeated readings of
    one engagement change. Rows with no value or no parseable date are skipped;
    an undated row has no span to build treatment from.
    """
    rows = [
        r for r in rows
        if r.get(value_key) is not None and _parse_date(r.get(date_key)) is not None
    ]
    if not rows:
        return []
    cluster_ids = cluster_events(
        rows, window_days=window_days, neighbour_key=neighbour_key, date_key=date_key
    )
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row, cid in zip(rows, cluster_ids):
        grouped[cid].append(row)

    pad = timedelta(days=window_days)
    out = []
    for cid, members in grouped.items():
        dates = [_parse_date(m[date_key]) for m in members]
        out.append(
            Observation(
                neighbour_id=str(members[0][neighbour_key]),
                value=sum(float(m[value_key]) for m in members) / len(members),
                start=min(dates) - pad,
                end=max(dates) + pad,
                n_rows=len(members),
                cluster_id=cid,
                event_dates=tuple(sorted(set(dates))),
            )
        )
    return sorted(out, key=lambda o: (o.start, o.neighbour_id))


def _overlaps(a: tuple[date, date], b: tuple[date, date]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def build_control_observations(
    windows: Sequence[tuple[tuple[date, date], Sequence[date], Iterable[str]]],
    lift_fn: Callable[[str, date], float | None],
    reserved_spans: dict[str, list[tuple[date, date]]] | None = None,
) -> list[Observation]:
    """P3. Unexposed observations measured around the treated windows' dates.

    WHY. Every treated observation has a sponsored neighbour by construction,
    so without these the model never sees T = 0 data: the control arm of the
    doubly robust estimator is identically zero and mu(0, X) is fitted to
    nothing. A control is a creator with NO sponsored neighbour and NO own
    sponsorship in the window, measured over the SAME calendar dates, so
    seasonality and platform-wide trends hit both groups alike -- a
    difference-in-differences design.

    Args:
        windows: (span, event_dates, eligible_creator_ids) per treatment window.
            Eligibility (unexposed, not self-sponsored) is decided by the caller,
            which holds the graph and the treatment vector for that span.
        lift_fn: (creator_id, event_date) -> lift or None, computed exactly as
            for treated rows.
        reserved_spans: spans already used per creator (their treated
            observations). A control must not overlap them.

    INDEPENDENCE. Same rule as E2: one creator's overlapping windows measure
    one engagement change. Windows are processed in time order and a creator is
    used as a control only if the span overlaps none of that creator's earlier
    spans, treated or control. Greedy, so the earliest window wins; stated, not
    tuned.
    """
    used: dict[str, list[tuple[date, date]]] = defaultdict(list)
    for creator, spans in (reserved_spans or {}).items():
        used[creator].extend(spans)

    out = []
    for k, (span, event_dates, eligible) in enumerate(sorted(windows, key=lambda w: w[0])):
        for creator in sorted(eligible):
            if any(_overlaps(span, s) for s in used[creator]):
                continue
            lifts = [v for d in event_dates if (v := lift_fn(creator, d)) is not None]
            if not lifts:
                continue
            used[creator].append(span)
            out.append(
                Observation(
                    neighbour_id=creator,
                    value=sum(lifts) / len(lifts),
                    start=span[0],
                    end=span[1],
                    n_rows=len(lifts),
                    cluster_id=f"{creator}#ctrl{k}",
                    event_dates=tuple(event_dates),
                    exposed=False,
                )
            )
    return out


def matched_did(observations: Iterable[Observation]) -> dict:
    """Calendar-matched difference-in-differences, no model involved.

    Each lift is already a before/after change. Within each window, the effect
    estimate is mean(exposed lift) - mean(control lift); windows are averaged
    weighted by their number of exposed observations, so the estimate is an
    effect on the exposed.

    SE: sum of w_p^2 * (var_t / n_t,p + var_c,p / n_c,p). var_t is pooled over
    all exposed observations, because most windows hold one; var_c,p is the
    window's own control variance, falling back to pooled. Assumes independent
    observations -- a floor on the true uncertainty, like the AIPW SE.

    Windows with no control are left out and counted, never filled with zero.
    `median_estimate` repeats the calculation with within-window medians.
    """
    by_span: dict[tuple[date, date], list[Observation]] = defaultdict(list)
    for o in observations:
        by_span[o.span].append(o)

    def _var(xs: list[float]) -> float | None:
        if len(xs) < 2:
            return None
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)

    treated_all = [o.value for group in by_span.values() for o in group if o.exposed]
    control_all = [o.value for group in by_span.values() for o in group if not o.exposed]
    var_t = _var(treated_all) or 0.0
    var_c_pooled = _var(control_all) or 0.0

    parts, skipped = [], 0
    for group in by_span.values():
        t = [o.value for o in group if o.exposed]
        c = [o.value for o in group if not o.exposed]
        if not t:
            continue
        if not c:
            skipped += len(t)
            continue
        var_c = _var(c)
        parts.append((len(t), sum(t) / len(t) - sum(c) / len(c), len(c),
                      var_c if var_c is not None else var_c_pooled,
                      statistics.median(t) - statistics.median(c)))

    n_t = sum(p[0] for p in parts)
    if not n_t:
        return {"estimate": float("nan"), "se": float("nan"),
                "median_estimate": float("nan"), "n_treated": 0,
                "n_control": 0, "windows": 0, "treated_without_control": skipped}
    est = sum(p[0] * p[1] for p in parts) / n_t
    var = sum((p[0] / n_t) ** 2 * (var_t / p[0] + p[3] / p[2]) for p in parts)
    return {
        "estimate": est,
        "se": var ** 0.5,
        # P3b. Same weighting, medians within each window: one extreme creator
        # cannot move it. No SE; read it as a robustness check on `estimate`.
        "median_estimate": sum(p[0] * p[4] for p in parts) / n_t,
        "n_treated": n_t,
        "n_control": sum(p[2] for p in parts),
        "windows": len(parts),
        "treated_without_control": skipped,
    }


def group_by_span(observations: Iterable[Observation]) -> dict[tuple[date, date], list[Observation]]:
    """Observations sharing a span share a treatment vector, so one pass each."""
    out: dict[tuple[date, date], list[Observation]] = defaultdict(list)
    for obs in observations:
        out[obs.span].append(obs)
    return dict(out)
