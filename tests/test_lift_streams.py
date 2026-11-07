"""7 Nov 2026 audit fixes to the spillover lift: format streams and unsettled posts."""

import math

import ml.engagement_lift as el


def _lift(v):
    return {"robust_lift": v, "lift": v, "log_lift": v, "n_before": 3, "n_after": 3}


def test_formats_average_within_platform_before_across_platforms():
    # YouTube short +0.6 and long 0.0 -> YouTube +0.3; Instagram -0.3 -> mean 0.0
    lifts = {"youtube_short": _lift(0.6), "youtube_long": _lift(0.0), "instagram": _lift(-0.3)}
    assert math.isclose(el.row_target(lifts, "log"), 0.0, abs_tol=1e-12)
    assert math.isclose(el.row_target({"instagram": _lift(0.4), "reddit": _lift(0.0)}, "log"), 0.2)


def test_stream_sql_filters_format_and_young_posts():
    short = el._posts_sql("youtube_short", with_creator_col=True)
    long_ = el._posts_sql("youtube_long", with_creator_col=False)
    assert "duration_seconds <= 180" in short and "from youtube_videos" in short
    assert "duration_seconds > 180" in long_ and "%s" in long_
    if el.MIN_POST_AGE_DAYS > 0:
        assert f"interval '{el.MIN_POST_AGE_DAYS} days'" in short
    assert el.stream_platform("youtube_long") == "youtube" and el.stream_platform("instagram") == "instagram"


def test_streams_cover_every_platform():
    platforms = {el.stream_platform(s) for s in el.lift_streams()}
    assert platforms == set(el.PLATFORM_TABLES)
