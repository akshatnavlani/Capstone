"""Rule-based sponsorship detector for a video description / Instagram caption.

WHY: is_sponsored was true for 3 of ~5,800 YouTube videos, so creator_sponsorship_events (the label source
for GAIL) was almost empty. This marks a post sponsored only when the text carries real evidence:
  - the platform's own paid-partnership label, or
  - a known brand together with a discount code, an @mention of the brand or a disclosure tag, or
  - an explicit disclosure tag (#ad, #sponsored, #paidpartnership, "sponsored by", "paid promotion").
A discount code on its own (no known brand, no disclosure) is NOT enough: it is returned as a candidate for
hand review. Description lines that repeat on 4+ of the same creator's videos are a standing footer (an
affiliate block pasted on every upload): they are ignored, except that a brand named in the TITLE together with
a code or disclosure anywhere in the description still counts.
The evidence strings go into sponsorship_raw_matches in the same list-of-strings style the table already uses
('#Ad', 'native:paid_partnership_label').

These are rules, not human labels. Measure their precision on a hand-checked sample before quoting them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from known_brands import all_strong_brands, match_known_brands

_DISCLOSURE = re.compile(
    r"(#\s*ad\b|#\s*sponsored|#\s*paidpartnership|#\s*paid\s*promotion|paid\s+partnership|paid\s+promotion|"
    r"sponsored\s+by|sponsored\s+post|brought\s+to\s+you\s+by)",
    re.I,
)
_PROMO_CODE = re.compile(r"(use\s+code|promo\s*code|coupon\s*code|discount\s*code|code\s*[:\-–—=]\s*[\"“'‘]?[A-Za-z0-9]{3,}|\bcode\s+(?-i:[\"“'‘*]?[A-Z0-9]{4,}\b))", re.I)


_NEGATION = re.compile(r"\b(no|not|non|never|without|un)[\s\-]*$", re.I)

BOILERPLATE_MIN_REPEATS = 4


def normalize_line(line: str) -> str:
    """Lowercase, links removed, spaces collapsed, so the same footer line compares equal across videos."""
    return re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", line.lower())).strip()


def boilerplate_lines(descriptions: list[str]) -> set[str]:
    """Lines (15+ characters) that appear in at least BOILERPLATE_MIN_REPEATS of one creator's descriptions."""
    counts: dict[str, int] = {}
    for d in descriptions:
        for line in {normalize_line(x) for x in (d or "").splitlines()}:
            if len(line) >= 15:
                counts[line] = counts.get(line, 0) + 1
    return {line for line, n in counts.items() if n >= BOILERPLATE_MIN_REPEATS}


@dataclass
class Detection:
    is_sponsored: bool
    evidence: list[str] = field(default_factory=list)
    brand_name: str | None = None
    candidate_only: bool = False  # promo code seen but not enough to call it sponsored


def detect(description: str | None, has_paid_partnership_label: bool = False, *, title: str = "",
           boilerplate: frozenset[str] | set[str] = frozenset()) -> Detection:
    evidence: list[str] = []
    brand_name = None
    if has_paid_partnership_label:
        evidence.append("native:paid_partnership_label")
    full = f"{title}\n{description or ''}"
    kept = "\n".join(x for x in (description or "").splitlines() if normalize_line(x) not in boilerplate)
    text = f"{title}\n{kept}"
    for m in _DISCLOSURE.finditer(text):
        if _NEGATION.search(text[max(0, m.start() - 8):m.start()]):  # "NO PAID PROMOTION", "not sponsored"
            continue
        tag = re.sub(r"\s+", " ", m.group(1).lower())
        if f"disclosure:{tag}" not in evidence:
            evidence.append(f"disclosure:{tag}")
    names = []
    for b in all_strong_brands(text):
        evidence.append(f"brand:{b.name}({'+'.join(b.signals)})")
        names.append(b.name)
    # a brand named in the title, with a code or disclosure anywhere in the (full) description
    if title and (_PROMO_CODE.search(full) or _DISCLOSURE.search(full)):
        for m in match_known_brands(title):
            if m.name not in names:
                evidence.append(f"brand:{m.name}(title+code)")
                names.append(m.name)
    if names:
        brand_name = names[0]
    if evidence:
        return Detection(True, evidence, brand_name)
    return Detection(False, [], None, candidate_only=bool(_PROMO_CODE.search(full)))
