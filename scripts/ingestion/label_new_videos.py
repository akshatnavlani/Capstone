"""Run the rule-based sponsorship detector on YouTube videos added since a given time (the older-history backfill adds videos with no label). Safe to re-run.

    python label_new_videos.py --since "2026-10-29 10:00+00" --dry-run
    python label_new_videos.py --since "2026-10-29 10:00+00"

WHY (29 Oct 2026): youtube_backfill_history.py stores videos without any sponsorship decision, so every new video counts as "not sponsored" in the analyses. This labels only the rows
created since --since (so earlier hand decisions, such as the 19 posts unflagged on 27 Oct, are never touched). Same detector and rules as the 12 Oct label pass
(sponsorship_detector.detect; a creator's repeated footer lines are ignored, computed over ALL of the creator's saved descriptions). Never flips true to false; every changed row is
backed up in youtube_videos_sponsor_backup_20261012; a brand is set only when it already exists in `brands` (no new brands are created).
"""
import argparse
import collections
import json
import sys

import psycopg2

from orchestrator import ENV
from sponsorship_detector import boilerplate_lines, detect

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", required=True, help="only videos created_at >= this timestamp")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select video_id, creator_id::text, coalesce(title,''), coalesce(description,''), is_sponsored, created_at >= %s from youtube_videos where duration_seconds is not null and creator_id is not null", (args.since,))
    rows = cur.fetchall()
    per = collections.defaultdict(list)
    for r in rows:
        per[r[1]].append(r[3])
    bp = {cid: boilerplate_lines(ds) for cid, ds in per.items()}
    cur.execute("select lower(name), brand_id from brands")
    by_name = dict(cur.fetchall())
    new = [r for r in rows if r[5]]
    flagged = changed = with_brand = 0
    tiers = collections.Counter()
    for vid, cid, title, desc, flag, _ in new:
        d = detect(desc, False, title=title, boilerplate=bp[cid])
        if not d.is_sponsored or flag:
            continue
        flagged += 1
        bid = by_name.get(d.brand_name.lower()) if d.brand_name else None
        tiers[d.evidence_type] += 1
        with_brand += bid is not None
        if args.dry_run:
            continue
        cur.execute("insert into youtube_videos_sponsor_backup_20261012 (video_id, old_is_sponsored, old_raw, old_brand_id) select video_id, is_sponsored, sponsorship_raw_matches, brand_id from youtube_videos where video_id=%s on conflict do nothing", (vid,))
        cur.execute("update youtube_videos set is_sponsored=true, sponsorship_raw_matches=%s::jsonb, sponsorship_evidence=%s, brand_id=coalesce(%s, brand_id) where video_id=%s and is_sponsored is not true",
                    (json.dumps(d.evidence), d.evidence_type, bid, vid))
        changed += cur.rowcount
    if not args.dry_run:
        conn.commit()
    print(f"{len(new)} new videos checked; {flagged} would be / were marked sponsored ({with_brand} with a known brand); rows written: {changed}; by evidence type: {dict(tiers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
