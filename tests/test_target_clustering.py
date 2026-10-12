"""Tests for ml.target_clustering (E2).

The test that carries the change is `test_kohli_scenario_collapses_to_one_cluster`:
it reproduces the real failure -- 16 sponsorship events straddling one engagement
jump, recorded as 16 training rows -- and checks they now count once.

Its counterpart, `test_distant_events_stay_separate`, is equally important: a fix
that merged everything would be no better than the per-creator averaging it
replaces.
"""

from __future__ import annotations

from datetime import date, datetime

from ml.target_clustering import (
    DEFAULT_WINDOW_DAYS,
    cluster_events,
    cluster_weights,
    effective_sample_size,
    summarize,
    windowed_engagement,
)

KOHLI = "kohli-uuid"
SHARMA = "sharma-uuid"


def _rows(neighbour: str, days: list[int], base: str = "2026-08-01") -> list[dict]:
    """Rows for one neighbour, at `days` offsets from a base date."""
    start = date.fromisoformat(base)
    return [
        {"neighbour_id": neighbour, "event_date": str(start.replace(day=1) if d == 0 else _shift(start, d))}
        for d in days
    ]


def _shift(d: date, days: int) -> date:
    from datetime import timedelta

    return d + timedelta(days=days)


# --- the headline case --------------------------------------------------------


def test_kohli_scenario_collapses_to_one_cluster():
    """16 events within a few weeks measure ONE engagement change."""
    rows = _rows(KOHLI, list(range(0, 32, 2)))  # 16 events, 2 days apart
    clusters = cluster_events(rows)

    assert effective_sample_size(clusters) == 1, (
        f"16 overlapping events should be one observation, got "
        f"{effective_sample_size(clusters)}"
    )
    weights = cluster_weights(clusters)
    assert all(abs(w - 1 / 16) < 1e-9 for w in weights)
    # The cluster contributes exactly one unit of evidence in total.
    assert abs(sum(weights) - 1.0) < 1e-9


def test_distant_events_stay_separate():
    """The fix must not merge genuinely independent events.

    Per-creator averaging collapsed these too; that was the overcorrection
    this module exists to avoid.
    """
    rows = _rows(KOHLI, [0, 120, 240])  # four months apart
    clusters = cluster_events(rows)
    assert effective_sample_size(clusters) == 3
    assert cluster_weights(clusters) == [1.0, 1.0, 1.0]


def test_mixed_near_and_far():
    """Two tight bursts months apart => two clusters, not one and not five."""
    rows = _rows(KOHLI, [0, 3, 6, 200, 203])
    clusters = cluster_events(rows)
    assert effective_sample_size(clusters) == 2
    weights = cluster_weights(clusters)
    assert abs(sum(weights) - 2.0) < 1e-9


# --- scoping ------------------------------------------------------------------


def test_different_neighbours_never_share_a_cluster():
    """Same dates, different creators: two independent observations."""
    rows = _rows(KOHLI, [0, 2]) + _rows(SHARMA, [0, 2])
    clusters = cluster_events(rows)
    assert effective_sample_size(clusters) == 2
    assert len(set(clusters[:2])) == 1
    assert len(set(clusters[2:])) == 1
    assert set(clusters[:2]).isdisjoint(set(clusters[2:]))


def test_single_linkage_chains_through_the_middle():
    """A overlaps B, B overlaps C, A and C do not touch -- still one cluster.

    They share a stretch of the creator's timeline, so treating them as three
    observations would be the same over-count in a subtler form.
    """
    rows = _rows(KOHLI, [0, 25, 50])  # gaps of 25 days, window 30
    assert effective_sample_size(cluster_events(rows)) == 1


def test_gap_exactly_at_the_window_does_not_split():
    rows = _rows(KOHLI, [0, DEFAULT_WINDOW_DAYS])
    assert effective_sample_size(cluster_events(rows)) == 1


def test_gap_one_day_past_the_window_splits():
    rows = _rows(KOHLI, [0, DEFAULT_WINDOW_DAYS + 1])
    assert effective_sample_size(cluster_events(rows)) == 2


def test_window_days_is_configurable():
    rows = _rows(KOHLI, [0, 45])
    assert effective_sample_size(cluster_events(rows, window_days=30)) == 2
    assert effective_sample_size(cluster_events(rows, window_days=60)) == 1


# --- bounded windows ----------------------------------------------------------


def test_windowed_engagement_excludes_distant_posts():
    """The unbounded-window bug: posts from a year away must not count."""
    data = [
        (date(2025, 1, 1), 100.0),   # a year before -- excluded
        (date(2026, 7, 20), 10.0),   # inside the before window
        (date(2026, 8, 10), 20.0),   # inside the after window
        (date(2027, 1, 1), 999.0),   # long after -- excluded
    ]
    before, after = windowed_engagement(data, date(2026, 8, 1), window_days=30)
    assert before == [10.0]
    assert after == [20.0]


def test_event_day_posts_are_excluded_from_both_sides():
    """A post made on the event day may BE the sponsored post."""
    data = [(date(2026, 8, 1), 50.0)]
    before, after = windowed_engagement(data, date(2026, 8, 1))
    assert before == [] and after == []


def test_windowed_engagement_accepts_datetimes():
    data = [(datetime(2026, 7, 25, 14, 30), 5.0)]
    before, after = windowed_engagement(data, datetime(2026, 8, 1, 9, 0))
    assert before == [5.0] and after == []


# --- robustness ---------------------------------------------------------------


def test_undated_rows_get_their_own_cluster():
    """An undated event cannot be shown to overlap anything, so it must not be
    silently merged -- that would be the same over-count in reverse."""
    rows = [
        {"neighbour_id": KOHLI, "event_date": "2026-08-01"},
        {"neighbour_id": KOHLI, "event_date": None},
        {"neighbour_id": KOHLI, "event_date": "not-a-date"},
    ]
    assert effective_sample_size(cluster_events(rows)) == 3


def test_iso_string_dates_parse():
    rows = [
        {"neighbour_id": KOHLI, "event_date": "2026-08-01T12:00:00Z"},
        {"neighbour_id": KOHLI, "event_date": "2026-08-03T09:30:00+00:00"},
    ]
    assert effective_sample_size(cluster_events(rows)) == 1


def test_empty_input():
    assert cluster_events([]) == []
    assert cluster_weights([]) == []
    assert effective_sample_size([]) == 0


# --- reporting ----------------------------------------------------------------


def test_summarize_exposes_a_dominating_cluster():
    """The number that makes a Kohli-shaped problem visible at a glance."""
    rows = _rows(KOHLI, list(range(0, 32, 2))) + _rows(SHARMA, [0])
    s = summarize(cluster_events(rows))
    assert s["rows"] == 17
    assert s["clusters"] == 2
    assert s["largest"][0][1] == 16
    assert s["max_cluster_share"] > 0.9


def test_weights_sum_to_effective_sample_size():
    rows = _rows(KOHLI, [0, 2, 4]) + _rows(SHARMA, [0, 200])
    clusters = cluster_events(rows)
    assert abs(sum(cluster_weights(clusters)) - effective_sample_size(clusters)) < 1e-9