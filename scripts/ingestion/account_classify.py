"""Per-account category classification from a real profile, at write time.

WHY THIS EXISTS (2026-08-17)
----------------------------
146 of 258 accepted sheet rows sat at `category='other'` because the two paths that
create rows never classified per account:

  - `collab_edges.py` hardcoded `category: "other"` for every co-author it pushed. At
    push time it holds only a handle scraped from a post header.
  - `discover_candidates.py` applies ONE `--category` hint to a whole run.

Last round repaired those 146 rows by hand. This module fixes the cause, so new rows get
a real category at write time.

NOTE ON "REUSE THE LOGIC FROM update_category()": `sheets_sync.update_category()` is a
*writer* — it takes a {handle: category} dict and writes cells. It contains no
classification logic; last round's categories came from a human reading each bio. So
there was nothing to literally reuse. This module is that missing piece, in ONE place,
imported by both call sites — which is the actual intent (one approach, not two).

`category` has a CHECK constraint accepting exactly:
    athlete · team · league · fitness_influencer · lifestyle_influencer · other
A wrong-but-valid value does NOT error, so a misclassification is silent. That is why
this module returns its evidence string: every decision is recorded in the notes column
and can be audited later without re-fetching.

CLASSIFICATION GUIDANCE (user, 2026-08-16):
    league          -> leagues AND sports federations/associations (closest fit)
    team            -> teams / clubs
    fitness_infl.   -> individual coaches & trainers posting their own content
    lifestyle_infl. -> actors, musicians, creators, podcasters, filmmakers
    other           -> coaching INSTITUTIONS/academies (organisational, not a person),
                       kept for breadth/discovery value
    BRAND           -> not a creator at all. Never gets a sheet row; the caller must
                       route it to the associated creator's `brand_signals` instead.

Word-boundary matching throughout: a bare substring test is the documented P1.3 bug
class in this project (`"mp"` matched "Madhya Pradesh" and silently dropped valid
candidates for ~14 cycles).
"""

import json
import os
import re
import shutil
import subprocess

import yaml

# CHECK-constraint values. Anything not in here hard-fails the insert.
VALID = {"athlete", "team", "league", "fitness_influencer", "lifestyle_influencer", "other"}

BRAND = "__BRAND__"   # sentinel: not a creator, route to brand_signals


def _words(*terms: str) -> re.Pattern:
    """Word-boundary alternation. Terms may contain spaces; regex-escaped."""
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in terms) + r")(?!\w)", re.I)


# --- BRAND markers. Deliberately high-precision: a false BRAND silently drops a real
# creator, which is worse than a row landing in review as a creator. Legal-entity
# suffixes and commerce verbs only -- NOT generic words like "official" or "store"
# that legitimately appear in athlete and team bios.
_BRAND_STRONG = _words(
    "pvt ltd", "pvt. ltd", "private limited", "ltd", "llp", "inc", "llc", "gmbh",
    "corporation", "enterprises",
)
_BRAND_COMMERCE = _words(
    "shop now", "buy now", "order now", "free shipping", "use code", "discount code",
    "our products", "official store", "flagship store", "worldwide shipping",
    # Added 2026-08-17 after inspecting real escapes: @gocolors ("India's leading
    # bottom-wear brand, 1200+ styles") and @eliore_essentials ("Elioré™ Luxury
    # Fragrances") both landed as candidate rows.
    #
    # ⚠️ The bare words "brand"/"brands"/"label" were tried here first and REVERTED --
    # they produced false BRANDs on real creators, which is the worst error this module
    # can make (a false BRAND silently drops a person instead of sending them to review):
    #   @singer_shaan  "Label: @shaanmusiclabel"          -> a musician's own record label
    #   @mohitvaru     "storytelling for brands & people" -> a photographer
    # and "For brand queries" appears in a large share of athlete bios. Product-category
    # nouns are safe; the bare word is not.
    "boutique", "couture", "apparel", "footwear", "menswear", "womenswear",
    "activewear", "sportswear", "cosmetics", "skincare", "fragrances", "eyewear",
    "jewellery", "jewelry", "showroom", "outlets", "franchise enquiry", "dealership",
)
# "brand" only when it reads as a self-description ("India's leading bottom-wear brand"),
# never as an inbound-enquiry line ("For brand queries").
_BRAND_PHRASE = re.compile(
    r"(?:leading|premium|luxury|official|home\s?grown|homegrown|clothing|fashion|"
    r"lifestyle)[\w\s'’-]{0,25}\bbrand\b|\bbrand\s+of\b", re.I)
