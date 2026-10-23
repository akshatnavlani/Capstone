"""Tests for the shared `platform_engagement` (E13).

THE BUG THIS PINS. The query lived in `compute_training_pair_deltas.py` and
`train_prod_model.py` with byte-identical SQL and different windowing: the
deltas script bounded to +/- 30 days (E2), the training script did not. So the
script used to INSPECT the data showed bounded windows while the model TRAINED
on unbounded ones -- the exact bug E2 was written to remove.

It survived E11, which shared the lift formula but not the window, and it was
invisible in both scripts' own output. It only showed up when the two were
compared: 26 lift-computable rows against 51, one creator contributing 17 of
the extra rows at a lift of +14.86.

`test_unbounded_and_bounded_windows_disagree` is the test that matters. It
fails if the window ever stops being applied.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ml.engagement_lift import PLATFORM_TABLES, platform_engagement

EVENT = date(2026, 8, 1)


class FakeCursor:
    """Minimal stand-in: records the SQL, returns canned rows."""

    def __init__(self, rows):
        self._rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self._rows


def _rows(*offsets_and_values):
    """(day offset from EVENT, e1, e2) tuples, as the query returns them."""
    return [(EVENT + timedelta(days=d), a, b) for d, a, b in offsets_and_values]


# --- the headline case --------------------------------------------------------


def test_unbounded_and_bounded_windows_disagree():
    """A post a year before the event must not count toward the baseline.

    Under the unbounded version it did, which is how one engagement jump became
    seventeen training rows.
    """
    cur = FakeCursor(_rows((-400, 100, 0), (-5, 10, 0), (+5, 20, 0)))

    before, after = platform_engagement(cur, "c", "instagram", EVENT, window_days=30)

    assert before == [10.0], "the year-old post must be excluded"
    assert after == [20.0]


def test_the_window_is_actually_applied_by_default():
    """Guards the default argument: an omitted window must not mean unbounded."""
    cur = FakeCursor(_rows((-400, 100, 0), (-5, 10, 0), (+5, 20, 0)))
    before, _ = platform_engagement(cur, "c", "instagram", EVENT)
    assert 100.0 not in before


# --- window semantics ---------------------------------------------------------


def test_event_day_counts_on_neither_side():
    """A post made the same day may BE the sponsored post."""
    cur = FakeCursor(_rows((0, 50, 0)))
    before, after = platform_engagement(cur, "c", "instagram", EVENT)
    assert before == [] and after == []


def test_window_boundaries_are_inclusive():
    cur = FakeCursor(_rows((-30, 1, 0), (+30, 2, 0)))
    before, after = platform_engagement(cur, "c", "instagram", EVENT, window_days=30)
    assert before == [1.0] and after == [2.0]


def test_one_day_past_the_window_is_excluded():
    cur = FakeCursor(_rows((-31, 1, 0), (+31, 2, 0)))
    before, after = platform_engagement(cur, "c", "instagram", EVENT, window_days=30)
    assert before == [] and after == []


def test_widening_the_window_admits_more_posts():
    cur = FakeCursor(_rows((-45, 7, 0), (+5, 1, 0)))
    narrow, _ = platform_engagement(cur, "c", "instagram", EVENT, window_days=30)
    wide, _ = platform_engagement(cur, "c", "instagram", EVENT, window_days=60)
    assert narrow == [] and wide == [7.0]


# --- engagement summing -------------------------------------------------------


def test_both_engagement_columns_are_summed():
    cur = FakeCursor(_rows((-5, 10, 3)))
    before, _ = platform_engagement(cur, "c", "instagram", EVENT)
    assert before == [13.0]


def test_query_requires_both_columns_non_null():
    """The filter is in the SQL, so it is checked on the SQL.

    Layer 2 of the missingness fix: a post carrying only the smaller metric
    still biases whichever side holds more of them.
    """
    cur = FakeCursor([])
    platform_engagement(cur, "c", "instagram", EVENT)
    assert "like_count is not null" in cur.sql
    assert "comment_count is not null" in cur.sql


def test_creator_id_is_parameterised_not_interpolated():
    cur = FakeCursor([])
    platform_engagement(cur, "some-uuid", "instagram", EVENT)
    assert cur.params == ("some-uuid",)
    assert "some-uuid" not in cur.sql


# --- platform coverage --------------------------------------------------------


@pytest.mark.parametrize("platform", sorted(PLATFORM_TABLES))
def test_every_platform_queries_its_own_table(platform):
    table, date_col, e1, e2 = PLATFORM_TABLES[platform]
    cur = FakeCursor([])
    platform_engagement(cur, "c", platform, EVENT)
    assert table in cur.sql
    assert date_col in cur.sql
    assert e1 in cur.sql and e2 in cur.sql


def test_unknown_platform_raises():
    with pytest.raises(KeyError):
        platform_engagement(FakeCursor([]), "c", "tiktok", EVENT)


def test_no_posts_gives_two_empty_sides():
    cur = FakeCursor([])
    assert platform_engagement(cur, "c", "reddit", EVENT) == ([], [])