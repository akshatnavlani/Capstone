"""Candidate discovery — Track A (Data/Infra), pivot round (2026-08-10).

Implements the "identify" phase of PROJECT_PLAN.md's revised identify -> curate ->
deepen process: cheap, broad candidate discovery (name/handle/category only, no deep
per-handle verification — that doesn't scale to ~1,000 candidates, see PROJECT_PLAN.md
and HANDOFF.md). Human review in the Google Sheet is the real quality gate at this
scale, not this script.

Discovery mechanism, verified real 2026-08-10 before building this (not assumed):
- `opencli instagram search <query>` does literal username/display-name substring
  matching, NOT semantic "accounts about X" discovery — tested with `search fitness`,
  got tiny unrelated accounts with "fitness" in the handle. Not useful here.
- Hashtag/tag pages ARE useful: `instagram.com/explore/tags/<tag>/` renders a real
  post grid; each post's page (opened via the same `browser open` + `find --css`
  pattern orchestrator.py already uses for profile grids) can be resolved to its
  author via a markdown-structure regex (see `find_post_author` below), confirmed
  against a real extracted post.

Author-detection approach: in `browser <session> extract`'s markdown, comment authors
and the post's own author both appear as `[username](/username/)` links, but ONLY the
post author's link is immediately followed by a relative-age token ("12w", "3d") before
any other content — confirmed against a real post (single match in the whole document,
which was the actual author, not a commenter).

Output: appends to `candidate_staging.json` (approval_status left blank, matches the
Sheet's schema) rather than writing to the Sheet directly — Sheet write access needs
the user to authorize the claude.ai Sheets MCP connector first (see HANDOFF.md). Once
that's done, staged candidates get pushed in one batch; this script doesn't assume
write access exists.

Run: python discover_candidates.py --tags fitness,gym,indianfitness --max-posts-per-tag 15
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import time

import yaml

import sheets_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("discover")

_OPENCLI_BIN = shutil.which("opencli")
if not _OPENCLI_BIN:
    raise RuntimeError("opencli not found on PATH")

STAGING_PATH = os.path.join(os.path.dirname(__file__), "candidate_staging.json")
TARGET_LIST_PATH = os.path.join(os.path.dirname(__file__), "target_list.json")

# Same "post author's username link is immediately followed by a relative-age token"
# structure used to isolate the author from commenters — see module docstring.
_AUTHOR_LINK = re.compile(r"\[\s*\n*\s*[A-Za-z0-9_.\\]+\s*\n*\s*\]\(/([A-Za-z0-9_.]+)/\)\s*\n*\s*\d+[smhdwy]\b")

# Minimum follower floor from PROJECT_PLAN.md Section 1 ("5k+ followers").
FOLLOWER_FLOOR = 5000


def with_retry(fn, *args, label: str = "", **kwargs):
    """Retry policy for flaky opencli calls (not stopping the loop on transient
    failures): 3 quick retries (~60s apart), then check session health via
    `opencli doctor` and re-raise for the CALLER to decide whether to skip -- the
    caller sets candidates aside rather than blocking the whole run on one stuck call.
    """
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            return fn(*args, **kwargs)
        except RuntimeError as e:
            last_err = e
            log.info("%s: attempt %d/3 failed: %s", label, attempt + 1, e)
            if attempt < 2:
                time.sleep(60)
    # 3 quick retries exhausted -- check whether this is session/auth-related rather
    # than assuming a pure rate limit.
    try:
        doctor = subprocess.run(
            [_OPENCLI_BIN, "doctor"], capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace",
        )
        log.info("%s: opencli doctor after repeated failures:\n%s", label, doctor.stdout)
    except Exception:
        pass
    raise last_err


def run_opencli(*args: str, timeout: int = 60) -> dict | list:
    env = dict(os.environ)
    env.setdefault("OPENCLI_PROFILE", os.environ.get("OPENCLI_PROFILE", ""))
    result = subprocess.run(
        [_OPENCLI_BIN, *args], capture_output=True, text=True, timeout=timeout, env=env,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"opencli {' '.join(args)} failed: {result.stdout}{result.stderr}")
    return yaml.safe_load(result.stdout)


def find_post_author(markdown: str) -> str | None:
    m = _AUTHOR_LINK.search(markdown)
    return m.group(1) if m else None


def discover_post_links_from_tag(tag: str, session: str, max_posts: int) -> list[str]:
    run_opencli("browser", session, "open", f"https://www.instagram.com/explore/tags/{tag}/")
    run_opencli("browser", session, "wait", "time", "2")
    try:
        found = run_opencli("browser", session, "find", "--css",
                             'a[href*="/reel/"], a[href*="/p/"]',
                             "--limit", str(max_posts))
        links = [e["attrs"]["href"] for e in found.get("entries", [])]
    except RuntimeError:
        links = []
    return list(dict.fromkeys(links))[:max_posts]


def author_for_post(post_path: str, session: str) -> str | None:
    post_url = f"https://www.instagram.com{post_path}"
    run_opencli("browser", session, "open", post_url)
    run_opencli("browser", session, "wait", "time", "2")
    extracted = run_opencli("browser", session, "extract")
    markdown = extracted["content"] if isinstance(extracted, dict) else str(extracted)
    return find_post_author(markdown)



# Soft India signal for the bio -- PROJECT_PLAN.md's coverage is "India-preferred, not
# a hard restriction" (per the earlier target-list-diversification decision), so this
# annotates candidates rather than rejecting non-Indian ones outright.
_INDIA_BIO_SIGNAL = re.compile(
    r"\b(india|indian|mumbai|delhi|bengaluru|bangalore|hyderabad|chennai|pune|kolkata|"
    r"ahmedabad|jaipur|lucknow|🇮🇳)\b", re.IGNORECASE,
)

# Real finding (2026-08-10 loop round): #fitindia is ALSO the name of a real government
# campaign ("Fit India Movement"), so hashtag search on it pulled in a sitting MP
# (rajeev_chandrasekhar) and an unrelated cinema/meme page (wtf.cinema) alongside real
# creators — hashtag hit alone is not a relevance signal, only the bio is. Broad,
# campaign/institution-adjacent tags (#fitindia) are more prone to this than
# creator-specific ones (#indianbodybuilder, #indianfitnessmodel) — treat hits from the
# former with extra scrutiny.
_EXCLUDE_BIO_SIGNAL = re.compile(
    r"\b(mla|minister|member of parliament|bjp|congress party|aap party|shiv sena|"
    r"member,? parliament|government of india|ministry of|govt\. of|"
    r"news|journalist|anchor|production house|film studio|box office|movie review)\b",
    re.IGNORECASE,
)
# Bare "mp" removed 2026-08-10 (cycle 15 self-audit): a real bug, not a small one --
# "MP" is Madhya Pradesh's standard state abbreviation and appears constantly in
# ordinary Indian bios as a location tag ("Bhopal, MP"), not just "Member of
# Parliament". Wrongly excluded ameensdq (a genuine content creator) on that basis.
# Real politicians are still caught via "minister"/"mla"/party names (confirmed:
# rajeev_chandrasekhar's exclusion also matched "minister" independently).
# "iaf"/"indian army" removed 2026-08-10 (cycle 3 self-audit): a real elite boxer's own
# bio ("Indian Boxer CWG Champion... INDIAN ARMY SOLDIER") got excluded by this --
# many legitimate Indian athletes are Services personnel (a common, real career path
# for national-level boxers/wrestlers), so military affiliation alone isn't an
# institutional-account signal the way "government of india"/"ministry of" is.

# Self-audit catch (2026-08-10, cycle 2): brsge.groups slipped through as
# "fitness_influencer" with a bio reading "BHARAT RESEARCH SPORTS EDUCATION,
# ENVIRONMENT & SOCIAL GROUP DEVELOPMENT TRUST" -- an NGO/trust, not an individual
# creator. Only applied to individual-creator categories, NOT team/league, where
# "federation"/"trust"/"association" language is often the legitimate real thing.
_EXCLUDE_INSTITUTIONAL_SIGNAL = re.compile(
    r"\b(trust|foundation|ngo|charitable society|non-?profit|development group|"
    r"research (?:group|organisation|organization))\b",
    re.IGNORECASE,
)
_INDIVIDUAL_CREATOR_CATEGORIES = {"fitness_influencer", "athlete", "lifestyle_influencer", "other"}

# Category -> keywords that would appear in a genuinely relevant creator's bio.
_RELEVANCE_KEYWORDS = {
    "fitness_influencer": [
        "coach", "trainer", "fitness", "gym", "workout", "bodybuilder", "bodybuilding",
        "calisthenics", "crossfit", "strength", "nutrition", "personal training",
        "physique", "powerlifting", "lifting",
        # "yoga" was missing entirely (cycle 18) despite running #yogaindia and
        # #yogateacherindia across multiple prior cycles -- real gap, real cost.
        "yoga", "yoga instructor", "yogi", "zumba", "pilates", "dietitian",
        "nutritionist", "physiotherapist", "rehab",
    ],
    "athlete": [
        "athlete", "sprinter", "olympian", "olympics", "track", "national team",
        "marathon", "runner", "boxer", "boxing", "wrestler", "wrestling", "badminton",
        "cricketer", "cricket", "footballer", "football player",
        # Transliterated Hindi terms (cycle 8) -- regional-language hashtags surface
        # real candidates whose bios use these instead of the English equivalent;
        # without them every regional-tag hit defaulted to "low confidence" even
        # when the bio was a clear match (e.g. "kushti" = wrestling).
        "kushti", "pahalwan", "akhada", "kabaddi", "kho kho",
        # More sports not originally covered (cycle 9) -- "squash player" slipped
        # through as low-confidence despite being an unambiguous athlete bio.
        "squash", "tennis player", "swimmer", "swimming", "shooter", "archery",
        "weightlifter", "weightlifting", "gymnast", "kabaddi player",
        "ironman", "triathlon", "triathlete",
    ],
    # Real bug found in self-audit (cycle 6): "official account" as an exact phrase
    # never matches real team bios like "Official Mumbai Indians account for IPL" --
    # the word "official" alone, plus league/competition names, catch these correctly.
    "team": ["team", "club", "official", "fc ", "cricket club", "ipl", "isl", "bcci"],
    "league": ["league", "federation", "association"],
    "lifestyle_influencer": ["creator", "content creator", "vlogger", "influencer"],
    "other": [],
}


def relevance_reason(bio: str, category: str) -> tuple[str, bool]:
    """Judge relevance from the bio text, not the hashtag that surfaced the candidate.

    Returns (one-line reason for the notes column, is_relevant). is_relevant=False for
    bios matching the exclusion set (political/government/media/entertainment) even if
    a keyword also happens to match — exclusion wins.
    """
    bio_lower = bio.lower()
    if _EXCLUDE_BIO_SIGNAL.search(bio):
        snippet = bio.strip().replace("\n", " ")[:80]
        return f"EXCLUDED: bio reads as political/government/media, not a creator -- '{snippet}'", False
    if category in _INDIVIDUAL_CREATOR_CATEGORIES and _EXCLUDE_INSTITUTIONAL_SIGNAL.search(bio):
        snippet = bio.strip().replace("\n", " ")[:80]
        return f"EXCLUDED: bio reads as an NGO/trust/institution, not an individual creator -- '{snippet}'", False
    keywords = _RELEVANCE_KEYWORDS.get(category, [])
    matched = [kw for kw in keywords if kw in bio_lower]
    if matched:
        snippet = bio.strip().replace("\n", " ")[:80]
        return f"bio: '{snippet}' -- matches {matched[0]}, clear match", True
    if not bio.strip():
        return "hashtag hit only, empty bio -- low confidence", True
    snippet = bio.strip().replace("\n", " ")[:80]
    return f"hashtag hit only, bio ('{snippet}') doesn't confirm relevance -- low confidence", True


def profile_check(handle: str) -> dict | None:
    """Lightweight relevance check: follower floor + bio-based relevance judgment (see
    relevance_reason). Not deep verification — the Sheet review is the real quality
    gate at this scale (see module docstring). Raises RuntimeError on a fetch failure
    (caller retries via with_retry) — returns None only for a genuine below-floor miss.
    """
    result = run_opencli("instagram", "profile", handle, "-f", "yaml")
    row = result[0] if isinstance(result, list) else result
    followers = row.get("followers") or row.get("follower_count") or 0
    if isinstance(followers, str):
        followers = int(re.sub(r"[^\d]", "", followers) or 0)
    if followers < FOLLOWER_FLOOR:
        return None
    bio = row.get("bio") or row.get("biography") or ""
    return {"followers": followers, "bio": bio, "india_signal": bool(_INDIA_BIO_SIGNAL.search(bio))}


def load_known_handles() -> set[str]:
    known: set[str] = set()
    for path in (TARGET_LIST_PATH, STAGING_PATH):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        for r in rows:
            h = r.get("instagram_handle")
            if h:
                known.add(h.lower())
    return known


def load_staging() -> list[dict]:
    if not os.path.exists(STAGING_PATH):
        return []
    with open(STAGING_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_staging(rows: list[dict]) -> None:
    with open(STAGING_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


# Team/league creator handles, populated once per discover() run.
_KNOWN_ORGS: set[str] = set()


def discover(tags: list[str], max_posts_per_tag: int, category_hint: str) -> tuple[list[dict], list[str]]:
    known = load_known_handles()
    staged = load_staging()
    new_rows: list[dict] = []
    retry_later: list[str] = []

    # Team/league handles, loaded once: a bio @-mentioning a known club is often the
    # only usable signal on a sparse profile.
    global _KNOWN_ORGS
    try:
        import psycopg2

        import account_classify
        from orchestrator import ENV
        _conn = psycopg2.connect(ENV["DATABASE_URL"])
        _KNOWN_ORGS = account_classify.load_known_orgs(_conn)
        _conn.close()
    except Exception as e:
        log.warning("could not load known team/league handles: %s", e)
        _KNOWN_ORGS = set()

    for tag in tags:
        session = f"disc_{tag}"
        log.info("tag=%s: fetching post grid", tag)
        try:
            post_links = with_retry(discover_post_links_from_tag, tag, session, max_posts_per_tag,
                                     label=f"tag-grid:{tag}")
        except RuntimeError as e:
            log.warning("tag=%s: grid fetch failed after retries, skipping this tag: %s", tag, e)
            retry_later.append(f"tag:{tag} (grid fetch)")
            continue
        log.info("tag=%s: %d post links found", tag, len(post_links))

        for path in post_links:
            try:
                handle = with_retry(author_for_post, path, session, label=f"author:{path}")
            except RuntimeError as e:
                log.info("tag=%s post=%s: author extraction failed after retries, skipping: %s", tag, path, e)
                retry_later.append(f"post:{path}")
                continue
            if not handle or handle.lower() in known:
                continue
            known.add(handle.lower())  # dedup within/across this run too

            try:
                check = with_retry(profile_check, handle, label=f"profile:{handle}")
            except RuntimeError as e:
                log.info("%s: profile check failed after retries, setting aside for retry: %s", handle, e)
                retry_later.append(f"handle:{handle}")
                continue
            if check is None:
                log.info("tag=%s: %s rejected (below follower floor)", tag, handle)
                continue

            reason, is_relevant = relevance_reason(check["bio"], category_hint)
            if not is_relevant:
                log.info("tag=%s: %s excluded -- %s", tag, handle, reason)
                continue

            india_note = ", India signal in bio" if check["india_signal"] else ""

            # PER-ACCOUNT CATEGORY (2026-08-17). `category_hint` is a single value for
            # the WHOLE run, so a run themed "fitness_influencer" labelled every account
            # it found that way regardless of what the account actually is. It is now a
            # fallback only, used when the real profile can't be classified.
            cat, cat_why = category_hint, f"run hint '{category_hint}' (not classified)"
            try:
                import account_classify
                a = account_classify.classify_handle(handle, _KNOWN_ORGS, use_grid=False)
                if a["category"] == account_classify.BRAND:
                    # Brands never become candidate rows. No owning creator exists on the
                    # hashtag path, so the signal is held rather than attached (see the
                    # standing rule: hold until an associated creator row exists).
                    log.info("tag=%s: %s is a BRAND (%s) -- not staged as a candidate",
                              tag, handle, a["evidence"])
                    continue
                if a["reachable"] and a["category"] != "other":
                    cat, cat_why = a["category"], a["evidence"]
            except Exception as e:
                log.warning("classify failed for %s: %s -- falling back to run hint", handle, e)

            row = {
                "name": handle,
                "category": cat,
                "instagram_handle": handle,
                "follower_count": check["followers"],
                "notes": f"discovered via #{tag}, {check['followers']} followers{india_note} "
                          f"-- {reason}; category: {cat_why}",
                "approval_status": "",
            }
            new_rows.append(row)
            log.info("tag=%s: staged %s (%d followers) -- %s", tag, handle, check["followers"], reason)

            # Push immediately, per-candidate, rather than batching a pile before
            # writing — lets the user start reviewing while discovery keeps running.
            try:
                sheets_sync.push_candidates([row])
            except Exception as e:
                log.warning("sheet push failed for %s, will retry from local staging: %s", handle, e)

        try:
            run_opencli("browser", session, "close")
        except RuntimeError:
            pass  # best-effort tab-lease release; a failure here shouldn't kill the run

    save_staging(staged + new_rows)
    return new_rows, retry_later


if __name__ == "__main__":
    import sys
    # Windows console defaults to cp1252, which crashes on real bio/emoji text --
    # same fix already applied in instagram_comment_extract.py's demo section.
    sys.stdout.reconfigure(errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", required=True, help="comma-separated hashtags, no # prefix")
    parser.add_argument("--max-posts-per-tag", type=int, default=15)
    parser.add_argument("--category", default="fitness_influencer",
                         help="category label applied to all candidates found this run")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    found, retry_later = discover(tags, args.max_posts_per_tag, args.category)
    print(f"\n{len(found)} new candidates staged -> {STAGING_PATH}")
    for r in found:
        print(f"  {r['instagram_handle']}: {r['notes']}")
    if retry_later:
        print(f"\n{len(retry_later)} set aside for retry: {retry_later}")
