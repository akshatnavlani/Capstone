"""Tests for ml/link_evidence.py: a YouTube-to-Instagram link needs evidence, not a lucky handle."""

from ml.link_evidence import names_match, score_link


def _link(**kw):
    base = dict(creator_name="Ranveer Allahbadia", ig_username="beerbiceps", ig_full_name="Ranveer Allahbadia", ig_bio="Podcast host",
                ig_followers=4_000_000, yt_handle="BeerBiceps", yt_title="BeerBiceps", yt_description="", yt_subscribers=8_000_000)
    base.update(kw)
    return score_link(**base)


def test_instagram_handle_in_the_channel_description_is_strong():
    r = _link(yt_description="Follow me on Instagram: beerbiceps and Twitter")
    assert r["level"] == "confirmed" and r["strong"]


def test_instagram_link_in_the_description_is_strong_even_for_a_short_handle():
    r = _link(ig_username="abc", yt_handle="xyz", yt_title="Other", yt_description="https://www.instagram.com/abc",
              creator_name="Q", ig_full_name="Q")
    assert r["level"] == "confirmed"


def test_bio_pointing_at_the_channel_is_strong():
    r = _link(yt_description="", ig_bio="New videos on youtube.com/@BeerBiceps")
    assert r["level"] == "confirmed"


def test_name_match_plus_plausible_size_is_probable_but_not_confirmed():
    r = _link(ig_username="someone_else", yt_description="Welcome to the channel", yt_handle="BeerBiceps", yt_title="Ranveer Allahbadia official")
    assert r["level"] == "probable" and not r["strong"]


def test_same_handle_text_alone_goes_to_review():
    r = _link(creator_name="Nisha Kumari", ig_full_name=None, ig_username="nisha_optimist", yt_handle="nisha_optimist", yt_title="Nisha Mishra",
              ig_followers=394_564, yt_subscribers=104_000)
    assert r["weak"] and r["level"] == "review"


def test_fan_channel_is_never_confirmed():
    r = _link(creator_name="Jeet Selal", ig_username="jeet_selal", ig_full_name=None, yt_handle="jeet_selal", yt_title="Jeet Selal Fan's Club. 10M views",
              yt_description="Follow jeet_selal on Instagram", ig_followers=2_651_146, yt_subscribers=3_340)
    assert r["level"] == "review"
    assert any("fan page" in f for f in r["flags"]) and any("mismatch" in f for f in r["flags"])


def test_thanks_to_my_fans_in_the_description_is_not_a_fan_page():
    r = _link(yt_description="Thank you to all my fans! instagram: beerbiceps")
    assert r["level"] == "confirmed" and not r["flags"]


def test_a_podcast_is_not_the_person():
    r = _link(creator_name="Sania Mirza", ig_username="mirzasaniar", ig_full_name="Sania Mirza", yt_handle="servingitupwithsania",
              yt_title="Serving it Up with Sania", yt_description="A podcast", ig_followers=12_550_823, yt_subscribers=69_500)
    assert r["level"] == "review"


def test_names_match_rules():
    assert names_match(["Prajakta Koli"], ["Prajakta Koli Official"])
    assert names_match(["Gaurav Gautam"], ["Gauravgautamindia"])
    assert not names_match(["Nisha Kumari"], ["Nisha Mishra"])
    assert not names_match([None], [None])


def test_missing_counts_do_not_crash():
    r = _link(ig_followers=None, yt_subscribers=None, yt_description="instagram: beerbiceps")
    assert r["ratio"] is None and r["level"] == "confirmed"


def test_a_merch_tagline_saying_unofficial_is_not_a_fan_page():
    r = _link(yt_description="Official merch. Unofficial attitude. instagram: beerbiceps")
    assert r["level"] == "confirmed" and not any("fan page" in f for f in r["flags"])


def test_missing_instagram_data_is_reported_as_not_collected():
    r = _link(ig_followers=None, ig_bio=None, yt_description="")
    assert any("not collected" in f for f in r["flags"]) and r["level"] == "review"
