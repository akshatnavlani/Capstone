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

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Sequence

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
            )
        )
    return sorted(out, key=lambda o: (o.start, o.neighbour_id))


def group_by_span(observations: Iterable[Observation]) -> dict[tuple[date, date], list[Observation]]:
    """Observations sharing a span share a treatment vector, so one pass each."""
    out: dict[tuple[date, date], list[Observation]] = defaultdict(list)
    for obs in observations:
        out[obs.span].append(obs)
    return dict(out)
