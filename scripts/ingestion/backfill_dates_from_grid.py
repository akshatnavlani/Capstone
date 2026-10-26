"""Backfill `instagram_posts.posted_at` from profile-grid alt-text, browser-only.

WHY THIS PATH (2026-08-18): the `opencli instagram user/profile` adapter has been returning
HTTP 429 for four rounds -- on the FIRST request even at 25-50s human pacing, so it is not a
frequency problem. The browser path (`browser open` + `extract`) works at the same moment,
which is why collection now runs through it.

WHAT IS AND IS NOT EXTRACTABLE — measured against ground truth, not assumed:
  post page  : date 0/4, comment count 0/4, like count 2/4 but WRONG (172,598 -> "8";
               228,603 -> "3,132") because the numbers on the page belong to SUGGESTED
               posts. Unusable; parsing it would write corrupt data.
  profile grid: image alt-text carries "on <Month D, YYYY>" for SOME posts, and those dates
               agree with the DB 4/4 with 0 disagreements. Trustworthy where present.

KNOWN CEILING: Instagram uses the CAPTION as alt-text when a post has one, and only falls
back to "Photo by X on <date>" boilerplate when it does not. So captioned posts -- which
includes most sponsored posts -- generally do NOT expose a date here. This tool reports that
hit rate honestly rather than implying full coverage.

Pacing is deliberately conservative: the browser path working today does not mean it is
immune, only that it is not yet flagged. Backs off on repeated failure instead of probing
for the ceiling.

Run: python backfill_dates_from_grid.py --handles carryminati mostlysane [--scrolls 8] [--dry-run]
"""

import argparse
import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
from datetime import datetime

import psycopg2

from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("grid-dates")

_OC = shutil.which("opencli")
SESSION = "griddates"
MON = (r"(?:January|February|March|April|May|June|July|August|September|October|November|"
       r"December)\s+\d{1,2},\s+\d{4}")
PAIR_RE = re.compile(
    r"!\[([^\]]{5,400})\]\([^)]*fbcdn[^)]*\)\s*\n*\s*\]\(/[A-Za-z0-9_.]+/(?:p|reel)/([A-Za-z0-9_-]+)/\)")


def oc(*args, timeout=150):
    env = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        env["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    return subprocess.run([_OC, "browser", SESSION, *args], capture_output=True, text=True,
                           timeout=timeout, env=env, encoding="utf-8", errors="replace")


def grid_dates(handle: str, scrolls: int) -> dict[str, datetime.date]:
    """{post_id: date} harvested from one profile grid, scrolling to reach older posts."""
    r = oc("open", f"https://www.instagram.com/{handle}/")
    if r.returncode != 0:
        raise RuntimeError(f"open failed: {(r.stdout + r.stderr)[:120]}")
    oc("wait", "time", "5")
    found: dict[str, datetime.date] = {}
    seen_pairs = 0
    for i in range(scrolls):
        r = oc("extract")
        if r.returncode == 0:
            try:
                md = json.loads(r.stdout).get("content") or ""
            except Exception:
                md = ""
            pairs = PAIR_RE.findall(md)
            seen_pairs = max(seen_pairs, len(pairs))
            for alt, pid in pairs:
                m = re.search(r"on\s+(" + MON + r")", alt)
                if m and pid not in found:
                    found[pid] = datetime.strptime(m.group(1), "%B %d, %Y").date()
        oc("scroll", "down")
        time.sleep(random.uniform(2.5, 4.5))   # let lazy-load settle, and stay unhurried
    log.info("%s: %d grid entries seen, %d carried a date", handle, seen_pairs, len(found))
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handles", nargs="+", required=True)
    ap.add_argument("--scrolls", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    total_new = total_conflict = 0
    consec_fail = 0

    for handle in args.handles:
        try:
            dates = grid_dates(handle, args.scrolls)
            consec_fail = 0
        except Exception as e:
            consec_fail += 1
            log.warning("%s: grid failed (%s)", handle, str(e)[:100])
            if consec_fail >= 2:
                log.warning("two consecutive grid failures — backing off rather than pushing on")
                break
            continue

        new = conflict = 0
        with conn.cursor() as cur:
            for pid, d in dates.items():
                cur.execute("select posted_at::date, is_sponsored, has_paid_partnership_label "
                             "from instagram_posts where post_id=%s", (pid,))
                row = cur.fetchone()
                if not row:
                    continue
                existing, spon, paid = row
                if existing is None:
                    if not args.dry_run:
                        cur.execute("update instagram_posts set posted_at=%s where post_id=%s",
                                     (d, pid))
                    new += 1
                    if spon or paid:
                        log.info("   SPONSORED post %s dated %s", pid, d)
                elif existing != d:
                    # Never overwrite a known-good date with a disagreeing one; report it.
                    conflict += 1
                    log.warning("   CONFLICT %s: grid=%s db=%s (left unchanged)", pid, d, existing)
        conn.commit()
        log.info("%s -> %d newly dated, %d conflicts", handle, new, conflict)
        total_new += new
        total_conflict += conflict
        time.sleep(random.uniform(15, 30))     # between creators

    oc("close")
    with conn.cursor() as cur:
        cur.execute("select count(*) from instagram_posts where posted_at is null")
        remaining = cur.fetchone()[0]
    conn.close()
    log.info("DONE newly_dated=%d conflicts=%d posts_still_dateless=%d%s",
              total_new, total_conflict, remaining, "  [DRY RUN]" if args.dry_run else "")


if __name__ == "__main__":
    main()
