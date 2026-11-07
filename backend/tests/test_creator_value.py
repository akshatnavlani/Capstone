"""Track A4: engagement-per-rupee ranking (app/creator_value.py and the /recommendations sort and budget filter)."""
import csv
import uuid
from datetime import datetime, timezone

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import creator_value
from app.models import Creator, YouTubeChannel, YouTubeVideo
from app.routers import influencers
from app.schemas import BrandRecommendationRequest

FIELDS = ["creator_id", "name", "platform", "ranking_expected_engagement", "cost_tier", "cost_low_inr", "cost_mid_inr",
          "cost_high_inr", "engagement_per_1000_inr", "engagement_per_1000_inr_lo", "engagement_per_1000_inr_hi",
          "direct_score", "direct_lo", "direct_hi", "direct_basis", "n_sponsored_posts", "overseas", "india_link"]


def _row(cid, platform, per1000, cost_mid, basis="prior"):
    return {"creator_id": cid, "name": cid, "platform": platform, "ranking_expected_engagement": per1000 * cost_mid / 1000,
            "cost_tier": "mid", "cost_low_inr": cost_mid / 2, "cost_mid_inr": cost_mid, "cost_high_inr": cost_mid * 2,
            "engagement_per_1000_inr": per1000, "engagement_per_1000_inr_lo": per1000 / 2,
            "engagement_per_1000_inr_hi": per1000 * 2, "direct_score": 0.04, "direct_lo": -0.1, "direct_hi": 0.2,
            "direct_basis": basis, "n_sponsored_posts": 3 if basis == "measured" else 0, "overseas": "no", "india_link": ""}


def _write(tmp_path, rows):
    path = tmp_path / "creator_value.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path


def test_percentile_is_within_platform_and_best_platform_is_chosen(tmp_path):
    # YouTube numbers are far larger than Instagram ones; each is ranked only against its own platform.
    path = _write(tmp_path, [_row("a", "youtube", 900, 1e5), _row("b", "youtube", 100, 1e5),
                             _row("a", "instagram", 5, 1e5), _row("b", "instagram", 50, 1e5)])
    vals = creator_value.load_values.__wrapped__(path)
    assert vals["a"][0]["percentile"] == 100.0 and vals["b"][1]["percentile"] == 100.0
    assert creator_value.best_value(vals["b"], None)["platform"] == "instagram"
    assert creator_value.best_value(vals["b"], ["youtube"])["platform"] == "youtube"
    assert creator_value.best_value(vals["b"], ["reddit"]) is None


def test_explain_says_estimate_and_basis(tmp_path):
    path = _write(tmp_path, [_row("a", "youtube", 900, 1.3e5, basis="measured")])
    why = creator_value.explain(creator_value.load_values.__wrapped__(path)["a"][0])
    text = " ".join(why)
    assert "per Rs 1,000" in text and "an estimate" in text and "Rs 1.3 lakh" in text
    assert "measured on 3 sponsored posts" in text


def _engine_with(creators):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for c in creators:
            s.add(c)
            s.add(YouTubeChannel(channel_id="UC" + c.name, creator_id=c.creator_id, subscriber_count=50_000))
            s.add(YouTubeVideo(video_id="v" + c.name, channel_id="UC" + c.name, creator_id=c.creator_id,
                               published_at=datetime(2026, 11, 1, tzinfo=timezone.utc)))
        s.commit()
    return engine


def test_recommendations_rank_by_value_and_filter_by_estimated_cost(tmp_path, monkeypatch):
    cheap_good, pricey, low = (Creator(creator_id=uuid.uuid4(), name=n, category="fitness_influencer")
                               for n in ("cheapgood", "pricey", "low"))
    rows = [_row(str(cheap_good.creator_id), "youtube", 800, 20_000),
            _row(str(pricey.creator_id), "youtube", 2000, 900_000),   # best value but over budget
            _row(str(low.creator_id), "youtube", 100, 20_000)]
    path = _write(tmp_path, rows)
    monkeypatch.setattr(influencers, "load_values", lambda: creator_value.load_values.__wrapped__(path))
    engine = _engine_with([low, pricey, cheap_good])
    with Session(engine) as s:
        res = influencers.get_recommendations(
            BrandRecommendationRequest(product_category="", budget=100_000), s).results
    names = [r.name for r in res]
    assert "pricey" not in names                     # mid cost Rs 9 lakh > budget Rs 1 lakh
    assert names.index("cheapgood") < names.index("low")
    top = res[0]
    assert top.value is not None and top.estimated_cost == 20_000 and top.value.why
