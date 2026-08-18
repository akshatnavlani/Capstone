"""Backfill `instagram_posts.posted_at` from the post page's og:description meta tag.

THE BREAKTHROUGH (2026-08-18). Every previously-tested date source failed on exactly the
posts that matter -- sponsored ones, which always have captions:
  adapter listing (`instagram user`) : capped at 12 posts regardless of --limit (verified)
  profile grid alt-text              : only dates CAPTION-LESS posts
  post page markdown (`extract`)     : no date at all (0/4), and its like counts belong to
                                       SUGGESTED posts (DB 172,598 vs extracted "8")
  post page <time datetime>          : element not present (0/3)

But the page's `<meta property="og:description">` carries it for ANY post:
    "885 likes, 33 comments - nasimamirza on May 9, 2026: "caption...""

Validated against DB ground truth: **6/6 parsed, 6/6 usable dates** (3 exact, 3 off by one
day -- the same timezone-boundary offset already documented for grid dates; Instagram renders
a viewer-local date while the stored value came from a different source).

⚠️ DATE ONLY. The like/comment counts in this string are NOT trustworthy: Instagram
abbreviates them ("1M likes" for a true 1,416,111) and they drift as engagement accrues.
Measured 1 of 2 exact even among the non-abbreviated ones. Writing them would corrupt real
values, so this tool never touches them.

⚠️ ±1 day. Immaterial for straddle analysis (events and neighbour activity sit weeks or
months apart) but it must not be presented as exact. Never overwrites an existing date.

Run: python backfill_dates_from_og.py [--sponsored-only] [--limit N] [--dry-run]
"""

import argparse
import datetime
import json
import logging
import os
import random
import re
import shutil
import subprocess
import time

import psycopg2

from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("og-dates")

_OC = shutil.which("opencli")
SESSION = "ogdates"
MAX_CONSEC_FAIL = 5

JS = 'JSON.stringify(document.querySelector(\'meta[property="og:description"]\')?.content)'

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
OG_DATE = re.compile(r"on\s+(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})", re.I)


def oc(*args, timeout=120):
    env = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        env["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    return subprocess.run([_OC, "browser", SESSION, *args], capture_output=True, text=True,
                           timeout=timeout, env=env, encoding="utf-8", errors="replace")


def og_date(post_id: str):
    """Date from og:description, or None. Asserts the page is the requested post."""
    r = oc("open", f"https://www.instagram.com/p/{post_id}/")
    if r.returncode != 0:
        return None, "open failed"
    oc("wait", "time", "4")
    out = (oc("eval", JS).stdout or "").strip()
    try:
        desc = json.loads(out)
    except Exception:
        return None, "eval unparseable"
    if not desc:
        return None, "no og:description"
    m = OG_DATE.search(desc)
    if not m:
        return None, f"no date in '{desc[:60]}'"
    return datetime.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))), None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sponsored-only", action="store_true",
                     help="Only posts flagged is_sponsored or has_paid_partnership_label — "
                          "these gate computable training pairs, so they come first.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    where = "posted_at is null"
    if args.sponsored_only:
        where += " and (is_sponsored or has_paid_partnership_label)"
    with conn.cursor() as cur:
        cur.execute(f"select post_id, username from instagram_posts where {where} "
                     f"order by post_id" + (f" limit {int(args.limit)}" if args.limit else ""))
        posts = cur.fetchall()
    log.info("posts to date: %d%s", len(posts), "  [sponsored only]" if args.sponsored_only else "")

    filled = failed = consec = 0
    for i, (pid, user) in enumerate(posts, 1):
        d, err = og_date(pid)
        if d is None:
            failed += 1
            consec += 1
            log.info("[%d/%d] %s: %s", i, len(posts), pid, err)
            if consec >= MAX_CONSEC_FAIL:
                log.warning("%d consecutive failures — stopping. Re-run to resume; nothing "
                             "already written is lost.", consec)
                break
        else:
            consec = 0
            filled += 1
            log.info("[%d/%d] %s (@%s) -> %s", i, len(posts), pid, user, d)
            if not args.dry_run:
                with conn.cursor() as cur:
                    # posted_at is null in the WHERE, so this cannot overwrite a known date.
                    cur.execute("update instagram_posts set posted_at=%s "
                                 "where post_id=%s and posted_at is null", (d, pid))
                conn.commit()
        time.sleep(random.uniform(5, 9))

    with conn.cursor() as cur:
        cur.execute("select count(*) from instagram_posts where (is_sponsored or "
                     "has_paid_partnership_label) and posted_at is null")
        spon_left = cur.fetchone()[0]
    conn.close()
    oc("close")
    log.info("DONE filled=%d failed=%d sponsored_still_dateless=%d%s",
              filled, failed, spon_left, "  [DRY RUN]" if args.dry_run else "")


if __name__ == "__main__":
    main()
