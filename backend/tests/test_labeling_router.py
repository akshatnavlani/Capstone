"""Tests the force-relabel behavior added Weeks 11-13 -- the router logic
itself (query selection differs based on `force`), not just detect_sponsorship.

Motivating case: Track A's upsert only touches columns it writes
(caption/title/body), never is_sponsored/sponsorship_raw_matches. If Track A
corrects a row's text after Track C already labeled it, the default mode
would never re-examine that row (it's no longer null). `force=True` exists
so a corrected row can be re-labeled without a code change.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool

from app.database import get_session
from app.main import app
from app.models import InstagramPost, YouTubeVideo


def _memory_engine():
    # StaticPool is required for an in-memory SQLite DB to be shared across
    # multiple connections/sessions within one test -- without it, each new
    # Session(engine) call gets its own independent empty in-memory DB.
    return create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )


@pytest.fixture
def client():
    engine = _memory_engine()
    SQLModel.metadata.create_all(engine)

    def _get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session_override
    # Deliberately NOT using `with TestClient(app) as c:` -- that triggers
    # the app's startup event (init_db()), which uses app.database's
    # module-level engine built from the real configured DATABASE_URL, not
    # this test's in-memory one. This test provides its own complete DB via
    # the dependency override above and doesn't need init_db() to run --
    # avoids a unit test silently reaching out to the real production DB.
    c = TestClient(app)
    yield c, engine
    app.dependency_overrides.clear()


def test_default_mode_skips_already_labeled_rows(client):
    c, engine = client
    with Session(engine) as s:
        s.add(YouTubeVideo(video_id="v1", channel_id="ch1", title="Old title", is_sponsored=False))
        s.commit()

    resp = c.post("/labeling/run")
    assert resp.status_code == 200
    assert resp.json()["youtube_videos"]["checked"] == 0  # already labeled, not null -- skipped


def test_force_mode_reprocesses_already_labeled_rows(client):
    c, engine = client
    with Session(engine) as s:
        # Simulate Track A correcting the text after Track C already labeled
        # it false against the old (e.g. truncated) text.
        s.add(YouTubeVideo(video_id="v1", channel_id="ch1", title="Old title", is_sponsored=False))
        s.commit()

    resp = c.post("/labeling/run", params={"force": "true"})
    assert resp.status_code == 200
    assert resp.json()["youtube_videos"]["checked"] == 1  # reprocessed despite not being null


def test_force_mode_picks_up_corrected_text():
    # Direct check (no HTTP layer) that a force run actually re-derives
    # is_sponsored from current text, not just re-touches the row.
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        video = YouTubeVideo(
            video_id="v1", channel_id="ch1",
            title="Old truncated tit", is_sponsored=False, sponsorship_raw_matches=None,
        )
        s.add(video)
        s.commit()

        # Track A "corrects" the text (simulating a re-scrape with the fix)
        video.title = "Full title now revealing #ad"
        s.add(video)
        s.commit()

    from sqlmodel import select

    from app.labeling import detect_sponsorship

    with Session(engine) as s:
        video = s.exec(select(YouTubeVideo)).one()
        found, matches = detect_sponsorship(video.title, video.description)
        assert found is True
        assert matches == ["#ad"]


def test_paid_partnership_label_forces_sponsored_even_without_caption_match(client):
    # Real case found live 2026-08-14: Instagram post DUkDWOYiL8x on
    # virat.kohli has has_paid_partnership_label=True but caption=None --
    # a caption-only labeler structurally cannot see this disclosure.
    c, engine = client
    with Session(engine) as s:
        s.add(InstagramPost(
            post_id="p1", username="creator1", caption=None,
            has_paid_partnership_label=True,
        ))
        s.commit()

    resp = c.post("/labeling/run")
    assert resp.status_code == 200
    body = resp.json()["instagram_posts"]
    assert body["checked"] == 1
    assert body["labeled_sponsored"] == 1

    with Session(engine) as s:
        post = s.exec(select(InstagramPost)).one()
        assert post.is_sponsored is True
        assert "native:paid_partnership_label" in post.sponsorship_raw_matches