# Trademark/registered symbols are near-decisive and are not word-boundary matchable.
_BRAND_SYMBOL = re.compile(r"[™®]")

# --- Organisational / institutional (NOT an individual). Ordered before individual
# checks because an academy bio often also says "coach".
_LEAGUE = _words(
    "league", "federation", "association", "championship", "governing body",
    "olympic association", "board of control", "premier league", "world championship",
)
_TEAM = _words(
    "football club", "cricket club", "fc", "cf", "official team", "squad",
    "franchise", "the official", "official account", "official ig", "official instagram",
)
_INSTITUTION = _words(
    "academy", "institute", "institution", "foundation", "trust", "ngo", "council",
    "centre of excellence", "center of excellence", "society",
)

# --- Individuals
# STRONG personal-athlete markers: unambiguously describe a PERSON, so they are tested
# BEFORE the organisational patterns. Real miss this fixes: P.T. Usha's bio reads
# "Olympian - Track & Field Athlete | Member of Parliament | President - Indian Olympic
# Association" — org-first classified a human athlete as a `league`.
_ATHLETE_STRONG = _words(
    "cricketer", "footballer", "olympian", "olympic medalist", "sprinter",
    "boxer", "wrestler", "badminton player", "tennis player", "basketball player",
    "professional cricketer", "professional footballer", "professional football player",
    "pro athlete", "international athlete", "batsman", "bowler", "all-rounder",
    "goalkeeper", "shuttler", "pro tennis player",
)
_ATHLETE = _words(
    "athlete", "national champion", "keeper", "all rounder", "midfielder", "striker",
    "javelin", "nba", "wnba", "ipl", "isl", "squad player",
)
_FITNESS = _words(
    "coach", "trainer", "personal trainer", "pt", "strength", "conditioning",
    "nutritionist", "nutrition", "physio", "physiotherapist", "fitness", "gym",
    "bodybuilding", "calisthenics", "yoga", "crossfit", "powerlifting", "wellness",
    "transformation", "weight loss",
    # Sports-science vocabulary: without these, an S&C specialist fell through to
    # lifestyle on the word "Director" (real miss: @waynelombardsa).
    "exercise", "exercise sci", "biokinetics", "s&c", "rehab", "recovery specialist",
    "performance specialist",
)
_LIFESTYLE = _words(
    "actor", "actress", "musician", "singer", "rapper", "composer", "filmmaker",
    "film maker", "director", "producer", "podcast", "podcaster", "content creator",
    "creator", "vlogger", "influencer", "youtuber", "comedian", "host", "anchor",
    "rj", "photographer", "model", "artist", "author", "writer", "entrepreneur",
    "speaker", "dancer", "music", "songs", "label", "band", "dj",
)


_SPORT_CONTEXT = _words(
    "cricket", "football", "badminton", "tennis", "hockey", "kabaddi", "athletics",
    "boxing", "wrestling", "basketball", "volleyball",
)


