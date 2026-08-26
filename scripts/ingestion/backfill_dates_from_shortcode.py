"""Date Instagram posts from the post ID itself. No network calls at all.

WHY THIS EXISTS. 921 of 1,802 instagram_posts rows (51%) have no `posted_at`, and the
straddle test that defines a computable training pair cannot see an undated post. Measured
2026-08-21: 40 of the 104 event x neighbour checks that fail the BEFORE clause belong to
neighbours who ALREADY HAVE undated posts stored. That share of the gap is neither a
collection problem nor a recency-window problem -- the data is in the database without a
date on it. Every other route to a date (og:description, grid datetime attributes) needs one
browser page load per post, which is exactly the resource that keeps being unavailable.

HOW IT WORKS. An Instagram shortcode is the post's media id in base64 over the alphabet
below, and the media id's high bits are a millisecond timestamp measured from Instagram's
own epoch. So the date is already sitting inside the primary key.

    media_id = base64_decode(shortcode)
    posted_at = (media_id >> 23) + 1314220021721 ms

THE SHIFT WAS FITTED, NOT ASSUMED, and the fit is checked against real ground truth rather
than a reference someone wrote down. Scored against all 881 posts whose posted_at is already
known from an independent source (og:description text and grid datetime attributes -- NOT
from the shortcode, so this is not circular):

    shift=21    0/881 within 24h     median error 16,290 days
    shift=22    0/881 within 24h     median error  5,430 days
    shift=23  789/881 within 24h     median error      0.5 days   <-- this one
    shift=24    0/881 within 24h     median error  2,715 days

Full agreement profile at shift=23:  <=24h 789 | 24-48h 85 | 48-72h 2 | >72h 5.
That is 99.4% agreement within 72h. The 0.5-day median error is expected and not a defect:
og:description carries a DATE ONLY ("on May 9, 2026"), stored at midnight UTC, while the
shortcode carries the real posting instant -- so a half-day median gap is what perfect
agreement looks like, and the 85 rows in the 24-48h band are the same effect crossing a
day boundary. This incidentally answers the "+/-1-day dates" question left open in HANDOFF.

A DELIBERATE LIMIT: this only FILLS NULLS. It never overwrites an existing posted_at, even
though the decoded value is strictly more precise. The 5 rows disagreeing by more than 72h
cannot be decoder drift -- the decode is a pure function of an immutable primary key -- so
they are evidence that those STORED dates are wrong. Correcting stored data is a bigger call
than filling blanks and belongs to the user, so they are reported and left alone.

Run: python backfill_dates_from_shortcode.py [--dry-run]
"""

import argparse
import datetime
import logging

import psycopg2

from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("shortcode_dates")

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
INSTAGRAM_EPOCH_MS = 1314220021721
SHIFT = 23

# Refuse to write if the decoder stops agreeing with reality. A silent regression here would
# poison every date in the corpus, and unlike a bad scrape it would look completely plausible.
MIN_AGREEMENT = 0.95
AGREEMENT_WINDOW_HOURS = 72


def decode(shortcode: str):
    media_id = 0
    for ch in shortcode:
        if ch not in ALPHABET:
            return None
        media_id = media_id * 64 + ALPHABET.index(ch)
    try:
        return datetime.datetime.fromtimestamp(
            ((media_id >> SHIFT) + INSTAGRAM_EPOCH_MS) / 1000, datetime.timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def self_check(cur) -> float:
    """Score the decoder against every independently-dated post before touching anything."""
    cur.execute("select post_id, posted_at from instagram_posts where posted_at is not null")
    rows = cur.fetchall()
    if not rows:
        return 0.0
    agree = 0
    for pid, when in rows:
        d = decode(pid)
        if d and abs((d - when).total_seconds()) <= AGREEMENT_WINDOW_HOURS * 3600:
            agree += 1
    rate = agree / len(rows)
    log.info("self-check: decoder agrees with %d/%d independently-dated posts (%.1f%%) "
              "within %dh", agree, len(rows), 100 * rate, AGREEMENT_WINDOW_HOURS)
    return rate


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()

    if self_check(cur) < MIN_AGREEMENT:
        log.error("decoder agreement below %.0f%% -- refusing to write. Something about the "
                   "shortcode format or the stored dates has changed; re-fit before using this.",
                   100 * MIN_AGREEMENT)
        return

    cur.execute("select post_id from instagram_posts where posted_at is null")
    todo = [r[0] for r in cur.fetchall()]
    log.info("undated posts: %d", len(todo))

    filled = undecodable = 0
    for pid in todo:
        d = decode(pid)
        if d is None:
            undecodable += 1
            continue
        if not args.dry_run:
            cur.execute("update instagram_posts set posted_at=%s where post_id=%s and "
                         "posted_at is null", (d, pid))
        filled += 1
    if not args.dry_run:
        conn.commit()

    log.info("DONE filled=%d undecodable=%d%s", filled, undecodable,
              "  [DRY RUN, nothing written]" if args.dry_run else "")
    conn.close()


if __name__ == "__main__":
    main()
