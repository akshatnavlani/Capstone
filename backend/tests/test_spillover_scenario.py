"""What-if spillover scenario: exposure from the real links and current sponsorships, times an ASSUMED strength; never an estimate."""

import math
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app import spillover_scenario as sc
from app.models import Creator, CreatorRelatedAccount, YouTubeChannel, YouTubeVideo
from app.schemas import CollaborationEdge


def edge(a, b):
    return CollaborationEdge(source_creator_id=a, target_creator_id=b, weight=1.0)


def test_exposure_is_the_share_of_linked_collaborators_that_were_sponsored():
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    nb = sc.neighbour_sets([edge(a, b), edge(b, a), edge(a, c), edge(c, a), edge(a, d), edge(d, a)])
    assert nb[a] == {b, c, d} and nb[b] == {a}
    assert sc.exposure(nb[a], {b, c}) == pytest.approx(2 / 3)
    assert sc.exposure(set(), {b}) == 0.0 and sc.exposure(nb[a], set()) == 0.0


def test_projection_is_zero_without_exposure_or_assumed_effect_and_grows_with_both():
    assert sc.projected_change(0.5, 0.0) == 0.0 and sc.projected_change(0.0, 1.0) == 0.0
    assert sc.projected_change(0.5, 1.0) == pytest.approx(math.exp(0.5) - 1)       # about +65%
    assert sc.projected_change(0.5, 0.5) < sc.projected_change(0.5, 1.0) < sc.projected_change(1.0, 1.0)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_the_scenario_counts_only_recent_sponsorships_and_labels_itself_an_assumption(session):
    now = datetime.now(timezone.utc)
    a, b, c = (Creator(name=n, category="fitness_influencer", instagram_handle=n.lower()) for n in ("Alpha", "Beta", "Gamma"))
    for x in (a, b, c):
        session.add(x)
    session.commit()
    session.add(CreatorRelatedAccount(creator_id=a.creator_id, platform="instagram", handle="beta", relation_type="frequent_collaborator"))
    session.add(CreatorRelatedAccount(creator_id=a.creator_id, platform="instagram", handle="gamma", relation_type="frequent_collaborator"))
    session.add(YouTubeChannel(channel_id="UCb", creator_id=b.creator_id))
    session.add(YouTubeChannel(channel_id="UCc", creator_id=c.creator_id))
    session.commit()
    session.add(YouTubeVideo(video_id="v1", channel_id="UCb", creator_id=b.creator_id, published_at=now - timedelta(days=5), is_sponsored=True))
    session.add(YouTubeVideo(video_id="v2", channel_id="UCc", creator_id=c.creator_id, published_at=now - timedelta(days=90), is_sponsored=True))   # too old
    session.commit()
    out = sc.build_scenario(session, 0.5)
    by = {r["creator_id"]: r for r in out["rows"]}
    assert by[a.creator_id]["exposure"] == 0.5 and by[a.creator_id]["sponsored_names"] == ["Beta"]
    assert by[a.creator_id]["projected_change_pct"] == pytest.approx(100 * (math.exp(0.25) - 1), abs=0.1)
    assert by[b.creator_id]["exposure"] == 0.0     # Beta's only collaborator, Alpha, has no recent sponsored post
    assert "assumption" in out["note"].lower() and out["assumed_effect_log"] == 0.5
    assert sc.build_scenario(session, 99)["assumed_effect_log"] == sc.MAX_EFFECT_LOG