def classify_from_profile(name: str, bio: str, handle: str = "",
                           known_orgs: set[str] | None = None) -> tuple[str, str]:
    """Return (category_or_BRAND, evidence). Pure function — no I/O, so it is testable.

    Order matters and is deliberate:
      1. brand (legal entity / commerce) — must win, brands are not creators at all
      2. STRONG personal-athlete markers — a person who runs a federation is still a
         person; org-first got P.T. Usha wrong (see _ATHLETE_STRONG)
      3. league / team / institution (organisational) — an academy bio says "coach" too
      4. athlete (weaker) -> fitness -> lifestyle (individuals)
      5. 'other' only when nothing matched, and the evidence says so honestly
    """
    # The handle itself carries real signal (`singer_shaan`, `ishaanphysio`), but `_`
    # and `.` are word characters, so `\bsinger\b` never matches inside `singer_shaan`.
    # Normalising separators to spaces makes handle tokens matchable.
    handle_words = re.sub(r"[._\-]+", " ", handle or "")
    text = f"{name or ''} \n {bio or ''} \n {handle_words}".strip()
    if not (name or bio or handle):
        return "other", "no name or bio available"

    m = _BRAND_STRONG.search(text)
    if m:
        return BRAND, f"BRAND: legal-entity marker '{m.group(0)}'"
    m = _BRAND_COMMERCE.search(text)
    if m:
        return BRAND, f"BRAND: commerce language '{m.group(0)}'"
    m = _BRAND_SYMBOL.search(text)
    if m:
        return BRAND, f"BRAND: trademark symbol '{m.group(0)}'"
    m = _BRAND_PHRASE.search(text)
    if m:
        return BRAND, f"BRAND: self-describes as a brand ('{m.group(0)[:40]}')"

    m = _ATHLETE_STRONG.search(text)
    if m:
        return "athlete", f"athlete marker '{m.group(0)}'"

    # Institution BEFORE team: an academy/foundation bio routinely says "official" too,
    # which made @neerajchoprafoundation classify as a `team`.
    m = _INSTITUTION.search(text)
    if m:
        return "other", f"institutional (academy/foundation/council) marker '{m.group(0)}' — kept for breadth, not a standalone creator"
    m = _LEAGUE.search(text)
    if m:
        return "league", f"league/federation marker '{m.group(0)}'"
    m = _TEAM.search(text)
    if m:
        return "team", f"team/club marker '{m.group(0)}'"

    m = _ATHLETE.search(text)
    if m:
        return "athlete", f"athlete marker '{m.group(0)}'"
    m = _FITNESS.search(text)
    if m:
        return "fitness_influencer", f"fitness/coaching marker '{m.group(0)}'"
    m = _LIFESTYLE.search(text)
    if m:
        return "lifestyle_influencer", f"lifestyle/creator marker '{m.group(0)}'"

    # AFFILIATION SIGNAL — added 2026-08-17 after held-out validation scored only 30%,
    # with 18 of 21 errors being "-> other". Real bios are sparse: Ishan Kishan's entire
    # bio is "For business enquiries", and a keyword classifier can never reach it.
    # But players routinely @-mention the club/league they play for, and we already know
    # which handles are teams/leagues because they are creators in our own DB. Resolving
    # those mentions is a real signal that needs no extra fetch.
    if known_orgs:
        for mention in re.findall(r"@([A-Za-z0-9_.]+)", bio or ""):
            if mention.lower() in known_orgs:
                return "athlete", (f"affiliation: bio @-mentions '{mention}', a known "
                                    f"team/league in our creator set")

    # LAST RESORT before 'other': a bare sport word, on an account that already failed
    # every organisational test above. Marked low-confidence in the evidence so a review
    # pass can find these quickly.
    m = _SPORT_CONTEXT.search(text)
    if m:
        return "athlete", (f"LOW CONFIDENCE: sport context '{m.group(0)}' only, no explicit "
                            f"role — verify before relying on this")

    snippet = " ".join(text.split())[:70]
    return "other", f"UNCLASSIFIED — no marker matched (bio: '{snippet}')"


# ---------------------------------------------------------------- profile fetching

_OPENCLI = shutil.which("opencli")
_SESSION = "classify"


