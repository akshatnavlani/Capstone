"""Tests for the pure parts of snapshot_instagram.py (no Instagram, no database)."""
import shutil
from datetime import datetime, timedelta, timezone

_real_which = shutil.which
shutil.which = lambda name, *a, **k: "stub" if name == "opencli" else _real_which(name, *a, **k)
import snapshot_instagram as snap  # noqa: E402  (importing orchestrator needs an opencli on PATH; the tests never call it)
shutil.which = _real_which

# DeXH-wjTvZ5 was posted 2026-10-11 16:48:47 UTC (decoded from its shortcode)
NOW = datetime(2026, 10, 12, 20, 0, tzinfo=timezone.utc)


def test_shortcode_from_reel_and_post_links():
    assert snap.shortcode_of("/fitadesss/reel/DeXH-wjTvZ5/") == "DeXH-wjTvZ5"
    assert snap.shortcode_of("/p/DLfBTjVTvDe/") == "DLfBTjVTvDe"
    assert snap.shortcode_of("/fitadesss/") is None


def test_own_links_keep_page_order_and_drop_duplicates_and_other_accounts():
    hrefs = ["/fitadesss/p/AAA/", "/fitadesss/reel/BBB/", "/fitadesss/p/AAA/", "/someoneelse/p/CCC/", "/p/DDD/"]
    assert snap.own_links(hrefs, "fitadesss") == ["/fitadesss/p/AAA/", "/fitadesss/reel/BBB/", "/p/DDD/"]


def test_only_young_posts_are_returned_newest_first():
    hrefs = ["/fitadesss/p/DLfBTjVTvDe/", "/fitadesss/reel/DeXH-wjTvZ5/"]  # first is months old
    young = snap.young_posts(hrefs, NOW, 7)
    assert [y[1] for y in young] == ["DeXH-wjTvZ5"]
    assert NOW - young[0][2] < timedelta(days=7)
    assert snap.young_posts(hrefs, NOW + timedelta(days=30), 7) == []


def test_caption_comes_from_the_og_text():
    og = '454 likes, 8 comments - fitadesss on October 11, 2026: "People Pov about CREATINE\n\n@wellcore.in code Adesh10". '
    assert snap.caption_from_og(og).startswith("People Pov about CREATINE")
    assert snap.caption_from_og("") is None


def test_block_signals_are_recognised():
    assert snap.looks_blocked("HTTP 429 from Instagram")
    assert snap.looks_blocked("chrome-error://chromewebdata/")
    assert not snap.looks_blocked("454 likes, 8 comments")
