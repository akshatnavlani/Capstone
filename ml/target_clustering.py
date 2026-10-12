"""Stop counting one engagement change as many training examples.

THE PROBLEM. `compute_training_pair_deltas.py` measured a neighbour's
engagement lift around a sponsorship event with UNBOUNDED windows:

    before = [posts where date < event_date]      # all history
    after  = [posts where date > event_date]      # all history

Every event on the same neighbour therefore splits that neighbour's whole post
history at a slightly different point. Two events a week apart produce before/
after sets that overlap almost entirely, so both record the same underlying
change. Virat Kohli's Reddit engagement rose around 2026-08-05 for reasons
unrelated to any sponsorship; 16 separate events straddled that date, and the
dataset recorded 16 "lifts" that are one jump measured 16 times.

Averaging per creator (the previous workaround) hides this but overcorrects: it
also merges events months apart, which are closer to genuinely independent.

THE FIX, IN TWO PARTS. Both are needed; either alone fails.

  1. `windowed_engagement` bounds each measurement to +/- `window_days` around
     the event. Distant events then measure genuinely different periods.

  2. `cluster_events` groups events on the same neighbour whose windows still
     overlap, and `cluster_weights` gives each row 1/cluster_size so a cluster
     contributes one unit of evidence however many rows it spans.

Without (1), every pair of events on a neighbour overlaps and clustering
collapses to one row per creator -- identical to the averaging it replaces.
Without (2), events a few days apart are still counted twice.

CLUSTERING RULE. Single-linkage on the time axis: events on the same neighbour
join the same cluster when consecutive event dates are within `window_days` of
each other. Single-linkage is the right choice because overlap is transitive in
effect -- if A overlaps B and B overlaps C, all three are measuring a shared
stretch of that creator's timeline even when A and C do not touch directly.

WHAT THIS IS NOT. Clustering cannot create information. It stops one change
being counted many times; it does not produce new independent observations. The
route to a genuinely larger sample is counting training pairs through
`co_occurs_with` edges as well as `collaborates_with`, which the pair-count
script does not yet do.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable, Sequence

# Half-width of the measurement window, in days. 30 is a starting value, not a
# fitted one: it is wide enough to catch several posts from a creator posting
# weekly, and narrow enough that events a quarter apart do not overlap. Any
# change here changes both the targets and the clustering, so it belongs in the
# write-up as a stated hyperparameter.
DEFAULT_WINDOW_DAYS = 30


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def windowed_engagement(
    dated_values: Sequence[tuple[date | datetime, float]],
    event_date: date | datetime,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> tuple[list[float], list[float]]:
    """Engagement values in a bounded window either side of the event.

    Args:
        dated_values: (date, engagement) pairs for ONE creator on ONE platform.
        event_date: when the sponsorship event happened.
        window_days: half-width of the window, in days.

    Returns:
        (before, after). `before` covers [event - window, event), `after`
        covers (event, event + window]. The event date itself is in neither:
        a post made the same day may be the sponsored post, and counting it on
        the "after" side would leak the treatment into its own outcome.
    """
    anchor = _as_date(event_date)
    lo = anchor - timedelta(days=window_days)
    hi = anchor + timedelta(days=window_days)

    before, after = [], []
    for raw_date, value in dated_values:
        d = _as_date(raw_date)
        if lo <= d < anchor:
            before.append(value)
        elif anchor < d <= hi:
            after.append(value)
    return before, after


def cluster_events(
    rows: Iterable[dict],
    window_days: int = DEFAULT_WINDOW_DAYS,
    neighbour_key: str = "neighbour_id",
    date_key: str = "event_date",
) -> list[str]:
    """Assign each row a cluster id. Rows sharing an id measure the same change.

    Single-linkage on the time axis, per neighbour: events are sorted by date
    and a new cluster starts whenever the gap to the previous event exceeds
    `window_days`.

    Args:
        rows: dicts carrying at least a neighbour id and an event date. Dates
            may be `date`, `datetime`, or an ISO-8601 string.
        window_days: same half-width used for the measurement windows.

    Returns:
        A cluster id per row, in the input order, shaped
        "<neighbour_id>#<n>". Rows with a missing or unparseable date each get
        their own singleton cluster: an undated event cannot be shown to
        overlap anything, and silently merging it would be the same
        over-counting error in reverse.
    """
    rows = list(rows)
    by_neighbour: dict[str, list[tuple[date, int]]] = defaultdict(list)
    cluster_of: list[str | None] = [None] * len(rows)

    for i, row in enumerate(rows):
        neighbour = str(row.get(neighbour_key, ""))
        parsed = _parse_date(row.get(date_key))
        if parsed is None or not neighbour:
            cluster_of[i] = f"{neighbour or 'unknown'}#solo{i}"
        else:
            by_neighbour[neighbour].append((parsed, i))

    for neighbour, entries in by_neighbour.items():
        entries.sort()
        index = 0
        previous: date | None = None
        for event_day, row_index in entries:
            if previous is not None and (event_day - previous).days > window_days:
                index += 1
            cluster_of[row_index] = f"{neighbour}#{index}"
            previous = event_day

    return [c for c in cluster_of if c is not None]


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        return None


def cluster_weights(cluster_ids: Sequence[str]) -> list[float]:
    """Per-row weight so each cluster contributes one unit of evidence total.

    A neighbour with 16 rows in one cluster gets 1/16 each; a neighbour with a
    single row gets 1.0. Summed over all rows, the total equals the number of
    distinct clusters -- which is the honest effective sample size.
    """
    sizes: dict[str, int] = defaultdict(int)
    for cid in cluster_ids:
        sizes[cid] += 1
    return [1.0 / sizes[cid] for cid in cluster_ids]


def effective_sample_size(cluster_ids: Sequence[str]) -> int:
    """Number of distinct clusters: the count to quote, not the row count."""
    return len(set(cluster_ids))


def summarize(cluster_ids: Sequence[str]) -> dict:
    """Row count, cluster count, and the largest clusters.

    `largest` is what exposes a Kohli-shaped problem at a glance: a cluster
    holding a large share of the rows means one engagement change is dominating
    the dataset.
    """
    sizes: dict[str, int] = defaultdict(int)
    for cid in cluster_ids:
        sizes[cid] += 1
    ordered = sorted(sizes.items(), key=lambda kv: -kv[1])
    return {
        "rows": len(cluster_ids),
        "clusters": len(sizes),
        "largest": ordered[:5],
        "max_cluster_share": (ordered[0][1] / len(cluster_ids)) if cluster_ids else 0.0,
    }

def per_creator_targets(
    rows: Iterable[dict],
    window_days: int = DEFAULT_WINDOW_DAYS,
    neighbour_key: str = "neighbour_id",
    date_key: str = "event_date",
    value_key: str = "mean_lift",
) -> dict[str, tuple[float, int]]:
    """Collapse rows to one target per creator, plus how much evidence backs it.

    Two levels of averaging, and the distinction matters:

      within a cluster  rows measure the SAME engagement change, so averaging
                        them is just a less noisy reading of one observation
      across clusters   each cluster is a separate observation, so averaging
                        these combines genuinely independent evidence

    Returns {neighbour_id: (target, n_clusters)}. `n_clusters` is the honest
    count of independent observations behind that creator's target, and is what
    `sample_weight` in the loss should be built from: a creator backed by three
    separate events deserves more influence on training than one backed by a
    single event measured sixteen times.

    Rows whose `value_key` is None (cross-platform-only straddles, which have no
    same-platform lift) are skipped rather than counted as zero.
    """
    rows = [r for r in rows if r.get(value_key) is not None]
    if not rows:
        return {}

    cluster_ids = cluster_events(
        rows, window_days=window_days, neighbour_key=neighbour_key, date_key=date_key
    )

    # cluster id -> values measured within it
    by_cluster: dict[str, list[float]] = defaultdict(list)
    cluster_owner: dict[str, str] = {}
    for row, cid in zip(rows, cluster_ids):
        by_cluster[cid].append(float(row[value_key]))
        cluster_owner[cid] = str(row.get(neighbour_key, ""))

    # creator -> one value per cluster
    per_creator: dict[str, list[float]] = defaultdict(list)
    for cid, values in by_cluster.items():
        per_creator[cluster_owner[cid]].append(sum(values) / len(values))

    return {
        creator: (sum(vals) / len(vals), len(vals))
        for creator, vals in per_creator.items()
    }