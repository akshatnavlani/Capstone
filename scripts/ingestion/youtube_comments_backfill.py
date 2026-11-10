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
    ap.add_argument("--video-ids-file", help="fetch these videos (one id per line) instead of the core-150 selection; e.g. the "
                                             "videos around collaboration tags for the audience-flow test (7 Nov 2026)")
    ap.add_argument("--pages", type=int, default=1, help="pages of 100 comments per video (9 Nov 2026: the audience-flow replication takes up "
                                                         "to 3); with --video-ids-file, videos whose first page was full are topped up")
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
    if args.video_ids_file:
        wanted = [l.strip() for l in open(args.video_ids_file, encoding="utf-8") if l.strip()]
        cur.execute("select distinct video_id from youtube_comments where video_id = any(%s)", (wanted,))
        have = {r[0] for r in cur.fetchall()}
        todo = [v for v in dict.fromkeys(wanted) if v not in have and v not in disabled]
        if args.pages > 1:   # also top up videos whose single stored page was full (90-100 threads) and that have more comments
            cur.execute("""select v.video_id from youtube_videos v where v.video_id = any(%s) and coalesce(v.comment_count, 0) > 100
                           and (select count(*) from youtube_comments c where c.video_id = v.video_id) between 90 and 100""", (wanted,))
            todo += [r[0] for r in cur.fetchall() if r[0] not in disabled]
        # 10 Nov 2026: most never-fetched list videos show 0 comments, 1 unit each for nothing; busiest first, 0-comment videos skipped
        cur.execute("select video_id, coalesce(comment_count, -1) from youtube_videos where video_id = any(%s)", (todo,))
        cc = dict(cur.fetchall())
        todo = sorted((v for v in todo if cc.get(v, -1) != 0), key=lambda v: -cc.get(v, -1))
    print(f"{len(todo)} videos waiting; this run takes at most {args.max_units}")
    if args.dry_run:
        return 0
    units = saved = off = bad = last_save = 0
    for vid in todo:
        if units >= args.max_units:
            break
        try:
            resp = youtube_api_get("commentThreads", videoId=vid, part="snippet", maxResults=100, order="relevance")
            units += 1
            items, tok = resp.get("items", []), resp.get("nextPageToken")
            for _ in range(args.pages - 1):
                if not tok:
                    break
                more = youtube_api_get("commentThreads", videoId=vid, part="snippet", maxResults=100, order="relevance", pageToken=tok)
                units += 1
                items, tok = items + more.get("items", []), more.get("nextPageToken")
            resp = {"items": items}
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
            for attempt in range(12):   # 8 Nov: Azure / Wi-Fi drops the connection; reconnect and retry (uncommitted rows since the last save are re-fetched next run)
                try:
                    execute_values(cur, "insert into youtube_comments (comment_id, video_id, author_handle, text, published_at, like_count) values %s "
                                        "on conflict (comment_id) do update set like_count=excluded.like_count", rows)
                    break
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    if attempt == 11:
                        raise
                    time.sleep(min(60, 5 * (attempt + 1)))
                    try:
                        conn = psycopg2.connect(ENV["DATABASE_URL"], connect_timeout=20)
                        cur = conn.cursor()
                    except psycopg2.OperationalError:
                        pass
            saved += len(rows)
        if units - last_save >= 50:   # 9 Nov: >= rather than % 50, since a video can now cost 2-3 units
            last_save = units
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
