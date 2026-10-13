"""Offline tests for the collection helpers: exact Instagram time, YouTube paging, snapshots.

No network and no database: the YouTube API and the database cursor are replaced by fakes.
"""

import datetime
import shutil
import types

import psycopg2.errors
import pytest

import ig_time

# orchestrator refuses to import when `opencli` is not on PATH (a laptop without the Instagram
# tooling installed). These tests never call it, so stand in for it during the import only.
_real_which = shutil.which
shutil.which = lambda name, *a, **k: _real_which(name, *a, **k) or ("opencli" if name == "opencli" else None)
try:
    import orchestrator
finally:
    shutil.which = _real_which

from orchestrator import YouTubeWorker, parse_iso8601_duration, record_post_snapshot  # noqa: E402

UTC = datetime.timezone.utc


def _encode(when: datetime.datetime, low_bits: int = 12345) -> str:
    """Inverse of ig_time.decode, used only to build test shortcodes."""
    ms = int(when.timestamp() * 1000)
    media_id = ((ms - ig_time.INSTAGRAM_EPOCH_MS) << ig_time.SHIFT) | low_bits
    chars = []
    while media_id:
        media_id, rem = divmod(media_id, 64)
        chars.append(ig_time.ALPHABET[rem])
    return "".join(reversed(chars))


# ---------------------------------------------------------------- Instagram time

def test_decode_returns_the_exact_instant_in_utc():
    when = datetime.datetime(2026, 3, 14, 15, 9, 26, 535000, tzinfo=UTC)
    assert ig_time.decode(_encode(when)) == when


def test_decode_rejects_bad_input():
    assert ig_time.decode("") is None
    assert ig_time.decode(None) is None
    assert ig_time.decode("abc def") is None
    assert ig_time.decode("ab$cd") is None


def test_decode_agrees_with_the_backfill_script():
    import backfill_dates_from_shortcode as backfill
    for when in (datetime.datetime(2021, 1, 2, 3, 4, 5, tzinfo=UTC),
                 datetime.datetime(2024, 11, 30, 23, 59, 59, tzinfo=UTC),
                 datetime.datetime(2026, 8, 20, 0, 0, 0, tzinfo=UTC)):
        code = _encode(when)
        assert ig_time.decode(code) == backfill.decode(code)


def test_posted_at_prefers_the_exact_time_over_a_bare_date():
    when = datetime.datetime(2026, 5, 9, 17, 42, 11, tzinfo=UTC)
    assert ig_time.posted_at_for(_encode(when), "5/9/2026") == when


def test_posted_at_falls_back_to_the_listing_date_then_none():
    assert ig_time.posted_at_for("not a code!", "5/9/2026") == datetime.datetime(2026, 5, 9, tzinfo=UTC)
    assert ig_time.posted_at_for("not a code!", None) is None
    assert ig_time.posted_at_for("not a code!", "garbage") is None


# ---------------------------------------------------------------- YouTube duration

@pytest.mark.parametrize("raw,seconds", [
    ("PT1H2M3S", 3723), ("PT45S", 45), ("PT1M", 60), ("PT2H", 7200), ("P1DT2H", 93600), ("P0D", 0),
])
def test_duration_parses(raw, seconds):
    assert parse_iso8601_duration(raw) == seconds


@pytest.mark.parametrize("raw", [None, "", "garbage", "PT", "1:02:03"])
def test_duration_missing_or_unrecognised_is_none(raw):
    assert parse_iso8601_duration(raw) is None


# ---------------------------------------------------------------- YouTube paging

def _worker(post_cap, recency_days=3650):
    stub_limiter = types.SimpleNamespace(wait=lambda: None)
    return YouTubeWorker(stub_limiter, dry_run=True, post_cap=post_cap, recency_days=recency_days)


def _page(first, count, next_token, published="2026-09-01T00:00:00Z"):
    return {"items": [{"contentDetails": {"videoId": f"v{first + i}", "videoPublishedAt": published}}
                      for i in range(count)],
            **({"nextPageToken": next_token} if next_token else {})}


