"""Instagram comment extraction via OpenCLI generic browser automation.

Real finding (2026-08-09): `opencli instagram user/profile` has no comment-text read
path at all (only aggregate counts — see DATA_COLLECTION_STATUS.md Section 4b). But
`opencli browser <session> extract` on an opened post page returns the rendered page
as markdown, and Instagram's comment section IS rendered into that markdown — comment
author, text, like count, and a permalink containing a real comment ID are all present.
This module parses that markdown. No Apify needed; tried this route first per the
user's own suggested fallback order and it worked.

Pipeline (see orchestrator TODOs):
  1. opencli browser <session> open <profile_url>
  2. opencli browser <session> find --css 'a[href*="/reel/"], a[href*="/p/"]'
     -> post URLs (profile-grid links have no query params to worry about)
  3. For each post URL: opencli browser <session> open <post_url>
  4. opencli browser <session> extract  -> markdown with comments embedded
  5. parse_comments() on that markdown

Not yet wired into the orchestrator — this is the parser. Tested 2026-08-09 against
two real posts of different types (`/reel/` and `/p/`, 15 comments each, 30 total),
including multi-paragraph comments and heavy emoji use — all parsed correctly. Not yet
run at any real volume/across many posts, so treat this as validated-in-principle, not
load-tested. Comment ordering in the DOM roughly follows what Instagram's client
considers top comments; there is no guarantee of completeness or chronological order,
and heavily-commented posts are truncated by Instagram's own initial render (a "View
all N replies" link for threads beyond the first reply, not the full thread, plus a
"[+N more]"-style truncation for very long comment lists) — this captures what's
rendered on first load, not the full comment set. Apify was the user's suggested
fallback if OpenCLI couldn't do this; wasn't needed since this approach worked on the
first real attempt (with two real bugs found and fixed along the way — see git log).
"""

import re
from dataclasses import dataclass

# Anchors each comment: a link to `/{post_or_username}/.../c/{comment_id}/` — this
# permalink format was confirmed present in a real extracted post's markdown.
_COMMENT_PERMALINK = re.compile(r"\]\(/[^)]*?/c/(\d+)/\)")

# The username, as a markdown link: [\n\nusername\n\n\n](/username/) — appears twice
# per comment (once as the avatar-image link, once as the display-name link); we take
# whichever match is closest to the comment permalink. Markdown escapes underscores in
# usernames (kozmo\_spacely) — confirmed against a real extract, first draft of this
# regex missed it entirely (0 matches) both for that reason and for requiring an
# end-of-string anchor that doesn't hold once there's trailing text in the window.
_USERNAME_LINK = re.compile(r"\[\s*\n*\s*([A-Za-z0-9_.\\]+)\s*\n*\s*\]\(/([A-Za-z0-9_.]+)/\)")

_LIKE_COUNT = re.compile(r"^([\d,]+)\s+likes?$", re.MULTILINE)


@dataclass
class ExtractedComment:
    comment_id: str
    author_username: str
    text: str
    like_count: int | None


def parse_comments(markdown: str) -> list[ExtractedComment]:
    """Best-effort parse of Instagram comments out of a `browser extract` markdown dump.

    Not guaranteed complete (see module docstring) — this is a real-data-validated
    parser for what IS present in the initial page render, not a claim of full
    comment-thread retrieval.
    """
    comments: list[ExtractedComment] = []
    permalink_matches = list(_COMMENT_PERMALINK.finditer(markdown))

    for i, m in enumerate(permalink_matches):
        comment_id = m.group(1)
        segment_start = m.end()
        segment_end = permalink_matches[i + 1].start() if i + 1 < len(permalink_matches) else len(markdown)
        segment = markdown[segment_start:segment_end]

        preceding = markdown[:m.start()]
        username_match = None
        for candidate in _USERNAME_LINK.finditer(preceding[-400:]):
            username_match = candidate  # keep the last (closest) match in the window
        if not username_match:
            continue
        username = username_match.group(2)  # URL slug, not the escaped display text

        like_match = _LIKE_COUNT.search(segment)
        like_count = int(like_match.group(1).replace(",", "")) if like_match else None

        text_block = segment.split("\n\n")
        text = next((t.strip() for t in text_block if t.strip() and "likes" not in t and t.strip() not in ("Reply",) and "View all" not in t), "")

        comments.append(ExtractedComment(comment_id, username, text, like_count))

    return comments


if __name__ == "__main__":
    import json
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print("usage: python instagram_comment_extract.py <path to saved `opencli browser extract` JSON output>")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    # `opencli browser extract` wraps the markdown in a JSON envelope
    # ({url, title, ..., content}) — unwrap it if present, else treat as raw markdown.
    try:
        raw = json.loads(raw)["content"]
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    found = parse_comments(raw)
    # Windows console (cp1252) can't encode emoji in real comment text — reconfigure
    # stdout to UTF-8 with replacement so the demo doesn't crash on real data.
    sys.stdout.reconfigure(errors="replace")
    print(f"{len(found)} comments parsed")
    for c in found:
        print(c)


# Caption regex — the post's own caption sits right after the SECOND occurrence of the
# author's profile link (the first is the avatar image link) and a relative-time marker
# ("6w", "2d", "1h"), and runs until the first comment's avatar image block begins.
_CAPTION_RE_TMPL = r"\]\(/{user}/\)\s*\n+\s*\d+[smhdwy]\s*\n+(.*?)(?=\n\s*\[!\[|\Z)"


def parse_caption(markdown: str, username: str) -> str | None:
    """Full post caption from a `browser extract` markdown dump.

    Why this exists: `opencli instagram user` truncates captions to exactly 100
    characters in its listing output. That silently cost real signal — Track C flagged
    the Virat Kohli / Agilitas caption as truncated while deciding whether it is a
    valid sponsorship training pair, and brand extraction was also matching against
    only the first 100 chars. The page extract (already fetched for comments) carries
    the complete text, so there is no extra request cost to getting it right.

    Returns None when the pattern doesn't match, so callers can fall back to the
    truncated listing caption rather than losing the field entirely.
    """
    if not markdown or not username:
        return None
    pattern = re.compile(_CAPTION_RE_TMPL.format(user=re.escape(username)), re.DOTALL)
    m = pattern.search(markdown)
    if not m:
        return None
    caption = re.sub(r"\s*\n\s*", " ", m.group(1)).strip()
    return caption or None
