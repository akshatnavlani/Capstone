"""Resolve a real name for handle-named creators via Wikipedia, for well-known figures only.

Third name source, after `instagram_profiles` (DB-side, reach ~8 of 200) and the live Instagram
profile fetch (`backfill_real_names.py`, the high-reach one). This one exists for creators whose
Instagram profile carries no usable name but who are notable enough to have an article.

USES PLAIN HTTP, NOT THE BROWSER. urllib straight to en.wikipedia.org touches no OpenCLI tab
lease, so this is safe to run alongside Instagram or Reddit work -- the same reasoning that
makes the YouTube Data API safe (see ORCHESTRATION.md). Do not "optimise" it onto the browser
path; that would reintroduce the contention this project has already measured twice.

⚠️ WIKIPEDIA SEARCH IS FUZZY AND WILL HAPPILY RETURN A WRONG PERSON. Real observed results:
    timdavid8      -> ['Tim David', 'Tim David Kelly', 'Tim Davie']
    carryminati    -> ['CarryMinati', 'Carrie Nation', 'Carrinatia gens']
Taking result[0] unverified would have written "Carrie Nation" onto a creator whose handle
merely rhymes. So every hit must pass `verifies()` below: the handle's letters must equal, or
prefix, the article title's letters.

That gate is deliberately strict and it REJECTS REAL NAMES rather than risk a wrong one:
    chetri_sunil11 -> 'Sunil Chhetri'   rejected (name order reversed, spelling differs)
Leaving that creator unresolved is the correct outcome -- a fabricated name is far worse than
a missing one, and the surname/given-name order cannot be verified from the handle alone.

Rate limit: Wikipedia returned HTTP 429 after ~16 rapid requests, so calls are paced.

Run: python resolve_names_wikipedia.py [--dry-run] [--limit N]
"""

import argparse
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import psycopg2

from assign_reddit_subs import looks_like_real_name
from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("wiki-names")

# Wikipedia asks for a descriptive User-Agent identifying the client.
UA = {"User-Agent": "CapstoneResearch/1.0 (academic influencer-brand study; non-commercial)"}
PACE_SECONDS = 2.0


def letters(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def wiki_search(query: str, limit: int = 3) -> list[str]:
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "opensearch", "search": query, "limit": limit,
         "namespace": 0, "format": "json"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
            return json.load(r)[1]
    except urllib.error.HTTPError as e:
        if e.code == 429:
            log.warning("Wikipedia 429 — backing off 30s")
            time.sleep(30)
        return []
    except Exception:
        return []


def verifies(handle: str, title: str) -> bool:
    """Only accept a title the handle actually corroborates."""
    h, t = letters(handle), letters(title)
    if len(h) < 5 or len(t) < 5:
        return False
    # Equal ("shubmangill" / "Shubman Gill"), or the handle is an abbreviation of a longer
    # title ("sunrisershyd" / "Sunrisers Hyderabad").
    #
    # The REVERSE direction -- title a prefix of the handle -- was tried and REMOVED: it
    # accepted any article whose title merely opens the handle, e.g. @sagarliftz matching
    # the article "Sagar". No genuine case needs it, and it manufactures names.
    return h == t or t.startswith(h)


def resolve(handle: str):
    """-> (title, why) or (None, why). Tries the raw handle, then letters-only."""
    for query in (handle, letters(handle)):
        if not query:
            continue
        for title in wiki_search(query):
            if verifies(handle, title):
                return title, f"wikipedia '{title}' verified against handle"
        time.sleep(PACE_SECONDS)
    return None, "no verifiable wikipedia article"


GATED = """
    select c.creator_id, c.instagram_handle
    from creators c
    where c.instagram_handle is not null
      and lower(c.name) = lower(c.instagram_handle)
      and not exists (select 1 from reddit_posts r where r.creator_id = c.creator_id)
      and not exists (select 1 from reddit_post_creators r where r.creator_id = c.creator_id)
      and coalesce(array_length(c.reddit_topic_subs, 1), 0) = 0
      and coalesce(array_length(c.reddit_handles, 1), 0) = 0
    order by c.instagram_handle
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute(GATED)
        gated = cur.fetchall()
    if args.limit:
        gated = gated[: args.limit]
    log.info("still name-gated after the Instagram pass: %d", len(gated))

    resolved = unresolved = 0
    for i, (cid, handle) in enumerate(gated, 1):
        title, why = resolve(handle)
        if title and looks_like_real_name(title, handle):
            resolved += 1
            log.info("[%d/%d] %s -> %r  (%s)", i, len(gated), handle, title, why)
            if not args.dry_run:
                with conn.cursor() as cur:
                    cur.execute("update creators set name=%s where creator_id=%s", (title, cid))
                conn.commit()
        else:
            unresolved += 1
            log.info("[%d/%d] %s: %s", i, len(gated), handle, why)
        time.sleep(PACE_SECONDS)

    conn.close()
    log.info("DONE resolved=%d unresolved=%d%s", resolved, unresolved,
              "  [DRY RUN]" if args.dry_run else "")


if __name__ == "__main__":
    main()
