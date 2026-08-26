from datetime import datetime, timezone, timedelta

from app.text_processing import normalize_to_utc, scrub_text


def test_scrub_removes_urls():
    assert scrub_text("Check this out https://example.com/path?q=1 cool right") == "Check this out cool right"


def test_scrub_removes_html_tags():
    assert scrub_text("<b>Bold</b> and <i>italic</i> text") == "Bold and italic text"


def test_scrub_removes_mentions():
    assert scrub_text("Thanks @someuser for the shoutout") == "Thanks for the shoutout"


def test_scrub_combined_and_collapses_whitespace():
    text = "Hey @friend  check <b>this</b>   out https://example.com   now"
    assert scrub_text(text) == "Hey check this out now"


def test_scrub_none_and_empty():
    assert scrub_text(None) == ""
    assert scrub_text("") == ""


def test_scrub_preserves_normal_text_untouched():
    assert scrub_text("Just a normal sentence with no links or mentions.") == \
        "Just a normal sentence with no links or mentions."


def test_normalize_naive_datetime_assumed_utc():
    naive = datetime(2026, 6, 15, 12, 0, 0)
    result = normalize_to_utc(naive)
    assert result.tzinfo == timezone.utc
    assert result.hour == 12  # unchanged, just labeled UTC


def test_normalize_aware_datetime_converted():
    ist = timezone(timedelta(hours=5, minutes=30))
    aware = datetime(2026, 6, 15, 17, 30, 0, tzinfo=ist)  # 17:30 IST == 12:00 UTC
    result = normalize_to_utc(aware)
    assert result.tzinfo == timezone.utc
    assert result.hour == 12


def test_normalize_none():
    assert normalize_to_utc(None) is None
