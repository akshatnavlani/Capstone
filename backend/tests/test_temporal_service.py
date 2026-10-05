"""Tests for app/temporal.py: real sentiment where comments were scored,
placeholder otherwise, and risk propagating along real edges. Synthetic data,
in-memory SQLite, temporary artifact: never touches the real artifact or DB.
"""

import json
import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app import temporal
from app.models import Creator, CreatorRelatedAccount


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def _fresh_cache():
    temporal.reset_cache()
    yield
    temporal.reset_cache()


def _artifact(tmp_path, rows):
    path = tmp_path / "temporal_sentiment.json"
    path.write_text(json.dumps({"creators": [
        {"creator_id": str(cid), "name": "x", "safety_score": s, "n_comments": 100, "platforms": {}}
        for cid, s in rows
    ]}), encoding="utf-8")
    return path


def _collab_pair(session, a_handle="@a", b_handle="@b"):
    a = Creator(name="A", youtube_handle=a_handle)
    b = Creator(name="B", youtube_handle=b_handle)
    c = Creator(name="C", youtube_handle="@c")  # no edges
    session.add_all([a, b, c])
    session.commit()
    session.add(CreatorRelatedAccount(
        creator_id=a.creator_id, platform="youtube", handle=b_handle, relation_type="frequent_collaborator",
    ))
    session.commit()
    return a, b, c


def test_load_scores_missing_artifact_is_empty(tmp_path):
    assert temporal.load_scores(tmp_path / "nope.json") == {}


def test_load_scores_corrupt_artifact_is_empty(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert temporal.load_scores(bad) == {}


def test_no_artifact_means_no_results_and_placeholder_fallback(session):
    assert temporal.compute_temporal(session, scores={}) == {}
    cid = uuid.uuid4()
    out = temporal.get_temporal_batch(session, [cid])  # real artifact may or may not exist
    assert out[str(cid)]["basis"] == "placeholder"
    assert out[str(cid)]["sentiment_risk_score"] == 0.5


def test_scored_creator_gets_real_score_and_unscored_stays_placeholder(session, tmp_path):
    a, b, c = _collab_pair(session)
    scores = temporal.load_scores(_artifact(tmp_path, [(a.creator_id, 0.9), (b.creator_id, 0.9)]))
    out = temporal.compute_temporal(session, scores=scores)
    assert out[str(a.creator_id)]["basis"] == "scored"
    assert out[str(a.creator_id)]["own_safety"] == pytest.approx(0.9)
    assert str(c.creator_id) not in out or out[str(c.creator_id)]["basis"] == "placeholder"


def test_risk_propagates_to_collaborator_with_source_identified(session, tmp_path):
    a, b, c = _collab_pair(session)
    # A is the clear low outlier; B and C are safe. Only A is below the shock percentile.
    scores = temporal.load_scores(_artifact(
        tmp_path, [(a.creator_id, 0.1), (b.creator_id, 0.8), (c.creator_id, 0.8)],
    ))
    out = temporal.compute_temporal(session, scores=scores)

    b_out, c_out = out[str(b.creator_id)], out[str(c.creator_id)]
    assert b_out["propagated_risk"] > 0
    assert b_out["source_creator_id"] == str(a.creator_id)
    assert b_out["sentiment_risk_score"] < b_out["own_safety"]   # lowered by A's risk
    assert c_out["propagated_risk"] == 0                          # isolated: unaffected
    assert c_out["sentiment_risk_score"] == pytest.approx(0.8)
    assert out[str(a.creator_id)]["source_creator_id"] is None    # the source is not its own source


def test_scores_stay_in_unit_range(session, tmp_path):
    a, b, c = _collab_pair(session)
    scores = temporal.load_scores(_artifact(
        tmp_path, [(a.creator_id, 0.0), (b.creator_id, 0.05), (c.creator_id, 1.0)],
    ))
    for item in temporal.compute_temporal(session, scores=scores).values():
        assert 0.0 <= item["sentiment_risk_score"] <= 1.0
