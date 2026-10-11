"""Evidence for "this YouTube channel and this Instagram account are the same creator".

Pure functions, no database and no network. A link is accepted on evidence, never on a guess:

  strong  the Instagram handle appears in the channel description (or an instagram.com link), or the
          Instagram bio points at the channel
  medium  the creator's name matches the channel title, and the audience sizes are plausible together
  weak    the same handle text on both platforms (fan accounts copy handles, so this never counts alone)

Levels returned by `score_link`:
  confirmed  at least one strong sign and no fan-channel warning
  probable   name match AND plausible size (two medium signs)
  review     anything weaker, or a fan-channel warning: a person must look at it

The S8 audit of the live data motivates the rules: 2 to 4 of the 41 existing YouTube links were doubtful
(a channel titled "Fan's Club", a podcast instead of the person, links accepted on identical handle text only).
"""

from __future__ import annotations

import difflib
import re

# A channel whose own TITLE says it is a fan page is not the creator (description text like "thanks to my
# fans" is normal for the real channel, so only the title and explicit "unofficial / fan page" phrases count).
_FAN_TITLE = re.compile(r"\b(fans?|fan ?club|fan ?page|unofficial|tribute|edits?|clips|compilations?)\b", re.I)
# explicit fan-page wording only: a bare "unofficial" shows up in real merch taglines ("Unofficial attitude")
_FAN_PHRASE = re.compile(r"\b(unofficial (fan|page|account|channel)|fan ?page|fan ?account|fan ?club|not (affiliated|associated) with)\b", re.I)

# YouTube audience as a share of the Instagram audience. A fan channel is usually a tiny fraction, a
# different kind of account (a team channel, a podcast) can be far larger.
RATIO_MIN, RATIO_MAX = 0.02, 50.0


def _alnum(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _tokens(s: str | None) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) >= 3}


def names_match(names: list[str | None], titles: list[str | None]) -> bool:
    """Any creator-side name matches any channel-side name: shared words, containment, or near-equal text."""
    for a in names:
        for b in titles:
            ta, tb = _tokens(a), _tokens(b)
            if ta and tb and len(ta & tb) / len(ta | tb) >= 0.5:
                return True
            aa, bb = _alnum(a), _alnum(b)
            if aa and bb and (difflib.SequenceMatcher(None, aa, bb).ratio() >= 0.8 or (len(aa) >= 6 and (aa in bb or bb in aa))):
                return True
    return False


def score_link(
    creator_name: str | None,
    ig_username: str | None,
    ig_full_name: str | None,
    ig_bio: str | None,
    ig_followers: int | None,
    yt_handle: str | None,
    yt_title: str | None,
    yt_description: str | None,
    yt_subscribers: int | None,
) -> dict:
    ig = _alnum(ig_username)
    desc = (yt_description or "").lower()
    strong: list[str] = []
    if len(ig) >= 5 and ig in _alnum(yt_description):
        strong.append("Instagram handle appears in the channel description")
    elif ig and f"instagram.com/{ig_username.lower().lstrip('@')}" in desc:
        strong.append("channel description links to the Instagram account")
    yh = _alnum(yt_handle)
    if (len(yh) >= 5 and yh in _alnum(ig_bio)) or ("youtube.com/" in (ig_bio or "").lower() and yh and yh in _alnum(ig_bio)):
        strong.append("Instagram bio points at the channel")

    medium: list[str] = []
    name_ok = names_match([creator_name, ig_full_name], [yt_title, yt_handle])
    if name_ok:
        medium.append("creator name matches the channel")
    ratio = None
    size_ok = False
    if yt_subscribers and ig_followers:
        ratio = yt_subscribers / ig_followers
        size_ok = RATIO_MIN <= ratio <= RATIO_MAX
        if size_ok:
            medium.append("audience sizes are plausible together")

    weak = ["same handle text on both platforms"] if ig and ig == yh else []

    flags: list[str] = []
    if _FAN_TITLE.search(yt_title or "") or _FAN_PHRASE.search(yt_description or ""):
        flags.append("channel looks like a fan page")
    if ratio is not None and not size_ok:
        flags.append(f"audience mismatch (YouTube is {ratio:.3f} of Instagram)")
    if not ig_followers and not ig_bio:
        flags.append("Instagram side not collected: cannot be verified yet")

    if "channel looks like a fan page" in flags:
        level = "review"
    elif strong:
        level = "confirmed"
    elif name_ok and size_ok:
        level = "probable"
    else:
        level = "review"
    return {"level": level, "strong": strong, "medium": medium, "weak": weak, "flags": flags, "ratio": ratio}