def test_upload_ids_follow_page_tokens_up_to_the_cap(monkeypatch):
    pages = {None: _page(0, 50, "p2"), "p2": _page(50, 50, "p3"), "p3": _page(100, 50, None)}
    calls = []

    def fake_get(endpoint, **params):
        calls.append(params.get("pageToken"))
        return pages[params.get("pageToken")]

    monkeypatch.setattr(orchestrator, "youtube_api_get", fake_get)
    ids = _worker(post_cap=120)._upload_ids("UU123")
    assert len(ids) == 120 and ids[0] == "v0" and ids[-1] == "v119"
    assert calls == [None, "p2", "p3"]


def test_upload_ids_stop_when_the_uploads_run_out(monkeypatch):
    monkeypatch.setattr(orchestrator, "youtube_api_get", lambda e, **p: _page(0, 7, None))
    assert len(_worker(post_cap=300)._upload_ids("UU123")) == 7


def test_upload_ids_stop_at_the_recency_cutoff(monkeypatch):
    recent = _page(0, 3, "more")
    old = _page(3, 3, "more", published="2001-01-01T00:00:00Z")
    pages = {None: {"items": recent["items"] + old["items"], "nextPageToken": "more"}}
    calls = []

    def fake_get(endpoint, **params):
        calls.append(params.get("pageToken"))
        return pages[params.get("pageToken")]

    monkeypatch.setattr(orchestrator, "youtube_api_get", fake_get)
    ids = _worker(post_cap=300, recency_days=365)._upload_ids("UU123")
    assert ids == ["v0", "v1", "v2"] and calls == [None]


# ---------------------------------------------------------------- brand mapping in the collector

class _BrandCursor:
    def __init__(self):
        self.names = []

    def execute(self, sql, params=None):
        if "insert into brands" in sql:
            self.names.append(params[0])

    def fetchone(self):
        return (f"brand-{len(self.names)}",)


def test_known_brand_with_a_code_gets_a_brand_id():
    cur = _BrandCursor()
    assert orchestrator.brand_id_for_text(cur, "Whey from @muscleblaze, code ANKUSHMB") == "brand-1"
    assert cur.names == ["MuscleBlaze"]


def test_bare_brand_name_does_not_set_a_brand_id():
    cur = _BrandCursor()
    assert orchestrator.brand_id_for_text(cur, "I wore my Puma shoes at the gym today") is None
    assert cur.names == []


# ---------------------------------------------------------------- snapshot poller helpers

def test_uploads_playlist_id_swaps_the_prefix():
    import snapshot_youtube
    assert snapshot_youtube.uploads_playlist_id("UCabc123") == "UUabc123"
    assert snapshot_youtube.uploads_playlist_id("XYabc123") is None
    assert snapshot_youtube.uploads_playlist_id("UC") is None


def test_chunks_split_into_batches_of_at_most_the_size():
    import snapshot_youtube
    parts = list(snapshot_youtube.chunks(list(range(120)), 50))
    assert [len(p) for p in parts] == [50, 50, 20]
    assert list(snapshot_youtube.chunks([], 50)) == []


# ---------------------------------------------------------------- snapshots

class _Cursor:
    def __init__(self, fail_insert=False):
        self.fail_insert, self.sql = fail_insert, []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if self.fail_insert and sql.startswith("insert into post_snapshots"):
            raise psycopg2.errors.UndefinedTable()


def test_snapshot_is_written_inside_a_savepoint():
    cur = _Cursor()
    record_post_snapshot(cur, "youtube", "vid", None, 10, 2, 1)
    assert cur.sql[0] == "savepoint snapshot_insert"
    assert cur.sql[1].startswith("insert into post_snapshots")
    assert cur.sql[-1] == "release savepoint snapshot_insert"


def test_missing_snapshot_table_is_skipped_not_fatal(monkeypatch):
    monkeypatch.setattr(orchestrator, "_snapshot_tables_missing_logged", False)
    cur = _Cursor(fail_insert=True)
    record_post_snapshot(cur, "instagram", "abc", None, None, 5, 0)  # must not raise
    assert cur.sql[-1] == "rollback to savepoint snapshot_insert"


