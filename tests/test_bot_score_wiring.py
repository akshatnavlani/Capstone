"""Tests for E10: bot detection wired to the live schema.

`ml/bot_detection.py` was written and tested long before any real profiles
existed, and was never connected to anything. The risk in connecting it is not
the scoring -- that has its own tests -- but the loader: it reads columns that
may or may not exist on a given table, and guessing a schema has already cost
this project a failed run (`creator_sponsorship_events` has no `id`).

So these tests cover the loader's contract: ask the server which columns exist,
use what is there, score 0 for what is not, and exclude nobody.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from ml.bot_detection import (
    BotSignals,
    compute_bot_score,
    is_bot_flagged,
    load_bot_scores,
)


class FakeCursor:
    """Answers `select * from t limit 0` with column names, then canned rows."""

    def __init__(self, columns: dict[str, list[str]], results: dict[str, list]):
        self.columns = columns
        self.results = results
        self._pending = []
        self.description = None
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append(sql)
        low = sql.lower()
        if "limit 0" in low:
            table = low.split("from")[1].split()[0]
            self.description = [(c,) for c in self.columns[table]]
            self._pending = []
        elif "from instagram_posts" in low:
            self._pending = self.results.get("cadence", [])
        else:
            self._pending = self.results.get("profiles", [])

    def fetchall(self):
        return self._pending


def _load(cur, id_to_index):
    return load_bot_scores(cur, id_to_index)


# --- the schema contract ------------------------------------------------------


def test_missing_following_count_column_is_tolerated():
    """Not every profile table carries following_count.

    The loader must ask rather than assume, and a column that is absent must
    score 0 (not suspicious) rather than crashing or inflating the score.
    """
    cur = FakeCursor(
        columns={"instagram_profiles": ["creator_id", "follower_count"]},
        results={"profiles": [("c1", 5000)], "cadence": []},
    )
    out = _load(cur, {"c1": 0})
    assert "c1" in out
    assert 0.0 <= out["c1"]["bot_score"] <= 1.0


def test_columns_are_read_from_the_server_not_assumed():
    cur = FakeCursor(
        columns={"instagram_profiles": ["creator_id", "follower_count", "following_count"]},
        results={"profiles": [("c1", 100, 9000)], "cadence": []},
    )
    _load(cur, {"c1": 0})
    assert any("limit 0" in q.lower() for q in cur.queries)


def test_creators_outside_the_graph_are_skipped():
    """A profile whose creator is not a node has no index to attach a score to."""
    cur = FakeCursor(
        columns={"instagram_profiles": ["creator_id", "follower_count"]},
        results={"profiles": [("in-graph", 100), ("not-in-graph", 100)], "cadence": []},
    )
    out = _load(cur, {"in-graph": 0})
    assert set(out) == {"in-graph"}


def test_every_returned_entry_has_both_fields():
    cur = FakeCursor(
        columns={"instagram_profiles": ["creator_id", "follower_count", "following_count"]},
        results={"profiles": [("c1", 100, 9000)], "cadence": []},
    )
    entry = _load(cur, {"c1": 0})["c1"]
    assert set(entry) == {"bot_score", "is_bot_flagged"}
    assert isinstance(entry["is_bot_flagged"], bool)


def test_posting_cadence_is_derived_from_the_post_span():
    """Two posts a day apart is 2/day, not 2 total."""
    cur = FakeCursor(
        columns={"instagram_profiles": ["creator_id", "follower_count", "following_count"]},
        results={
            "profiles": [("c1", 100, 100)],
            "cadence": [("c1", 20, datetime(2026, 1, 1), datetime(2026, 1, 11))],
        },
    )
    out = _load(cur, {"c1": 0})
    assert out["c1"]["bot_score"] > 0, "20 posts in 10 days should register"


def test_no_profiles_gives_no_scores():
    cur = FakeCursor(
        columns={"instagram_profiles": ["creator_id", "follower_count"]},
        results={"profiles": [], "cadence": []},
    )
    assert _load(cur, {"c1": 0}) == {}


# --- the scoring itself, as the loader uses it --------------------------------


def test_mass_following_account_scores_higher_than_a_normal_one():
    normal = compute_bot_score(BotSignals(100_000, 500, None, 1.0, 0.03))
    masser = compute_bot_score(BotSignals(500, 50_000, None, 1.0, 0.03))
    assert masser > normal


def test_missing_age_does_not_inflate_the_score():
    """Instagram exposes no creation date; absent must mean 0, not 1."""
    with_age = compute_bot_score(BotSignals(10_000, 100, 400.0, 1.0, 0.03))
    without = compute_bot_score(BotSignals(10_000, 100, None, 1.0, 0.03))
    assert without == pytest.approx(with_age)


def test_flag_threshold_is_a_boundary_not_a_range():
    assert is_bot_flagged(0.6) is True
    assert is_bot_flagged(0.5999) is False