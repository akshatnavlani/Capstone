"""READ-ONLY audit of the 1 Nov standing-code un-flag (no database writes).

For every video the fix un-flagged, decide whether it was the start of a deal
(new_onset), a new campaign code (new_code) or a repeat (standing); see
ml/standing_code_audit.py. Writes:

  models/standing_code_audit.csv    one row per un-flagged video
  models/standing_code_sample.csv   5 random videos per label, for a quick spot check

Usage:
    python scripts/audit_standing_codes.py [--backup-table standing_code_backup_20261101]
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.standing_code_audit import Video, classify  # noqa: E402

ID_COLUMNS = ("video_id", "youtube_video_id", "id")
BRAND_COLUMNS = ("brand_id", "brand_name", "brand")


def database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("DATABASE_URL not set and not found in .env")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-table", default="standing_code_backup_20261101")
    ap.add_argument("--window", type=int, default=30)
    args = ap.parse_args()

    conn = psycopg2.connect(database_url())
    conn.set_session(readonly=True)
    cur = conn.cursor()

    cur.execute("select column_name from information_schema.columns where table_name = %s", (args.backup_table,))
    cols = [r[0] for r in cur.fetchall()]
    if not cols:
        sys.exit(f"table {args.backup_table} not found")
    id_col = next((c for c in ID_COLUMNS if c in cols), None)
    if id_col is None:
        sys.exit(f"no video id column in {args.backup_table}; columns are: {cols}")
    brand_col = next((c for c in BRAND_COLUMNS if c in cols), None)

    # Un-flagged videos and their brand name (from the backup if it kept one, else the video row).
    if brand_col == "brand_id":
        brand_sql = "(select name from brands where brand_id = b.brand_id)"
    elif brand_col:
        brand_sql = f"b.{brand_col}::text"
    else:
        brand_sql = "(select name from brands where brand_id = v.brand_id)"
    cur.execute(f"""
        select v.video_id::text, coalesce({brand_sql}, (select name from brands where brand_id = v.brand_id))
          from {args.backup_table} b
          join youtube_videos v on v.video_id::text = b.{id_col}::text
    """)
    unflagged = {vid: brand for vid, brand in cur.fetchall()}
    print(f"{len(unflagged)} un-flagged videos found in {args.backup_table}", flush=True)

    cur.execute("""
        select video_id::text, creator_id::text, published_at, coalesce(title, ''), coalesce(description, '')
          from youtube_videos
         where published_at is not null and creator_id in (
               select creator_id from youtube_videos where video_id::text = any(%s))
    """, (list(unflagged),))
    by_creator: dict[str, list[Video]] = defaultdict(list)
    videos: dict[str, Video] = {}
    for vid, creator, published, title, desc in cur.fetchall():
        v = Video(vid, creator, published, title, desc)
        by_creator[creator].append(v)
        videos[vid] = v

    rows, skipped = [], 0
    for vid, brand in unflagged.items():
        v = videos.get(vid)
        if v is None or not brand:
            skipped += 1
            continue
        r = classify(v, brand, by_creator[v.creator], args.window)
        rows.append({"video_id": vid, "creator_id": v.creator, "published": v.published.date().isoformat(),
                     "brand": brand, **r, "title": v.title[:120]})

    out = ROOT / "models" / "standing_code_audit.csv"
    out.parent.mkdir(exist_ok=True)
    if rows:
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        rng = random.Random(0)
        sample = []
        for label in ("new_onset", "new_code", "standing"):
            group = [r for r in rows if r["label"] == label]
            sample += rng.sample(group, min(5, len(group)))
        with open(ROOT / "models" / "standing_code_sample.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(sample)

    counts = Counter(r["label"] for r in rows)
    creators = defaultdict(Counter)
    for r in rows:
        creators[r["creator_id"]][r["label"]] += 1
    print(f"classified {len(rows)} (skipped {skipped}: no matching video or no brand name)")
    for label in ("new_onset", "new_code", "standing"):
        print(f"  {label:10s} {counts[label]}")
    print(f"  creators with at least one new_onset: {sum(1 for c in creators.values() if c['new_onset'])} "
          f"of {len(creators)}")
    print(f"Wrote {out} and models/standing_code_sample.csv (spot-check the sample)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
