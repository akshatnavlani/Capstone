"""Tests for PendingWork S3: spillover on a 0-1 scale, the three-branch
confidence interval, and is_mock_data. No model download, no real database.
"""

import json
import math

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import fusion, spillover, temporal
from app.config import settings
from app.fusion import compute_fusion_score, feature_uncertainty, sentiment_uncertainty
from app.models import Creator
from app.routers import influencers
from app.schemas import BrandRecommendationRequest


# ---- spillover: raw lift -> percentile ----------------------------------------------

def test_unit_rank_is_a_percentile_and_ties_share_the_middle():
    ref = [-1.0, 0.0, 0.0, 5.0, 25.0]
    assert spillover.unit_rank(25.0, ref) == pytest.approx(0.9)
    assert spillover.unit_rank(-1.0, ref) == pytest.approx(0.1)
    assert spillover.unit_rank(0.0, ref) == pytest.approx(0.4)   # ranks 2 and 3 share
    assert spillover.unit_rank(100.0, ref) == 1.0                # beyond the largest
    assert spillover.unit_rank(1.0, []) == spillover.NEUTRAL_UNIT


def test_one_huge_lift_cannot_dominate_the_unit_scale():
    ref = sorted([0.1, 0.2, 0.3, 0.4, 22.9])
    assert spillover.unit_rank(22.9, ref) - spillover.unit_rank(0.4, ref) == pytest.approx(0.2)


def test_fallback_has_neutral_unit_and_widest_uniform_interval():
    res = spillover._fallback("x", "isolated")
    assert res["spillover_unit"] == 0.5
    assert res["unit_low"] == pytest.approx(0.025) and res["unit_high"] == pytest.approx(0.975)


def test_with_unit_adds_monotone_unit_fields(monkeypatch):
    monkeypatch.setattr(spillover, "_reference", [-1.0, 0.0, 1.0, 2.0])
    res = spillover._with_unit({"spillover_score": 1.0, "confidence_low": -1.0, "confidence_high": 3.0})
    assert res["unit_low"] < res["spillover_unit"] < res["unit_high"]
    assert 0.0 <= res["unit_low"] and res["unit_high"] <= 1.0


# ---- fusion: scale and confidence interval -----------------------------------------------

def test_unit_inputs_never_saturate_the_score():
    final, lo, hi, _, _ = compute_fusion_score(1.0, 1.0, 1.0, spillover_half_width=0.1)
    assert final == pytest.approx(100.0)  # the maximum, reached only when every branch is maximal
    final, *_ = compute_fusion_score(0.9, 0.6, 0.6, spillover_half_width=0.1)
    assert 0.0 < final < 100.0


def test_ci_combines_all_three_branches_in_quadrature():
    w1, w2, w3 = (settings.fusion_weight_spillover, settings.fusion_weight_sentiment_risk,
                  settings.fusion_weight_creator_feature)
    final, lo, hi, _, _ = compute_fusion_score(
        0.5, 0.5, 0.5, spillover_half_width=0.2, sentiment_half_width=0.1, feature_half_width=0.3)
    margin = 100 * math.sqrt((w1 * 0.2) ** 2 + (w2 * 0.1) ** 2 + (w3 * 0.3) ** 2)
    assert hi - final == pytest.approx(margin)
    assert final - lo == pytest.approx(margin)


def test_ci_is_wider_with_all_branches_than_spillover_alone():
    _, lo1, hi1, _, _ = compute_fusion_score(0.5, 0.5, 0.5, spillover_half_width=0.2)
    _, lo3, hi3, _, _ = compute_fusion_score(
        0.5, 0.5, 0.5, spillover_half_width=0.2, sentiment_half_width=0.1, feature_half_width=0.3)
    assert (hi3 - lo3) > (hi1 - lo1)
    # legacy callers that pass only the spillover half-width keep the old formula
    assert (hi1 - lo1) / 2 == pytest.approx(100 * settings.fusion_weight_spillover * 0.2)


