import pytest
from fastapi.testclient import TestClient

from app import passport
from app.main import app

FAKE = {
    "as_of": "2026-11-01T00:00:00+00:00",
    "summary": {"clash": {"window_days": 120}, "mood_gap": {}},
    "limits": ["x"],
    "creators": [
        {"creator_id": "a", "name": "Alpha", "category": "fitness_influencer", "coverage": {"platforms": "youtube"}, "evidence": {"grade": "B", "notes": []}, "mood": {"significant": True},
         "clash_events": [{"brand": "Rival Whey", "category": "supplement", "last_seen": "2026-10-20", "tier": "brand_and_code", "posts": 2}, {"brand": "Own Brand", "category": "supplement", "last_seen": "2026-10-01", "tier": "official_label", "posts": 1}]},
        {"creator_id": "b", "name": "Beta", "category": "athlete", "coverage": {"platforms": "instagram"}, "evidence": {"grade": "D", "notes": []}, "mood": None, "clash_events": [{"brand": "Nike", "category": "footwear", "last_seen": "2026-09-30", "tier": "official_label", "posts": 1}]},
    ],
}


@pytest.fixture
def fake(monkeypatch):
    data = dict(FAKE, _by_id={c["creator_id"]: c for c in FAKE["creators"]})
    monkeypatch.setattr(passport, "_data", lambda: data)


def test_infer_category():
    assert passport.infer_category("Whey protein — fitness") == "supplement"
    assert passport.infer_category("Running shoes") == "footwear"
    assert passport.infer_category("a brand new thing") is None


def test_clash_excludes_own_brand_and_other_categories(fake):
    out = passport.clash("whey protein", brand="own brand")
    assert out["category"] == "supplement" and set(out["creators"]) == {"a"}
    assert [e["brand"] for e in out["creators"]["a"]["brands"]] == ["Rival Whey"]
    assert passport.clash("mystery product")["creators"] == {}


def test_endpoints(fake):
    c = TestClient(app)
    assert c.get("/passport/summary").json()["limits"] == ["x"]
    assert [r["name"] for r in c.get("/passport/creators").json()] == ["Alpha", "Beta"]
    assert c.get("/passport/creators").json()[0]["sections_filled"] == 1  # only the clash events are filled in the fake record
    assert c.get("/passport/a").json()["name"] == "Alpha"
    assert c.get("/passport/zzz").status_code == 404
    assert set(c.get("/passport/clash", params={"product": "shoes"}).json()["creators"]) == {"b"}


def test_insights_endpoint_returns_every_block_with_a_source():
    c = TestClient(app)
    d = c.get("/passport/insights").json()
    for block in ("spillover_journey", "benchmark", "power", "passport", "fusion_simulation", "extensions"):
        assert d[block]["source"].startswith("models/")
    assert [r["exposed"] for r in d["spillover_journey"]["rows"]] == sorted(r["exposed"] for r in d["spillover_journey"]["rows"])
    assert d["benchmark"]["simulated"] is True and len(d["benchmark"]["settings"]) == 4
    assert all(0 <= s["share"][0] <= 1 for s in d["power"]["series"]) if d["power"]["series"] else True


def test_strip_returns_only_known_creators_with_missing_parts_as_none(fake):
    out = passport.strip(["a", "zzz", "b"])
    assert set(out) == {"a", "b"}
    assert out["b"]["mood"] is None and out["b"]["speed_first_24h"] is None and out["b"]["recent_brands"] == 1
    c = TestClient(app)
    assert set(c.get("/passport/strip", params={"ids": ["a", "nope"]}).json()) == {"a"}
