"""Where creator-to-creator links drop out before they can become exposure.

A link (A -> @B) only yields exposed observations when B is a creator we
hold, B has enough posts, A has dated sponsorships, and B has posts on both
sides of one of them. This module holds the pure pieces; the database
script is scripts/audit_collab_funnel.py.
"""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta

from ml.creator_links import _norm

# @handle not preceded by a word char or dot (skips emails), 2-30 chars, no trailing dot.
_MENTION = re.compile(r"(?<![\w.@])@([A-Za-z0-9_](?:[A-Za-z0-9_.]{0,28}[A-Za-z0-9_])?)(?![\w@]|\.[A-Za-z]{2,4}\b)")


def mentions(text: str) -> set[str]:
    """Normalised @handles in a caption or description; e-mail addresses are skipped."""
    return {_norm(m) for m in _MENTION.findall(text or "")}


def straddles(event: datetime, post_times: list[datetime], window_days: int) -> bool:
    """B has a post strictly before and strictly after the event, each within the window.
    `post_times` must be sorted."""
    lo, hi = event - timedelta(days=window_days), event + timedelta(days=window_days)
    before = bisect_left(post_times, event) - bisect_left(post_times, lo)
    after = bisect_right(post_times, hi) - bisect_right(post_times, event)
    return before > 0 and after > 0
