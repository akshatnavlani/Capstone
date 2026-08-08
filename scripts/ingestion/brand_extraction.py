"""Brand-name lead extraction — Track A, bounded Weeks 3-4 scope.

Scope boundary (deliberately narrow, see SCHEMA.md "Brand data"): this ONLY pulls
brand-name candidates out of text already being collected on creator content rows
(captions/titles/bodies, and whatever disclosure phrase eventually lands in
sponsorship_raw_matches). It does NOT search for or discover brands independently.

This is explicitly NOT the precision-validated is_sponsored classifier — that's
Track C's Weeks 7-8 deliverable (PROJECT_PLAN.md Section 6, timeline row 7-8), and
per SCHEMA.md, Track A doesn't build a competing labeler. This module is a coarser
"lead generation" pass: its only job is to produce a candidate brand name so we know
which official account to scrape for the `brands` table. Track C's later, properly
validated pipeline is expected to review/correct is_sponsored and, ideally, the
brand_id linkage this produces — treat this module's output as a first-pass seed,
not an authoritative label.

Status: designed and unit-testable now; NOT yet run against real data, because there
is no real scraped content yet (Instagram/Reddit still blocked on the OpenCLI Chrome
extension, YouTube Data API key not yet provided — see DATA_COLLECTION_STATUS.md).
Once real captions/titles start landing via the orchestrator, wire this in as a step
between fetch and upsert for youtube_videos/instagram_posts/reddit_posts.
"""

import re
from dataclasses import dataclass

# Explicit disclosure phrasing — high confidence the captured group is a brand name.
# Brand name = 1-3 consecutive Capitalized words right after the trigger phrase (a
# proper-noun heuristic) — NOT a greedy character class, which was tested and found
# to over-capture trailing words ("Nike for this drop" instead of "Nike") since
# lowercase connector words like "for"/"this" don't stop a `[\w ]+`-style class.
# Trigger phrase is case-insensitive ((?i:...)); the captured brand name itself is
# NOT — that case-sensitivity is what makes the proper-noun heuristic work.
_BRAND_NAME = r"([A-Z][\w&.']*(?:\s+[A-Z][\w&.']*){0,2})"
_EXPLICIT_PATTERNS = [
    re.compile(r"(?i:in partnership with)\s+" + _BRAND_NAME),
    re.compile(r"(?i:sponsored by)\s+" + _BRAND_NAME),
    re.compile(r"(?i:thanks to)\s+" + _BRAND_NAME + r"\s+(?i:for )(?i:sponsoring|partnering)"),
    re.compile(r"(?i:paid partnership with)\s+" + _BRAND_NAME),
]

# Disclosure hashtags — confirm the post IS a sponsorship, but don't name the brand.
_DISCLOSURE_TAGS = re.compile(r"#(ad|sponsored|spon|partner|paidpartnership)\b", re.IGNORECASE)

# @mentions co-occurring with a disclosure tag are a lower-confidence brand candidate.
_MENTION = re.compile(r"@(\w+)")


@dataclass
class BrandMention:
    candidate_name: str
    matched_phrase: str
    confidence: str  # 'explicit' | 'mention'


def extract_brand_mentions(text: str) -> list[BrandMention]:
    """Best-effort brand-name leads from a single caption/title/body string.

    Not exhaustive, not precision-validated — see module docstring. Returns [] for
    text with no disclosure signal at all, which is the common case pre-labeling.
    """
    if not text:
        return []

    mentions: list[BrandMention] = []

    for pattern in _EXPLICIT_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1).strip().rstrip(".,!'")
            if name:
                mentions.append(BrandMention(name, m.group(0), "explicit"))

    if mentions:
        return mentions  # explicit phrasing found — don't dilute with weaker mention-guessing

    if _DISCLOSURE_TAGS.search(text):
        for m in _MENTION.finditer(text):
            mentions.append(BrandMention(m.group(1), m.group(0), "mention"))

    return mentions


if __name__ == "__main__":
    samples = [
        "Stoked to be in partnership with Nike for this drop! #ad",
        "Big thanks to Gatorade for sponsoring today's shoot",
        "#sponsored @underarmour check the new line",
        "just a normal Tuesday, no brands here",
    ]
    for s in samples:
        print(s, "->", extract_brand_mentions(s))
