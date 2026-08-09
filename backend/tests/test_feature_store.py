"""Tests for app/feature_store.py against synthetic data -- real scraped
data doesn't exist yet (Track A's tables are still empty as of 2026-08-09),
so synthetic data is the correct validation method at this stage, same
approach Track A/B used for their own Weeks 1-4 modules.
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
