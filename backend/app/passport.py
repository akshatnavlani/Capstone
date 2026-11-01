"""Creator Passport: serves models/creator_passport.json (written by scripts/build_creator_passport.py) and answers the brief-dependent competitor-clash question.

Nothing here changes a score or a ranking. The passport shows what we know about a creator across platforms, each part with its own sample size; the clash flag is a warning, not a penalty.
"""

import json
from pathlib import Path
from typing import Optional

PASSPORT_PATH = Path(__file__).resolve().parents[2] / "models" / "creator_passport.json"
_cache: dict = {"mtime": None, "path": None, "data": None}

# Product words in a brief -> the brand category in the brands table. First category with the most keyword hits wins; no hit means no clash check (we do not guess).
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "supplement": ("protein", "whey", "creatine", "supplement", "pre-workout", "preworkout", "bcaa", "gainer", "multivitamin", "nutrition", "vitamin"),
    "footwear": ("shoe", "sneaker", "footwear", "running shoes"),
    "apparel": ("apparel", "clothing", "activewear", "gym wear", "gymwear", "t-shirt", "tshirt", "leggings", "joggers"),
    "food": ("snack", "oats", "muesli", "peanut butter", "chocolate", "granola", "energy bar", "protein bar", "food"),
    "equipment": ("dumbbell", "equipment", "treadmill", "resistance band", "yoga mat", "kettlebell", "gym membership"),
    "wellness": ("wellness", "ayurved", "sleep", "skincare", "herbal"),
}


def _data() -> Optional[dict]:
    """The passport file, re-read only when it changes; a missing or unreadable file means no passport."""
    try:
        mtime = PASSPORT_PATH.stat().st_mtime
    except OSError:
        return None
    if _cache["mtime"] != mtime or _cache["path"] != str(PASSPORT_PATH):
        try:
            data = json.loads(PASSPORT_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        data["_by_id"] = {c["creator_id"]: c for c in data.get("creators", [])}
        _cache.update(mtime=mtime, path=str(PASSPORT_PATH), data=data)
    return _cache["data"]


def infer_category(product: str) -> Optional[str]:
    text = (product or "").lower()
    best, best_hits = None, 0
    for cat, words in CATEGORY_KEYWORDS.items():
        hits = sum(w in text for w in words)
        if hits > best_hits:
            best, best_hits = cat, hits
    return best


def summary() -> Optional[dict]:
    d = _data()
    return None if d is None else {"as_of": d["as_of"], "summary": d["summary"], "limits": d["limits"]}


def creator_list() -> list[dict]:
    d = _data()
    if d is None:
        return []
    out = []
    for c in d["creators"]:
        mood = c.get("mood") or {}
        sp = c.get("sponsored") or {}
        parts = [c.get("platform_strength"), mood.get("gap") is not None, c.get("speed"), sp.get("youtube_views") or sp.get("youtube_likes") or sp.get("instagram_likes"), sp.get("buying_signals"),
                 sp.get("disclosure"), c.get("fatigue"), c.get("clash_events"), (c.get("network") or {}).get("linked_creators")]
        out.append({"creator_id": c["creator_id"], "name": c["name"], "category": c["category"], "platforms": c["coverage"]["platforms"], "grade": c["evidence"]["grade"],
                    "mood_gap_flag": bool(mood.get("significant")), "has_recent_brand_posts": bool(c.get("clash_events")), "sections_filled": sum(bool(x) for x in parts)})
    return sorted(out, key=lambda r: r["name"].lower())


def get_creator(creator_id: str) -> Optional[dict]:
    d = _data()
    return None if d is None else d["_by_id"].get(creator_id)


def clash(product: str, brand: Optional[str] = None) -> dict:
    """Creators who promoted a RIVAL brand of the brief's category in the last window days. A brand never clashes with itself. Unknown category: no check is made."""
    d = _data()
    category = infer_category(product)
    if d is None or category is None:
        return {"category": category, "window_days": (d or {}).get("summary", {}).get("clash", {}).get("window_days"), "creators": {}}
    own = (brand or "").strip().lower()
    found = {}
    for c in d["creators"]:
        rivals = [e for e in c.get("clash_events", []) if e["category"] == category and e["brand"].lower() != own]
        if rivals:
            found[c["creator_id"]] = {"brands": rivals[:5], "total_brands": len(rivals)}
    return {"category": category, "window_days": d["summary"]["clash"]["window_days"], "creators": found}


def strip(ids: list[str]) -> dict[str, dict]:
    """Compact novelty strip for the dashboard cards: only what a card shows, per creator. Unknown ids are skipped; a missing part is None (never guessed)."""
    out: dict[str, dict] = {}
    for cid in ids:
        c = get_creator(cid)
        if c is None:
            continue
        mood = c.get("mood") or {}
        yt = (c.get("sponsored") or {}).get("youtube_views")
        out[cid] = {
            "grade": c["evidence"]["grade"],
            "mood": {"gap": mood.get("gap"), "significant": bool(mood.get("significant")), "label": mood.get("label")} if mood.get("gap") is not None else None,
            "speed_first_24h": (c.get("speed") or {}).get("share_first_24h"),
            "ad_load": c.get("fatigue"),
            "sponsored_views_percent": yt.get("approx_percent") if yt and yt.get("enough") else None,
            "linked_creators": (c.get("network") or {}).get("linked_creators", 0),
            "recent_brands": len(c.get("clash_events") or []),
        }
    return out
