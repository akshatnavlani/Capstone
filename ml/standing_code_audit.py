"""Classify videos un-flagged by the 1 Nov standing-affiliate-code fix.

The fix set is_sponsored = false on weak-tier videos whose brand appears in at
least half of the creator's videos within +-30 days. That is right for the
repeats of a standing deal, but a standing deal still STARTS somewhere, and a
new promo code can mean a new campaign. This module decides, per un-flagged
video, which of three it is:

  new_onset   the brand is absent from the creator's previous `window` days:
              the start of the deal, a real sponsorship event
  new_code    the video's promo code for the brand appears in none of the
              creator's other videos within +-window days: likely a new campaign
  standing    neither: a repeat of the same code block

`top_of_description` (brand within the first TOP_CHARS characters) is reported
as a supporting signal only; footers are usually link blocks, sponsor reads sit
near the top.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

TOP_CHARS = 300
_CODE = re.compile(r"(?:code|coupon|promo)\s*[:\-]?\s*[\"'“]?([A-Za-z0-9][A-Za-z0-9_\-]{2,19})", re.I)
_STOP = {"for", "and", "the", "here", "below", "link", "use", "get", "off", "at", "to", "now", "with"}


@dataclass
class Video:
    video_id: str
    creator: str
    published: datetime
    title: str
    description: str


def mentions(text: str, brand: str) -> int:
    """Position of the brand name in the text (case-insensitive, whole word), or -1."""
    m = re.search(r"(?<!\w)" + re.escape(brand.lower()) + r"(?!\w)", text.lower())
    return m.start() if m else -1


def codes(text: str) -> set[str]:
    """Promo codes written as 'code XYZ', 'coupon: XYZ', 'promo code "XYZ"'."""
    return {c.upper() for c in _CODE.findall(text) if c.lower() not in _STOP}


def classify(v: Video, brand: str, creator_videos: list[Video], window: int = 30) -> dict:
    """Label one un-flagged video. `creator_videos` is all of the creator's videos."""
    lo, hi = v.published - timedelta(days=window), v.published + timedelta(days=window)
    near = [o for o in creator_videos
            if o.video_id != v.video_id and lo <= o.published <= hi
            and mentions(o.title + "\n" + o.description, brand) >= 0]
    onset = not any(o.published < v.published for o in near)
    mine = codes(v.description)
    seen = set().union(*(codes(o.description) for o in near)) if near else set()
    new_code = bool(mine) and bool(mine - seen)
    pos = mentions(v.description, brand)
    label = "new_onset" if onset else "new_code" if new_code else "standing"
    return {"label": label, "onset": onset, "new_code": new_code,
            "top_of_description": 0 <= pos < TOP_CHARS,
            "codes": " ".join(sorted(mine)), "brand_videos_nearby": len(near)}
