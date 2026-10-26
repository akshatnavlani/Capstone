"""A3 red-team canary: degenerate queries must not wipe results.

REGRESSION SOURCE. `_keyword_overlap` matches on >=3-character words, so an
empty or single-character `product_category` yields zero keywords. Returning
"no overlap" for that case would read as a confirmed mismatch and exclude
every creator -- this exact wipeout happened on 2026-08-09 (1-char test
payload excluded every real result). The router guards (`if keywords and
...`) make empty mean "no signal" (pass-through); these tests lock that in.

If the first two tests ever fail, the guards regressed -- fix the router,
not the tests. If the third fails, filtering itself is dead -- also fix the
router. All three run against an in-memory SQLite DB; no network, no writes
outside the test process.
"""

from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from app.models import Creator
from app.routers.influencers import (
    _extract_keywords,
    get_recommendations,
)
from app.schemas import BrandRecommendationRequest


def _seeded_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Creator(name="Fit Alice", category="fitness_influencer"))
        s.add(Creator(name="Gym Bob", category="fitness_influencer"))
        s.commit()
    return engine


def _results(engine, product_category):
    with Session(engine) as s:
        req = BrandRecommendationRequest(
            product_category=product_category, budget=10_000_000
        )
        return get_recommendations(req, s).results


def test_extract_keywords_drops_short_words():
    assert _extract_keywords("") == []
    assert _extract_keywords("x") == []
    assert _extract_keywords("a") == []
    assert _extract_keywords("fitness apparel") == ["fitness", "apparel"]


def test_empty_and_single_char_queries_do_not_filter():
    engine = _seeded_engine()
    assert len(_results(engine, "")) == 2
    assert len(_results(engine, "x")) == 2
    assert len(_results(engine, "a")) == 2


def test_genuine_mismatch_still_filters():
    # Guards against "fixing" the canary by disabling filtering entirely.
    engine = _seeded_engine()
    assert _results(engine, "zxywq") == []


def test_creators_with_collected_posts_rank_above_empty_profiles():
    """An empty profile can score high on category and graph alone; it stays in the list but below creators that have data (26 Oct 2026)."""
    import uuid as _uuid
    from datetime import datetime, timezone

    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine

    from app.models import Creator, YouTubeChannel, YouTubeVideo
    from app.routers.influencers import get_recommendations
    from app.schemas import BrandRecommendationRequest

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        empty, full = Creator(name="Empty", category="fitness_influencer"), Creator(name="Has Data", category="fitness_influencer")
        s.add_all([empty, full])
        s.commit()
        s.add(YouTubeChannel(channel_id="ch", creator_id=full.creator_id, subscriber_count=1000))
        s.add(YouTubeVideo(video_id="v", channel_id="ch", creator_id=full.creator_id, published_at=datetime.now(timezone.utc), view_count=10))
        s.commit()
        res = get_recommendations(BrandRecommendationRequest(product_category="fitness", budget=10_000_000), s).results
    by_name = {r.name: r for r in res}
    assert by_name["Has Data"].data_coverage == "youtube" and by_name["Empty"].data_coverage == "none"
    assert [r.name for r in res].index("Has Data") < [r.name for r in res].index("Empty")
