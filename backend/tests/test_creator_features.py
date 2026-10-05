"""Tests for app/creator_features.py (PendingWork S2): the brief-dependent
creator feature score. Fake embedders and a tiny artifact: no model download,
no database, never touches the real artifact.
"""

import numpy as np
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import creator_features
from app.models import Creator
from app.routers import influencers
from app.schemas import BrandRecommendationRequest
from ml.creator_embeddings import QueryEmbedder


class _FakeEmbedder:
    """Query 'fitness' points along axis 0, anything else along axis 1."""

    def __init__(self):
        self.clip_text = lambda q: np.array([1.0, 0.0] if "fitness" in q else [0.0, 1.0])
        self.bert_text = lambda q: np.array([1.0, 0.0, 0.0] if "fitness" in q else [0.0, 1.0, 0.0])


def _artifact(ids):
    n = len(ids)
    clip = np.zeros((n, 2))
    clip_text = np.zeros((n, 2))
    bert = np.zeros((n, 3))
    has_img = np.zeros(n, dtype=bool)
    has_text = np.zeros(n, dtype=bool)
    # creator 0: fitness-like image and text; creator 1: unrelated text; creator 2: nothing known
    clip[0], has_img[0] = [1.0, 0.1], True
    bert[0], has_text[0] = [1.0, 0.1, 0.0], True
    bert[1], has_text[1] = [0.0, 1.0, 0.0], True
    clip_text[0], clip_text[1] = [1.0, 0.1], [0.0, 1.0]
    return {
        "ids": np.array([str(i) for i in ids]), "clip": clip, "clip_text": clip_text, "bert": bert,
        "has_img": has_img, "has_text": has_text,
        "engagement": np.full(n, np.nan), "log_reach": np.full(n, np.nan),
    }


@pytest.fixture(autouse=True)
def _clean():
    creator_features.reset()
    yield
    creator_features.reset()


def test_score_query_ranks_the_relevant_creator_first_and_leaves_unknown_neutral():
    art = _artifact(["a", "b", "c"])
    res = creator_features.score_query("fitness apparel", art, _FakeEmbedder())
    assert res["a"]["score"] > res["b"]["score"]
    assert res["c"] == {"score": 0.5, "basis": "neutral"}
    assert res["a"]["basis"] == "scored" and res["b"]["basis"] == "scored"
    assert all(0.0 <= v["score"] <= 1.0 for v in res.values())


def test_score_depends_on_the_brief():
    art = _artifact(["a", "b", "c"])
    fit = creator_features.score_query("fitness", art, _FakeEmbedder())
    other = creator_features.score_query("kitchen", art, _FakeEmbedder())
    assert fit["a"]["score"] > fit["b"]["score"]
    assert other["b"]["score"] > other["a"]["score"]


def test_get_feature_scores_is_none_when_disabled_or_empty_query(monkeypatch):
    assert creator_features.get_feature_scores("fitness") is None  # disabled by conftest
    monkeypatch.delenv("CREATOR_FEATURES_DISABLED")
    assert creator_features.get_feature_scores("") is None
    assert creator_features.get_feature_scores(None) is None


def test_missing_artifact_is_none(tmp_path):
    assert creator_features.load_artifact(tmp_path / "nope.npz") is None


def test_artifact_round_trip_and_cached_scores(tmp_path, monkeypatch):
    art = _artifact(["a", "b", "c"])
    path = tmp_path / "creator_embeddings.npz"
    np.savez_compressed(path, **art)
    loaded = creator_features.load_artifact(path)
    assert list(loaded["ids"]) == ["a", "b", "c"]

    monkeypatch.delenv("CREATOR_FEATURES_DISABLED")
    creator_features._artifact, creator_features._embedder = loaded, _FakeEmbedder()
    first = creator_features.get_feature_scores("Fitness")
    assert first is not None and creator_features.get_feature_scores(" fitness ") is first  # cached, case/space-insensitive


def test_query_embedder_accepts_plain_callables():
    e = QueryEmbedder(lambda q: np.ones(2), lambda q: np.ones(3))
    assert e.clip_text("x").shape == (2,) and e.bert_text("x").shape == (3,)


def test_recommendations_use_the_feature_score_when_available(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        a, b = Creator(name="Relevant", category="fitness_influencer"), Creator(name="Unrelated", category="fitness_influencer")
        s.add(a); s.add(b); s.commit(); s.refresh(a); s.refresh(b)
        scores = {str(a.creator_id): {"score": 0.9, "basis": "scored"}, str(b.creator_id): {"score": 0.1, "basis": "scored"}}
        monkeypatch.setattr(influencers, "get_feature_scores", lambda q: scores)
        res = influencers.get_recommendations(BrandRecommendationRequest(product_category="fitness", budget=10_000_000), s).results
    by_name = {r.name: r for r in res}
    assert by_name["Relevant"].score_breakdown.creator_feature_score == pytest.approx(0.9)
    assert by_name["Unrelated"].score_breakdown.creator_feature_score == pytest.approx(0.1)
    assert by_name["Relevant"].final_score > by_name["Unrelated"].final_score


def test_recommendations_keep_neutral_when_feature_scores_unavailable(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Creator(name="Solo", category="fitness_influencer")); s.commit()
        monkeypatch.setattr(influencers, "get_feature_scores", lambda q: None)
        res = influencers.get_recommendations(BrandRecommendationRequest(product_category="fitness", budget=10_000_000), s).results
    assert res[0].score_breakdown.creator_feature_score == pytest.approx(0.5)
