"""Per-platform profile: honest unknowns, status from the creator's own engagement rate against the others, first-day growth only when a reading exists."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import platform_profile as pp
from app.models import Creator, InstagramPost, InstagramProfile, YouTubeChannel, YouTubeVideo


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    pp._cohort_cache.clear()
    return Session(engine)


def _creator(s, name="C"):
    c = Creator(name=name)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


def _youtube(s, c, n, views, likes, comments, sponsored_every=0):
    ch = YouTubeChannel(channel_id=f"ch-{c.creator_id}", creator_id=c.creator_id, subscriber_count=100_000)
    s.add(ch)
    for i in range(n):
        s.add(YouTubeVideo(video_id=f"{c.creator_id}-{i}", channel_id=ch.channel_id, creator_id=c.creator_id, published_at=datetime.now(timezone.utc) - timedelta(days=60 + 5 * i),
                           view_count=views, like_count=likes, comment_count=comments, is_sponsored=bool(sponsored_every and i % sponsored_every == 0)))
    s.commit()


def test_a_creator_with_no_data_says_so_and_has_no_numbers():
    with _session() as s:
        p = pp.build_profile(s, _creator(s).creator_id)
    assert not p.youtube.available and not p.instagram.available and p.youtube.status == "unknown"
    assert p.youtube.typical_views is None and "No YouTube data" in p.youtube.notes[0]
    assert "Not enough data" in p.summary


def test_youtube_typical_numbers_and_engagement_rate():
    with _session() as s:
        c = _creator(s)
        _youtube(s, c, 8, views=10_000, likes=400, comments=100)
        side = pp.youtube_side(s, c.creator_id)
    assert side.typical_views == 10_000 and abs(side.engagement_rate - 0.05) < 1e-9 and abs(side.views_per_subscriber - 0.1) < 1e-9
    assert side.items_with_counts == 8 and side.status == "unknown" and side.first_day is None   # fewer than 10 creators to compare with


def test_status_is_strong_for_a_top_third_engagement_rate():
    with _session() as s:
        others = []
        for i in range(12):
            c = _creator(s, f"o{i}")
            _youtube(s, c, 6, views=10_000, likes=100 + 20 * i, comments=10)
        star = _creator(s, "star")
        _youtube(s, star, 6, views=10_000, likes=2_000, comments=500)
        weak = _creator(s, "weak")
        _youtube(s, weak, 6, views=10_000, likes=10, comments=1)
        assert pp.youtube_side(s, star.creator_id, refresh=True).status == "strong"
        assert pp.youtube_side(s, weak.creator_id, refresh=True).status == "weak"


def test_instagram_counts_missing_are_reported_not_filled():
    with _session() as s:
        c = _creator(s)
        s.add(InstagramProfile(username="u", creator_id=c.creator_id, follower_count=50_000))
        for i in range(6):
            s.add(InstagramPost(post_id=f"p{i}", username="u", creator_id=c.creator_id, posted_at=datetime.now(timezone.utc) - timedelta(days=3 * i + 1),
                                like_count=1_000 if i < 4 else None, comment_count=50 if i < 4 else None))
        s.commit()
        side = pp.instagram_side(s, c.creator_id)
    assert side.items_total == 6 and side.items_with_counts == 4 and abs(side.engagement_rate - 1050 / 50_000) < 1e-9
    assert any("4 of 6" in n for n in side.notes) and side.status == "unknown"


def test_summary_names_the_stronger_platform(monkeypatch):
    from app.schemas import PlatformSide

    def side(platform, status):
        return PlatformSide(platform=platform, available=True, status=status)

    cid = uuid.uuid4()
    for yt, ig, expected in [("strong", "weak", "Stronger on YouTube than on Instagram"), ("weak", "strong", "Stronger on Instagram than on YouTube"),
                             ("typical", "typical", "About equally typical"), ("strong", "unknown", "Instagram cannot be judged")]:
        monkeypatch.setattr(pp, "youtube_side", lambda s_, c_, r_=False, v=yt: side("youtube", v))
        monkeypatch.setattr(pp, "instagram_side", lambda s_, c_, r_=False, v=ig: side("instagram", v))
        assert expected in pp.build_profile(None, cid).summary


def test_a_first_day_share_above_one_is_not_reported():
    with _session() as s:
        c = _creator(s)
        s.add(InstagramProfile(username="u", creator_id=c.creator_id, follower_count=1000))
        born = datetime.now(timezone.utc) - timedelta(days=2)
        for i in range(2):
            s.add(InstagramPost(post_id=f"p{i}", username="u", creator_id=c.creator_id, posted_at=born, like_count=10, comment_count=1))
        s.commit()
        from sqlalchemy import text as sql

        s.execute(sql("create table post_snapshots (snapshot_id integer primary key, platform text, post_id text, creator_id text, fetched_at timestamp, view_count integer, like_count integer, comment_count integer)"))
        s.execute(sql("insert into post_snapshots (platform, post_id, creator_id, fetched_at, like_count) values ('instagram', 'p0', :c, :t, 500)"),
                  {"c": str(c.creator_id), "t": (born + timedelta(hours=24)).replace(tzinfo=None)})
        s.commit()
        side = pp.instagram_side(s, c.creator_id)
    assert side.first_day.items_with_a_first_day_reading == 1 and side.first_day.median_value_at_24h == 500
    assert side.first_day.median_share_of_current_total is None   # 500 likes at 24 h against a stored total of 10: the counts disagree, so no share is reported
