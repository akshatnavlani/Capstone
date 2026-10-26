"""Backfill posted_at / like_count / comment_count by matching listing entries on CAPTION.

WHY CAPTION MATCHING (2026-08-18): `opencli instagram user` returns caption, date, likes,
comments and type -- but NO post id. orchestrator.py therefore matched the listing to the
browser's post-URL list POSITIONALLY, which is the unsafe pairing documented at
orchestrator.py:447: Instagram pins up to 3 posts to the top of a grid, so the two lists can
be offset and post N silently gets post M's date and likes.

Captions sidestep that completely. A caption is effectively a unique key within one
creator's recent posts, so a match is self-verifying and needs no ordering assumption.

Also fixes the metadata ceiling: the listing defaults to `--limit 12`, which is exactly why
only ~12 of ~40 posts per creator ever had metadata. This requests the full post cap.

Only fills NULLs. An existing value is never overwritten -- a disagreement is reported
instead, because the two sources have different timezone bases (grid dates were measured
running ~1 day earlier than adapter dates on near-midnight posts).

Run: python backfill_meta_by_caption.py --handles carryminati mostlysane [--limit 40] [--dry-run]
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
log = logging.getLogger("meta-backfill")

_OC = shutil.which("opencli")


def norm(s: str) -> str:
    """Normalise a caption for comparison: collapse whitespace, drop non-ascii."""
    s = re.sub(r"\s+", " ", (s or "")).strip().lower()
    return re.sub(r"[^a-z0-9 ]", "", s)[:180]


def fetch_listing(handle: str, limit: int) -> list[dict]:
    env = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        env["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    r = subprocess.run([_OC, "instagram", "user", handle, "--limit", str(limit), "-f", "json"],
                        capture_output=True, text=True, timeout=180, env=env,
                        encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if "429" in out:
        raise RuntimeError("HTTP 429")
    data = json.loads(r.stdout)
    return data if isinstance(data, list) else []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--handles", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    tot_dated = tot_liked = tot_conflict = tot_unmatched = 0
    consec_block = 0

    for handle in args.handles:
        try:
            listing = fetch_listing(handle, args.limit)
            consec_block = 0
        except RuntimeError as e:
            consec_block += 1
            log.warning("%s: %s", handle, e)
            if consec_block >= 2:
                log.warning("two consecutive 429s — stopping, the adapter is intermittent")
                break
            time.sleep(random.uniform(30, 60))
            continue
        except Exception as e:
            log.warning("%s: listing failed (%s)", handle, str(e)[:90])
            continue

        with conn.cursor() as cur:
            cur.execute("""select p.post_id, p.caption, p.posted_at, p.like_count, p.comment_count
                            from instagram_posts p join creators c on c.creator_id=p.creator_id
                            where lower(c.instagram_handle)=lower(%s) and p.caption is not null
                              and p.caption <> ''""", (handle,))
            by_caption = {}
            for pid, cap, dt, likes, cmts in cur.fetchall():
                by_caption.setdefault(norm(cap), (pid, dt, likes, cmts))

            dated = liked = conflict = unmatched = 0
            for item in listing:
                cap = norm(item.get("caption") or "")
                if not cap or cap not in by_caption:
                    unmatched += 1
                    continue
                pid, cur_dt, cur_likes, cur_cmts = by_caption[cap]
                raw = item.get("date")
                new_dt = None
                if raw:
                    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
                        try:
                            new_dt = datetime.strptime(raw, fmt).date()
                            break
                        except ValueError:
                            pass
                sets, vals = [], []
                if new_dt and cur_dt is None:
                    sets.append("posted_at=%s"); vals.append(new_dt); dated += 1
                elif new_dt and cur_dt and cur_dt.date() != new_dt:
                    conflict += 1
                if item.get("likes") is not None and cur_likes is None:
                    sets.append("like_count=%s"); vals.append(item["likes"]); liked += 1
                if item.get("comments") is not None and cur_cmts is None:
                    sets.append("comment_count=%s"); vals.append(item["comments"])
                if sets and not args.dry_run:
                    vals.append(pid)
                    cur.execute(f"update instagram_posts set {', '.join(sets)} where post_id=%s", vals)
        if not args.dry_run:
            conn.commit()
        log.info("%s: listing=%d matched-and-dated=%d likes-filled=%d conflicts=%d unmatched=%d",
                  handle, len(listing), dated, liked, conflict, unmatched)
        tot_dated += dated; tot_liked += liked
        tot_conflict += conflict; tot_unmatched += unmatched
        time.sleep(random.uniform(20, 40))

    with conn.cursor() as cur:
        cur.execute("select count(*) from instagram_posts where (is_sponsored or "
                     "has_paid_partnership_label) and posted_at is null")
        spon_dateless = cur.fetchone()[0]
    conn.close()
    log.info("DONE newly_dated=%d likes_filled=%d conflicts=%d unmatched=%d "
              "sponsored_still_dateless=%d%s", tot_dated, tot_liked, tot_conflict,
              tot_unmatched, spon_dateless, "  [DRY RUN]" if args.dry_run else "")


if __name__ == "__main__":
    main()
