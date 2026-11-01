"""Fetch comments for recent long YouTube videos of the core 150 that have none yet. Costs 1 quota unit per video (commentThreads.list, 100 comments).

    python youtube_comments_backfill.py [--max-units 4500] [--min-comments 20] [--months 18] [--dry-run]

WHY (29 Oct 2026): only about a quarter of the videos have comments; the sentiment, audience-overlap graph and the long-history lag test all read them. The 2-hourly Supabase
job uses the same key (about 2,400 units a day), so a run is capped by --max-units; run it again on the next quota day (resets 12:30 IST). Videos are taken round-robin over
creators (each creator's most-commented unfetched video first) so every creator gains before any creator gets a second helping. Videos with comments switched off are
remembered in models/comments_disabled.json and skipped next time. Stops at the first quota error.
"""
import argparse
import json
import sys
import time
import urllib.error
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from orchestrator import ENV, youtube_api_get

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
DISABLED = ROOT / "models" / "comments_disabled.json"
V = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-units", type=int, default=4500)
    ap.add_argument("--min-comments", type=int, default=20)
    ap.add_argument("--months", type=int, default=18)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    disabled = set(json.loads(DISABLED.read_text())) if DISABLED.exists() else set()
    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(f"""
        select video_id from (
          select v.video_id, row_number() over (partition by v.creator_id order by v.comment_count desc) rk, v.comment_count
            from youtube_videos v
           where v.creator_id in {V} and v.published_at >= now() - make_interval(months => %s) and v.published_at < now() - interval '72 hours'
             and coalesce(v.duration_seconds, 0) > 60 and v.comment_count >= %s
             and not exists (select 1 from youtube_comments c where c.video_id = v.video_id)) t
         order by rk, comment_count desc""", (args.months, args.min_comments))
    todo = [r[0] for r in cur.fetchall() if r[0] not in disabled]
    print(f"{len(todo)} videos waiting; this run takes at most {args.max_units}")
    if args.dry_run:
        return 0
    units = saved = off = bad = 0
    for vid in todo[: args.max_units]:
        try:
            resp = youtube_api_get("commentThreads", videoId=vid, part="snippet", maxResults=100, order="relevance")
            units += 1
            bad = 0
        except urllib.error.HTTPError as e:
            body = getattr(e, "body_text", "")
            if (e.code == 403 and "commentsDisabled" in body) or e.code == 404:   # comments off, or video deleted/private
                disabled.add(vid)
                off += 1
                units += 1
                continue
            if e.code in (400, 500, 502, 503, 504) and "quota" not in body.lower():   # processing error on this one video: skip, stop only if it keeps happening
                bad += 1
                print(f"  skipped {vid}: HTTP {e.code}", flush=True)
                if bad >= 10:
                    print("stopping: 10 failures in a row")
                    break
                time.sleep(2)
                continue
            print(f"stopping at {units} units: HTTP {e.code} {body[:120]}")
            break
        except RuntimeError as e:
            print("stopping:", e)
            break
        except (TimeoutError, urllib.error.URLError, OSError) as e:   # network hiccup: skip this video, it is picked up on the next run
            print(f"  skipped {vid}: {type(e).__name__}", flush=True)
            time.sleep(2)
            continue
        rows = [(item["id"], vid, c.get("authorDisplayName"), c.get("textDisplay"), c.get("publishedAt"), c.get("likeCount"))
                for item in resp.get("items", []) for c in [item["snippet"]["topLevelComment"]["snippet"]]]
        if rows:
            execute_values(cur, "insert into youtube_comments (comment_id, video_id, author_handle, text, published_at, like_count) values %s "
                                "on conflict (comment_id) do update set like_count=excluded.like_count", rows)
            saved += len(rows)
        if units % 50 == 0:
            conn.commit()
            DISABLED.write_text(json.dumps(sorted(disabled)))
            print(f"  {units} units, {saved} comments, {off} switched off", flush=True)
        time.sleep(0.1)
    conn.commit()
    DISABLED.write_text(json.dumps(sorted(disabled)))
    print(f"done: {units} units, {saved} comments saved, {off} videos with comments switched off")
    return 0


if __name__ == "__main__":
    sys.exit(main())