def _run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    profile = os.environ.get("OPENCLI_PROFILE")
    if profile:
        env["OPENCLI_PROFILE"] = profile
    return subprocess.run([_OPENCLI, *args], capture_output=True, text=True,
                           timeout=timeout, env=env, encoding="utf-8", errors="replace")


def fetch_profile(handle: str) -> dict | None:
    """(name, bio, followers) for a handle, or None if unreachable.

    Two independent transports, because they fail INDEPENDENTLY (verified 2026-08-16):
    `instagram profile` served 111 of 146 handles while 35 failed it persistently with
    HTTP 400 yet loaded fine in the browser — the exact inverse of the grid stall, where
    the browser failed and the adapter worked. Neither is a superset of the other.
    """
    try:
        r = _run(["instagram", "profile", handle, "-f", "yaml"])
        if r.returncode == 0:
            data = yaml.safe_load(r.stdout)
            if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("username"):
                d = data[0]
                return {"name": d.get("name") or "", "bio": d.get("bio") or "",
                        "followers": d.get("followers"), "via": "adapter"}
    except Exception:
        pass

    # Browser fallback: meta description carries counts AND the bio line, at a fraction
    # of a full page extract.
    # NO `||` IN THIS JS — opencli resolves via an npm .cmd shim, so cmd.exe re-parses
    # the argument and treats `||` as its OR operator, truncating the script.
    js = ("JSON.stringify({d:document.querySelector('meta[name=description]')?.content,"
          "t:document.title})")
    try:
        if _run(["browser", _SESSION, "open", f"https://www.instagram.com/{handle}/"]).returncode != 0:
            return None
        _run(["browser", _SESSION, "wait", "time", "3"])
        r = _run(["browser", _SESSION, "eval", js])
        out = (r.stdout or "").strip()
        s, e = out.find("{"), out.rfind("}")
        if r.returncode != 0 or s < 0:
            return None
        # Do NOT unescape \" before json.loads: the payload is already valid JSON and
        # bios legitimately contain quotes.
        payload = json.loads(out[s:e + 1])
        desc = payload.get("d") or ""
        if not desc:
            return None
        # "12K Followers, 34 Following, 56 Posts - NAME (@handle) on Instagram: "BIO""
        name, bio = "", ""
        m = re.search(r"Posts\s*-\s*(.*?)\s*\(@", desc)
        if m:
            name = m.group(1)
        m = re.search(r'on Instagram:\s*"(.*)"\s*$', desc, re.S)
        if m:
            bio = m.group(1)
        return {"name": name, "bio": bio, "followers": None, "via": "browser"}
    except Exception:
        return None
    finally:
        _run(["browser", _SESSION, "close"])


_DOMAIN = _words(
    "cricket", "football", "soccer", "badminton", "tennis", "hockey", "kabaddi",
    "athletics", "boxing", "wrestling", "basketball", "volleyball", "marathon",
    "training", "workout", "gym", "fitness", "match", "tournament", "league",
    "championship", "goal", "wicket", "innings", "runs", "squad", "practice",
    "season", "trophy", "medal", "team", "player", "sport", "sports",
)


def fetch_grid(handle: str, max_chars: int = 12000) -> list[str]:
    """Recent post alt-texts/captions from the profile grid.

    Required by the routing rule that a candidate's GRID — not just the bio — must show
    a clear majority of domain-relevant posts. It doubles as the best classification
    signal available: Instagram bios are frequently near-empty ("For business
    enquiries"), while the grid describes what the account actually posts.
    """
    if _run(["browser", _SESSION, "open", f"https://www.instagram.com/{handle}/"]).returncode != 0:
        return []
    _run(["browser", _SESSION, "wait", "time", "3"])
    r = _run(["browser", _SESSION, "extract"], timeout=90)
    if r.returncode != 0:
        return []
    try:
        md = (json.loads(r.stdout) or {}).get("content") or ""
    except Exception:
        return []
    # Grid entries render as ![<caption or alt text>](<cdn url>)
    alts = re.findall(r"!\[([^\]]{12,400})\]\(https://[^)]*fbcdn[^)]*\)", md[:max_chars * 4])
    out, seen = [], set()
    for a in alts:
        a = " ".join(a.split())
        if a.lower().startswith("photo by") and len(a) < 60:
            continue          # pure boilerplate, no content signal
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out[:25]


