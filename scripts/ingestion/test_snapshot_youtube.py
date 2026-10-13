"""Tests for the pure part of snapshot_youtube.py (no YouTube, no database)."""
import shutil

_real_which = shutil.which
shutil.which = lambda name, *a, **k: "stub" if name == "opencli" else _real_which(name, *a, **k)
import snapshot_youtube as sy  # noqa: E402
shutil.which = _real_which


def _video(vid, views="100", likes="5", comments="2", duration="PT1M30S"):
    return {"id": vid, "snippet": {"title": "t"}, "statistics": {"viewCount": views, "likeCount": likes, "commentCount": comments},
            "contentDetails": {"duration": duration}}


def test_known_videos_become_bulk_rows_and_new_ones_stay_whole():
    items = [_video("old1"), _video("new1"), _video("old2", likes=None)]
    items[2]["statistics"].pop("likeCount")
    targets = {"old1": "UC_a", "new1": "UC_b", "old2": "UC_a"}
    owner = {"UC_a": "creator-a", "UC_b": "creator-b"}
    new_items, count_rows, snap_rows = sy.split_items(items, {"old1", "old2"}, targets, owner)
    assert [v["id"] for v in new_items] == ["new1"]
    assert count_rows[0] == ("old1", "100", "5", "2", 90)
    assert count_rows[1] == ("old2", "100", None, "2", 90)  # hidden likes stay None
    assert snap_rows[0] == ("youtube", "old1", "creator-a", "100", "5", "2")


def test_nothing_known_means_everything_is_new():
    new_items, count_rows, snap_rows = sy.split_items([_video("x")], set(), {"x": "UC_a"}, {"UC_a": "c"})
    assert len(new_items) == 1 and count_rows == [] and snap_rows == []
