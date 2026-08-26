"""Text scrubbing + temporal normalization (PROJECT_PLAN.md Section 2).

Edge Pre-processing, Basic Preprocessing items 1-2: temporal normalization
(UTC) and text scrubbing (URLs/HTML/mentions) so BERT gets cleaner input in
Track B's Weeks 9-10 embedding step.
"""

import re
from datetime import datetime, timezone

_URL_RE = re.compile(r"https?://\S+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MENTION_RE = re.compile(r"@\w+")
_WHITESPACE_RE = re.compile(r"\s+")


def scrub_text(text: str | None) -> str:
    """Strips URLs, HTML tags, and @mentions; collapses whitespace.

    Order matters: URLs first (a mention-like string could appear inside a
    URL's path/query and get mangled by the mention regex otherwise), then
    HTML tags, then mentions, then whitespace collapse last so removals
    don't leave visible double-spaces.
    """
    if not text:
        return ""
    text = _URL_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _MENTION_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_to_utc(dt: datetime | None) -> datetime | None:
    """Returns a timezone-aware UTC datetime.

    Naive datetimes are assumed to already be UTC (the common case for
    timestamps parsed from platform APIs that report UTC without an
    explicit offset) rather than the local machine's timezone -- silently
    assuming local time would be wrong far more often. Timezone-aware
    datetimes are converted to UTC properly, not just relabeled.

    Note: Postgres `timestamptz` columns (used throughout Track A's schema)
    already normalize to UTC internally regardless of what's inserted, so
    this mostly matters for values before they reach the DB, or non-DB
    sources (CSV imports, API payloads with mixed offsets).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