def grid_relevance(alts: list[str]) -> tuple[int, int, float]:
    """(relevant_posts, total_posts, ratio) by domain vocabulary over grid text."""
    if not alts:
        return 0, 0, 0.0
    rel = sum(1 for a in alts if _DOMAIN.search(a))
    return rel, len(alts), rel / len(alts)


def load_known_orgs(conn) -> set[str]:
    """Instagram handles of creators already classified team/league.

    Feeds the affiliation signal: a player's bio @-mentioning their club is often the
    ONLY usable signal, since sparse bios ("For business enquiries") defeat keywords.
    """
    with conn.cursor() as cur:
        cur.execute("select lower(instagram_handle) from creators "
                     "where instagram_handle is not null and category in ('team','league')")
        return {r[0] for r in cur.fetchall()}


def classify_handle(handle: str, known_orgs: set[str] | None = None,
                     use_grid: bool = True) -> dict:
    """Full write-time assessment of one candidate account.

    Returns {category, evidence, relevance_ratio, relevant, total, followers, name,
    reachable}. `category` may be the BRAND sentinel, in which case the caller MUST
    route it to `brand_signals` and must NOT create a sheet row.

    Bio first; grid only when the bio was inconclusive or the relevance check is wanted.
    Held-out validation showed bio-only classification reaching just ~47% agreement with
    human labels, because real bios are sparse — the grid is what closes that gap.
    """
    p = fetch_profile(handle)
    if p is None:
        return {"reachable": False, "category": "other", "evidence": "profile unreachable",
                "relevance_ratio": 0.0, "relevant": 0, "total": 0,
                "followers": None, "name": ""}

    cat, why = classify_from_profile(p["name"], p["bio"], handle, known_orgs)
    result = {"reachable": True, "category": cat, "evidence": why,
              "relevance_ratio": 0.0, "relevant": 0, "total": 0,
              "followers": p.get("followers"), "name": p.get("name") or ""}
    if cat == BRAND or not use_grid:
        return result

    alts = fetch_grid(handle)
    rel, tot, ratio = grid_relevance(alts)
    result.update({"relevance_ratio": round(ratio, 2), "relevant": rel, "total": tot})

    # Re-classify over bio + grid when the bio alone produced nothing usable. The grid
    # describes what the account actually posts, which is the stronger signal.
    if cat == "other" and alts:
        cat2, why2 = classify_from_profile(p["name"], p["bio"] + " \n " + " \n ".join(alts),
                                            handle, known_orgs)
        # ⚠️ A BRAND verdict from GRID TEXT is not admissible (2026-08-18). The brand rules
        # read product-category nouns ("skincare", "activewear", "sportswear") as evidence
        # that the ACCOUNT is a brand -- true of a bio, false of a caption, because creators
        # post about products constantly. Applied to grid text it inverts the meaning and
        # DROPS real people, which is the worst error this module can make. Real damage:
        #   brisonfernandes17_ (a Goan footballer) -> BRAND on 'sportswear'
        #   duamirzaasad       (a person)          -> BRAND on 'skincare'
        #   abhishekganguly    (a person)          -> BRAND on 'activewear'
        # Brand determination therefore stays bio/name-only; the grid may only refine the
        # CREATOR category.
        if cat2 == BRAND:
            result["evidence"] = (f"{why} — grid suggested BRAND ('{why2}') but grid text is "
                                   f"captions, not self-description; ignored")
        elif cat2 != "other":
            result["category"] = cat2
            result["evidence"] = f"{why2} (from grid, bio was inconclusive)"
    return result