def test_ci_without_any_half_width_is_the_fixed_placeholder_margin():
    final, lo, hi, _, _ = compute_fusion_score(0.5, 0.5, 0.5)
    assert hi - final == pytest.approx(fusion.PLACEHOLDER_CONFIDENCE_MARGIN)


def test_ci_is_clamped_to_zero_one_hundred():
    _, lo, hi, _, _ = compute_fusion_score(
        0.99, 0.99, 0.99, spillover_half_width=0.475, sentiment_half_width=0.27, feature_half_width=0.475)
    assert 0.0 <= lo <= hi <= 100.0


def test_sentiment_uncertainty_shrinks_with_more_comments():
    assert sentiment_uncertainty(7) > sentiment_uncertainty(100) > sentiment_uncertainty(300)
    assert sentiment_uncertainty(None) == sentiment_uncertainty(0) == fusion.SENTIMENT_NO_DATA_HALF_WIDTH
    assert sentiment_uncertainty(100) == pytest.approx(1.96 * 0.5 / math.sqrt(120))


def test_feature_uncertainty_is_narrower_only_when_scored():
    assert feature_uncertainty("scored") < feature_uncertainty("neutral") == feature_uncertainty(None)
    assert feature_uncertainty(None) == fusion.UNIFORM_HALF_WIDTH


# ---- temporal exposes comment counts ---------------------------------------------------------

def test_temporal_reports_comment_counts(tmp_path):
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    path = tmp_path / "temporal_sentiment.json"
    with Session(engine) as s:
        a, b = Creator(name="A"), Creator(name="B")
        s.add_all([a, b]); s.commit()
        path.write_text(json.dumps({"creators": [
            {"creator_id": str(a.creator_id), "name": "A", "safety_score": 0.7, "n_comments": 42, "platforms": {}},
        ]}), encoding="utf-8")
        out = temporal.compute_temporal(s, scores=temporal.load_scores(path))
    assert out[str(a.creator_id)]["n_comments"] == 42
    assert temporal._fallback("x")["n_comments"] == 0


# ---- recommendations ------------------------------------------------------------------------------

def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_is_mock_data_is_false_for_real_creators_without_stored_scores(monkeypatch):
    with _session() as s:
        s.add(Creator(name="Real", category="fitness_influencer")); s.commit()
        monkeypatch.setattr(influencers, "get_feature_scores", lambda q: None)
        res = influencers.get_recommendations(
            BrandRecommendationRequest(product_category="fitness", budget=10_000_000), s)
    assert res.is_mock_data is False  # no stored FusionScore row, still not mock


def test_is_mock_data_is_true_for_demo_creators(monkeypatch):
    with _session() as s:  # empty creators table -> built-in demo creators
        monkeypatch.setattr(influencers, "get_feature_scores", lambda q: None)
        res = influencers.get_recommendations(
            BrandRecommendationRequest(product_category="fitness", budget=10_000_000), s)
    assert res.is_mock_data is True


def test_recommendation_ci_is_never_the_whole_range_and_scores_stay_in_range(monkeypatch):
    unit = {"spillover_score": 22.0, "spillover_unit": 0.99, "unit_low": 0.9, "unit_high": 1.0,
            "confidence_low": 19.0, "confidence_high": 25.0, "basis": "trained"}
    with _session() as s:
        c = Creator(name="Hot", category="fitness_influencer")
        s.add(c); s.commit(); s.refresh(c)
        monkeypatch.setattr(influencers, "get_feature_scores", lambda q: None)
        monkeypatch.setattr(influencers, "get_spillover_batch", lambda ids: {str(c.creator_id): dict(unit)})
        r = influencers.get_recommendations(
            BrandRecommendationRequest(product_category="fitness", budget=10_000_000), s).results[0]
    assert r.score_breakdown.spillover_score == pytest.approx(0.99)  # the percentile, not the raw 22
    assert r.final_score < 100.0
    assert not (r.confidence_low == 0.0 and r.confidence_high == 100.0)
