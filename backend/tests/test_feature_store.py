"""Tests for app/feature_store.py against synthetic data -- validated
separately against real live scraped content too (see API_CONTRACTS.md),
same two-track approach Track A/B used for their own modules.
"""

import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app import feature_store
from app.models import (
    Creator,
    CreatorRelatedAccount,
    InstagramPost,
    InstagramProfile,
    RedditPost,
    RedditPostCreator,
    YouTubeChannel,
    YouTubeVideo,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_category_one_hot_matches_track_b_taxonomy():
    assert feature_store.CREATOR_CATEGORIES == (
        "athlete", "team", "league", "fitness_influencer", "lifestyle_influencer", "other",
    )
    assert feature_store._category_one_hot("league") == [0, 0, 1, 0, 0, 0]
    assert feature_store._category_one_hot(None) == [0, 0, 0, 0, 0, 0]
    assert feature_store._category_one_hot("not_a_real_category") == [0, 0, 0, 0, 0, 0]


def test_creator_features_computed_from_real_signals(session):
    creator = Creator(name="TestCreator", category="fitness_influencer")
    session.add(creator)
    session.commit()
    session.refresh(creator)

    session.add(YouTubeChannel(channel_id="UC1", creator_id=creator.creator_id, subscriber_count=1000, description="Fitness channel"))
    session.add(YouTubeVideo(
        video_id="v1", channel_id="UC1", creator_id=creator.creator_id,
        title="Leg day", view_count=100, like_count=10, comment_count=5, thumbnail_url="https://example.com/v1.jpg",
    ))
    session.commit()

    [record] = feature_store.build_creator_features(session)

    assert record.category_one_hot == [0, 0, 0, 1, 0, 0]
    assert record.log_subscriber_count == pytest.approx(6.9088, abs=1e-3)  # log1p(1000)
    assert record.engagement_rate == pytest.approx(0.15)  # (10+5)/100
    assert record.reputation_score is None  # documented gap, not a bug
    assert "Fitness channel" in record.raw_text
    assert "Leg day" in record.raw_text
    assert record.thumbnail_urls == ["https://example.com/v1.jpg"]
    assert record.is_stub is False


def test_creator_with_no_content_is_flagged_stub(session):
    creator = Creator(name="EmptyCreator")
    session.add(creator)
    session.commit()

    [record] = feature_store.build_creator_features(session)
    assert record.is_stub is True
    assert record.log_subscriber_count is None
    assert record.engagement_rate is None


def test_collaboration_edges_resolve_handles_bidirectionally(session):
    a = Creator(name="CreatorA", youtube_handle="@CreatorA")
    b = Creator(name="CreatorB", youtube_handle="@creatorb")  # different case
    session.add(a)
    session.add(b)
    session.commit()
    session.refresh(a)
    session.refresh(b)

    # A lists B as a frequent collaborator, using "@CreatorB" (case differs from B's stored handle)
    session.add(CreatorRelatedAccount(
        creator_id=a.creator_id, platform="youtube", handle="@CreatorB", relation_type="frequent_collaborator",
    ))
    session.commit()

    edges = feature_store.build_collaboration_edges(session)

    pairs = {(e.source_creator_id, e.target_creator_id) for e in edges}
    assert (a.creator_id, b.creator_id) in pairs
    assert (b.creator_id, a.creator_id) in pairs  # both directions, per Track B's contract
    assert len(edges) == 2
    assert all(e.weight == 1.0 for e in edges)


def test_collaboration_edge_skipped_when_handle_does_not_resolve(session):
    a = Creator(name="CreatorA", youtube_handle="@CreatorA")
    session.add(a)
    session.commit()
    session.refresh(a)

    # Handle doesn't match any known creator -- should be silently skipped, not an error.
    session.add(CreatorRelatedAccount(
        creator_id=a.creator_id, platform="youtube", handle="@SomeRandomFanPage", relation_type="frequent_collaborator",
    ))
    session.commit()

    assert feature_store.build_collaboration_edges(session) == []


def test_ambiguous_handle_across_two_creators_is_unresolvable(session):
    # Real scenario, not hypothetical: confirmed live on 2026-08-09 that a
    # pre-fix Track A bug left two separate creator rows both claiming
    # reddit handle "lebron". A naive last-write-wins handle map would
    # silently resolve to whichever creator happened to be seen last --
    # this must instead treat the handle as unresolvable for both.
    dup1 = Creator(name="DupCreatorOne", reddit_handles=["lebron"])
    dup2 = Creator(name="DupCreatorTwo", reddit_handles=["lebron"])
    third = Creator(name="ThirdCreator", reddit_handles=["thirdhandle"])
    session.add(dup1)
    session.add(dup2)
    session.add(third)
    session.commit()
    session.refresh(third)

    session.add(CreatorRelatedAccount(
        creator_id=third.creator_id, platform="reddit", handle="lebron", relation_type="frequent_collaborator",
    ))
    session.commit()

    # Should NOT resolve to either dup1 or dup2 -- the handle is ambiguous.
    assert feature_store.build_collaboration_edges(session) == []


def test_non_collaborator_relation_types_are_ignored(session):
    a = Creator(name="CreatorA", youtube_handle="@CreatorA")
    b = Creator(name="CreatorB", youtube_handle="@CreatorB")
    session.add(a)
    session.add(b)
    session.commit()
    session.refresh(a)
    session.refresh(b)

    session.add(CreatorRelatedAccount(creator_id=a.creator_id, platform="youtube", handle="@CreatorB", relation_type="fan_page"))
    session.commit()

    assert feature_store.build_collaboration_edges(session) == []


def test_co_occurrence_edges_from_shared_reddit_post(session):
    # Mirrors the real scenario found live 2026-08-10: PV Sindhu and Saina
    # Nehwal both linked to the same r/badminton posts via
    # reddit_post_creators (a post can relate to multiple creators when
    # they share a community subreddit).
    a = Creator(name="CreatorA")
    b = Creator(name="CreatorB")
    unrelated = Creator(name="Unrelated")
    session.add(a)
    session.add(b)
    session.add(unrelated)
    session.commit()
    session.refresh(a)
    session.refresh(b)
    session.refresh(unrelated)

    session.add(RedditPost(post_id="p1", subreddit="r/badminton"))
    session.add(RedditPost(post_id="p2", subreddit="r/badminton"))
    session.commit()

    session.add(RedditPostCreator(post_id="p1", creator_id=a.creator_id))
    session.add(RedditPostCreator(post_id="p1", creator_id=b.creator_id))
    session.add(RedditPostCreator(post_id="p2", creator_id=a.creator_id))
    session.add(RedditPostCreator(post_id="p2", creator_id=b.creator_id))
    session.commit()

    edges = feature_store.build_co_occurrence_edges(session)

    pairs = {(e.source_creator_id, e.target_creator_id): e.weight for e in edges}
    assert pairs[(a.creator_id, b.creator_id)] == 2.0  # co-occur on 2 posts
    assert pairs[(b.creator_id, a.creator_id)] == 2.0  # both directions
    assert len(edges) == 2
    assert unrelated.creator_id not in {c for pair in pairs for c in pair}


def test_co_occurrence_edges_empty_when_no_post_has_multiple_creators(session):
    a = Creator(name="CreatorA")
    session.add(a)
    session.commit()
    session.refresh(a)

    session.add(RedditPost(post_id="p1", subreddit="r/solo"))
    session.commit()
    session.add(RedditPostCreator(post_id="p1", creator_id=a.creator_id))
    session.commit()

    assert feature_store.build_co_occurrence_edges(session) == []


def test_sponsorship_edges_empty_until_is_sponsored_populated(session):
    creator = Creator(name="TestCreator")
    session.add(creator)
    session.commit()
    session.refresh(creator)

    session.add(YouTubeChannel(channel_id="UC1", creator_id=creator.creator_id))
    session.add(YouTubeVideo(video_id="v1", channel_id="UC1", creator_id=creator.creator_id))  # is_sponsored=None
    session.commit()

    assert feature_store.build_sponsorship_edges(session) == []


def test_sponsorship_edge_populated_when_labeled_and_linked(session):
    creator = Creator(name="TestCreator")
    brand_id = uuid.uuid4()
    session.add(creator)
    session.commit()
    session.refresh(creator)

    session.add(YouTubeChannel(channel_id="UC1", creator_id=creator.creator_id))
    session.add(YouTubeVideo(
        video_id="v1", channel_id="UC1", creator_id=creator.creator_id,
        is_sponsored=True, brand_id=brand_id,
    ))
    session.commit()

    [edge] = feature_store.build_sponsorship_edges(session)
    assert edge.creator_id == creator.creator_id
    assert edge.brand_id == brand_id
    assert edge.content_id == "v1"
    assert edge.platform == "youtube"