def test_everyday_word_is_not_saved_as_a_brand(monkeypatch):
    class _Lead:
        candidate_name = "Call"
        confidence = "explicit"

    monkeypatch.setattr(orchestrator, "extract_brand_mentions", lambda text: [_Lead()])
    cur = _BrandCursor()
    assert orchestrator.brand_id_for_text(cur, "Call now for a free quote") is None
    assert cur.names == []


# --- Instagram page readers (text taken from a real profile and post page, 2026-10-13) ------------------

_PROFILE_OG = "105K Followers, 546 Following, 456 Posts - See Instagram photos and videos from Adesh Sahu (@fitadesss)"
_PROFILE_DESC = ('105K Followers, 546 Following, 456 Posts - Adesh Sahu (@fitadesss) on Instagram: '
                 '"⚡️\n20teen..\nYouTube 250k+\n@wellcore.in “Adesh10”\n@wellversed.in “Adesh10”"')


def test_approx_int_handles_k_m_and_plain_numbers():
    assert orchestrator.og_approx_int("105K") == 105000
    assert orchestrator.og_approx_int("1.3M") == 1300000
    assert orchestrator.og_approx_int("1,234") == 1234
    assert orchestrator.og_approx_int("456") == 456
    assert orchestrator.og_approx_int(None) is None
    assert orchestrator.og_approx_int("lots") is None


def test_profile_page_gives_counts_name_and_bio():
    prof = orchestrator.parse_profile_page({"og": _PROFILE_OG, "desc": _PROFILE_DESC})
    assert (prof["followers"], prof["following"], prof["posts"]) == (105000, 546, 456)
    assert prof["name"] == "Adesh Sahu"
    assert "@wellcore.in" in prof["bio"] and "Adesh10" in prof["bio"]


def test_profile_page_with_no_counts_is_none():
    assert orchestrator.parse_profile_page({"og": "Instagram", "desc": None}) is None
    assert orchestrator.parse_profile_page("not json") is None
    assert orchestrator.parse_profile_page(None) is None


def test_post_extras_pairs_each_comment_id_with_its_exact_time():
    raw = ('{"img": "https://cdn.example/a.jpg", "paid": false, "times": ['
           '{"id": "18175595176453225", "dt": "2026-10-11T17:05:28.000Z"},'
           '{"id": "17933987250147142", "dt": "2026-10-12T04:12:59.000Z"}]}')
    extras = orchestrator.parse_post_extras(raw)
    assert extras["image"] == "https://cdn.example/a.jpg" and extras["paid"] is False
    assert extras["comment_times"]["18175595176453225"].isoformat() == "2026-10-11T17:05:28+00:00"
    assert len(extras["comment_times"]) == 2


def test_post_extras_with_nothing_returned_is_unknown_not_false():
    extras = orchestrator.parse_post_extras(None)
    assert extras["paid"] is None and extras["comment_times"] == {} and extras["image"] is None


def test_post_extras_skips_a_bad_time_entry():
    extras = orchestrator.parse_post_extras({"times": [{"id": "1", "dt": "nonsense"}, {"id": "2", "dt": "2026-10-11T17:05:28Z"}]})
    assert list(extras["comment_times"]) == ["2"]


def test_og_approx_counts_reads_rounded_numbers():
    assert orchestrator.og_approx_counts("12.3K likes, 456 comments - x on October 11, 2026") == (12300, 456)
    assert orchestrator.og_approx_counts("454 likes, 8 comments - fitadesss on October 11, 2026") == (454, 8)
    assert orchestrator.og_approx_counts("") == (None, None)


def test_a_failed_creator_rolls_the_transaction_back_so_the_next_one_can_run():
    class _Conn:
        closed = 0
        rollbacks = 0

        def rollback(self):
            self.rollbacks += 1

    class _Boom(orchestrator.PlatformWorker):
        platform_name = "test"

        def _handle_for(self, creator):
            return creator.name

        def process_creator(self, creator, handle, conn):
            raise RuntimeError("statement timeout")

    conn = _Conn()
    creators = [orchestrator.Creator("1", "a", "c"), orchestrator.Creator("2", "b", "c")]
    _Boom(None).run_batch(creators, conn)
    assert conn.rollbacks == 2
