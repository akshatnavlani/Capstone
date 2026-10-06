"""Filter matching rules (PendingWork S7 fixes): stemmed whole-word matching for the keyword
filters, and a region filter that reads country codes, the flag, Indian scripts and the name.
Each test pins a false drop or a false keep that the S7 audit measured on the live data.
"""

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import Creator, YouTubeChannel
from app.routers.influencers import _keyword_overlap, _region_overlap, _stem, get_recommendations
from app.schemas import BrandRecommendationRequest


# ---- keyword matching ---------------------------------------------------------------------------

def test_athletic_finds_athlete_and_plurals_match():
    assert _keyword_overlap(["athletic"], ["athlete"])          # the demo query's false drop
    assert _keyword_overlap(["athletic"], ["Olympic athletes"])
    assert _keyword_overlap(["shoes"], ["a good running shoe"])
    assert _keyword_overlap(["running"], ["trail runner"])


def test_short_words_must_match_a_whole_word():
    assert not _keyword_overlap(["mat"], ["cinematic storyteller", "IPL matches", "ultimate arms"])
    assert _keyword_overlap(["mat"], ["premium yoga mat"])
    assert not _keyword_overlap(["bat"], ["battleground"])
    assert not _keyword_overlap(["night"], ["Kolkata Knight Riders"])
    assert _keyword_overlap(["night"], ["fight night"])


def test_long_words_may_match_inside_a_longer_word():
    assert _keyword_overlap(["cricket"], ["Indian Cricketer"])
    assert _keyword_overlap(["cricket"], ["@lancashirecricket"])
    assert _keyword_overlap(["protein"], ["@myproteinin ambassador"])


def test_no_keywords_and_no_match():
    assert not _keyword_overlap([], ["anything"])
    assert not _keyword_overlap(["zxywq"], ["yoga", None, ""])
    assert not _keyword_overlap(["!!!"], ["yoga"])


def test_stem_is_conservative():
    assert _stem("athletic") == _stem("athlete") == _stem("athletics")
    assert _stem("gym") == "gym" and _stem("shoes") == "shoe"


# ---- region matching ------------------------------------------------------------------------------

def test_region_reads_country_code_flag_phone_script_and_name():
    assert _region_overlap(["india"], ["IN", None, None], "Prajakta Koli")             # YouTube country code
    assert _region_overlap(["india"], [None, None, "Cricketer \U0001f1ee\U0001f1f3"], "X")  # flag emoji
    assert _region_overlap(["india"], [None, None, "book now +91 98765 43210"], "X")
    assert _region_overlap(["india"], [None, "\u0927\u0928\u094d\u092f\u0903 \u0905\u0938\u094d\u092e\u093f", None], "X")  # Devanagari
    assert _region_overlap(["india"], [None, "Health supplement", None], "Fully Dosed - India")  # name
    assert _region_overlap(["india"], [None, "Indian cricketer", None], "X")           # 'indian'


def test_region_still_drops_clear_mismatches():
    assert not _region_overlap(["india"], ["US", "Ohio State football", None], "Ohio State Buckeyes")
    assert not _region_overlap(["india"], ["AU", "Australian Cricket Captain", None], "Pat Cummins")
    assert not _region_overlap(["india"], [None, "Indiana state park", None], "Indiana Parks")  # 'indiana' is not india
    assert _region_overlap(["australia"], ["AU", None, None], "X")                    # other regions via the code


# ---- the router keeps the "no text, no judgement" rule -----------------------------------------------

def _engine_with(*rows):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        for name, category, country in rows:
            c = Creator(name=name, category=category)
            s.add(c)
            s.commit()
            s.refresh(c)
            if country is not None:
                s.add(YouTubeChannel(channel_id=f"UC{name[:6]}", creator_id=c.creator_id, country=country, description="channel"))
                s.commit()
    return engine


def _names(engine, **query):
    with Session(engine) as s:
        req = BrandRecommendationRequest(budget=10_000_000, **query)
        return {r.name for r in get_recommendations(req, s).results}


def test_router_region_filter_keeps_india_code_and_no_text_creators_and_drops_foreign():
    engine = _engine_with(
        ("Desi Coach", "fitness_influencer", "IN"),       # country code IN -> kept (was dropped)
        ("Texas Coach", "fitness_influencer", "US"),      # clearly elsewhere -> dropped
        ("Silent Coach", "fitness_influencer", None),     # no region text at all -> kept, as before
    )
    assert _names(engine, product_category="fitness", target_region="India") == {"Desi Coach", "Silent Coach"}


def test_router_product_filter_finds_athletes_for_athletic_products():
    engine = _engine_with(("Sprint Star", "athlete", None), ("Chef Anna", "other", None))
    assert _names(engine, product_category="athletic water bottle") == {"Sprint Star"}
