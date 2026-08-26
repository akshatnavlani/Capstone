"""Disclosure-tag (is_sponsored) labeling pipeline (PROJECT_PLAN.md Section
2 "Sponsorship Labeling" / Section 1). This is the SOLE source of GAIL's
treatment labels (via Track A's `creator_sponsorship_events` view) --
precision matters more here than almost anywhere else in the system, per
PROJECT_PLAN.md Section 1: "undisclosed/untagged sponsorships will simply
be invisible to GAIL as training signal" (false negatives are somewhat
tolerable -- missed signal, not wrong signal) but a false positive
poisons a training label outright, so patterns are written to require an
unambiguous disclosure convention, not a loose keyword match. See
backend/tests/test_labeling.py for validation against real scraped
content (ATHLEAN-X self-promotional links, institutional bio text) plus
deliberate near-miss/decoy cases, not just obvious positive examples.

Regex-based, matching PROJECT_PLAN.md Section 1's own framing ("#ad,
#sponsored, 'in partnership with', including variants/misspellings").
Each pattern requires a real word boundary so it can't fire inside an
unrelated longer word/hashtag (e.g. "#ad" must not match "#adidas" or
"#adventure"; "spon-con" must not match "spontaneous").
"""

import re

# (compiled pattern, human-readable label for sponsorship_raw_matches audit trail)
_SPONSORSHIP_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"#ad\b", re.IGNORECASE), "#ad"),
    (re.compile(r"#sponsored\b", re.IGNORECASE), "#sponsored"),
    (re.compile(r"#spon\b", re.IGNORECASE), "#spon"),
    (re.compile(r"#paidpartnership\b", re.IGNORECASE), "#paidpartnership"),
    (re.compile(r"\bsponsored\s+by\b", re.IGNORECASE), "sponsored by"),
    (re.compile(r"\bpaid\s+partnership\b", re.IGNORECASE), "paid partnership"),
    (re.compile(r"\bpaid\s+promotion\b", re.IGNORECASE), "paid promotion"),
    (re.compile(r"\bin\s+partnership\s+with\b", re.IGNORECASE), "in partnership with"),
    (re.compile(r"\bbrought\s+to\s+you\s+by\b", re.IGNORECASE), "brought to you by"),
    # Common misspellings of "sponsor(ed)" -- e.g. "sponser", "sponsered".
    (re.compile(r"\bsponser(?:ed|ship|s)?\b", re.IGNORECASE), "sponser* (misspelling)"),
    (re.compile(r"\bspon[\s-]?con\b", re.IGNORECASE), "spon-con"),
]


def detect_sponsorship(*texts: str | None) -> tuple[bool, list[str]]:
    """Checks one or more text fields (e.g. title + description) for a
    disclosure convention. Returns (is_sponsored, matched_raw_phrases) --
    matched_raw_phrases is the actual substring matched (not the pattern
    label), for `sponsorship_raw_matches` (auditing the labeler's own
    precision later, per PROJECT_PLAN.md Section 1).
    """
    combined = " ".join(t for t in texts if t)
    if not combined:
        return False, []

    matches = []
    for pattern, _label in _SPONSORSHIP_PATTERNS:
        for m in pattern.finditer(combined):
            matches.append(m.group(0))

    return bool(matches), matches
