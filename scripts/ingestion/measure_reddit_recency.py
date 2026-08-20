"""Measure how far back RELEVANT Reddit discussion actually goes, before touching the window.

WHY MEASURE FIRST. The recency window replaced the missing-name problem as Reddit's binding
constraint: r/india search for "Sunil Chhetri" returned 40 results with 0 off-topic and every
one was dropped as stale. The obvious move is to widen the window, and the obvious move is what
this project has been burned by before -- an earlier round widened Reddit's reach without
measuring relevance and had to purge 88% of the data as noise.

So this answers two questions separately, and neither by assumption:
  1. HOW OLD is the relevant discussion? (the date histogram of on-topic hits)
  2. Does going older mean going NOISIER? (relevance rate per age bucket)

If relevance holds steady as posts get older, widening recovers real signal. If relevance
collapses with age, the window is doing useful work and widening would re-import the noise the
purge removed. The point is to find out which, not to guess.

READ-ONLY. Writes nothing to the database.

Run: python measure_reddit_recency.py [--creators N] [--limit N]
"""

import argparse
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import time

import psycopg2

from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("recency")

_OC = shutil.which("opencli")


def oc_search(query: str, sub: str, limit: int) -> list:
    env = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        env["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    r = subprocess.run([_OC, "reddit", "search", query, "--subreddit", sub,
                        "--sort", "new", "--limit", str(limit), "-f", "json"],
                       capture_output=True, text=True, timeout=180, env=env,
                       encoding="utf-8", errors="replace")
    try:
        d = json.loads((r.stdout or "").strip())
    except Exception:
        return []
    return d if isinstance(d, list) else d.get("entries", [])


def mentions(post: dict, name: str) -> bool:
    """The same shape of relevance test the orchestrator's topic-search gate applies: the
    creator's name must actually appear, matched on word boundaries so a substring cannot
    manufacture a hit (the bug class that produced the earlier false-positive purge)."""
    blob = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
    parts = [p for p in re.split(r"\s+", name.lower()) if len(p) > 2]
    if not parts:
        return False
    return all(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", blob) for p in parts)


def age_days(post: dict, now: datetime.datetime):
    for key in ("created_utc", "created", "posted_at", "date"):
        v = post.get(key)
        if v is None:
            continue
        try:
            if isinstance(v, (int, float)):
                dt = datetime.datetime.fromtimestamp(float(v), datetime.timezone.utc)
            else:
                dt = datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return (now - dt).days
        except (ValueError, OSError, OverflowError):
            continue
    return None


# The first run's top bucket was an unbounded "2y+" that scored 100% on 71 results. That
# supports widening, but it does NOT characterise the range actually being adopted -- a
# 1095-day window reaches 3 years, and "2y+" cannot tell 2y from 8y apart. Split so the
# re-verification measures the range the window now admits instead of extrapolating into it.
BUCKETS = [(0, 90), (90, 183), (183, 365), (365, 730), (730, 1095), (1095, 100000)]
LABELS = ["0-90d", "90-183d (just outside)", "183-365d", "1-2y",
          "2-3y (newly admitted)", "3y+ (still excluded)"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--creators", type=int, default=12)
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("""
            select c.name, c.reddit_topic_subs
            from creators c
            where coalesce(array_length(c.reddit_topic_subs, 1), 0) > 0
              and lower(c.name) <> lower(coalesce(c.instagram_handle, ''))
            order by md5(c.name)
            limit %s
        """, (args.creators,))
        targets = cur.fetchall()
    conn.close()

    now = datetime.datetime.now(datetime.timezone.utc)
    rel = [0] * len(BUCKETS)
    tot = [0] * len(BUCKETS)
    undated = 0

    for name, subs in targets:
        for sub in subs[:2]:
            posts = oc_search(name, sub, args.limit)
            for p in posts:
                d = age_days(p, now)
                if d is None:
                    undated += 1
                    continue
                for i, (lo, hi) in enumerate(BUCKETS):
                    if lo <= d < hi:
                        tot[i] += 1
                        rel[i] += 1 if mentions(p, name) else 0
                        break
            log.info("%s in r/%s -> %d results", name, sub, len(posts))
            time.sleep(4)

    print(f"\n{'age bucket':<26}{'results':>9}{'on-topic':>10}{'relevance':>11}")
    for i, label in enumerate(LABELS):
        r = f"{100*rel[i]/tot[i]:.0f}%" if tot[i] else "-"
        print(f"{label:<26}{tot[i]:>9}{rel[i]:>10}{r:>11}")
    print(f"\nundated results: {undated}")
    print("Read it this way: if relevance holds steady across the older buckets, widening the "
           "window recovers real signal. If it collapses, the window is doing useful work.")


if __name__ == "__main__":
    main()
