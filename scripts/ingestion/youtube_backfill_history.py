"""Add OLDER YouTube videos (not yet stored) for the verified 150 creators, so more past sponsored events and neighbour windows exist for GAIL.

    python youtube_backfill_history.py --days 730 --dry-run                  # plan only, no API call
    python youtube_backfill_history.py --days 730 --limit-creators 3         # pilot
    python youtube_backfill_history.py --days 730 --quota-budget 3000        # the real run

WHY a separate script (26 Oct 2026): orchestrator.py's YouTube worker re-fetches comments for each creator's 30 newest videos on every run (about 4,500 quota units
for 150 creators) and guesses a brand from free text, which is how junk 'brands' such as "gmail" and "Delhi" were created. This script only ADDS videos that are not yet stored:
no comments, no brand guess (brand_id stays NULL; the sponsorship detector pass sets brands from the curated list afterwards), no deletes.

Quota: playlistItems.list and videos.list cost 1 unit per call of up to 50 items. It stops at the first API error and when --quota-budget units are used.
Each new video also gets the one snapshot row `upsert_youtube_video` writes (a real reading at that moment; the 2-hourly job only follows videos younger than 7 days).
"""
import argparse
import logging
from datetime import datetime, timedelta, timezone

from orchestrator import get_connection, log, upsert_youtube_video, youtube_api_get

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def older_upload_ids(channel_id: str, cutoff: datetime, known: set[str], budget_left: list[int], max_new: int) -> list[str]:
    """Upload ids newer than `cutoff` that are not in `known`, walking the uploads playlist newest to oldest. `budget_left` is a one-item list so callers share it."""
    playlist = "UU" + channel_id[2:]
    ids, token = [], None
    while len(ids) < max_new and budget_left[0] > 0:
        params = {"playlistId": playlist, "part": "contentDetails", "maxResults": 50}
        if token:
            params["pageToken"] = token
        resp = youtube_api_get("playlistItems", **params)
        budget_left[0] -= 1
        oldest_on_page = None
        for it in resp.get("items", []):
            cd = it.get("contentDetails", {})
            published = cd.get("videoPublishedAt")
            if published:
                when = datetime.fromisoformat(published.replace("Z", "+00:00"))
                oldest_on_page = when if oldest_on_page is None else min(oldest_on_page, when)
                if when < cutoff:
                    continue
            if cd.get("videoId") and cd["videoId"] not in known:
                ids.append(cd["videoId"])
        token = resp.get("nextPageToken")
        if not token or (oldest_on_page is not None and oldest_on_page < cutoff):
            break
    return ids[:max_new]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=730, help="how far back to go (days from today)")
    ap.add_argument("--max-new-per-creator", type=int, default=600)
    ap.add_argument("--limit-creators", type=int, default=0, help="pilot: only the first N channels")
    ap.add_argument("--quota-budget", type=int, default=3000, help="stop after this many API units")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_connection()
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    with conn.cursor() as cur:
        cur.execute("""select c.channel_id, c.creator_id, c.title, c.video_count,
                              (select count(*) from youtube_videos v where v.channel_id = c.channel_id),
                              (select min(published_at) from youtube_videos v where v.channel_id = c.channel_id)
                       from youtube_channels c
                       where c.channel_id like 'UC%%' and c.creator_id in (select creator_id from creator_verification
                             where creator_id is not null and link_level in ('confirmed', 'probable'))
                       order by c.title""")
        channels = cur.fetchall()
    if args.limit_creators:
        channels = channels[: args.limit_creators]
    log.info("%d channels; going back to %s; quota budget %d units", len(channels), cutoff.date(), args.quota_budget)
    if args.dry_run:
        for ch in channels[:10]:
            log.info("  %s: %s stored of %s on the channel, oldest stored %s", (ch[2] or "")[:30], ch[4], ch[3], ch[5] and ch[5].date())
        log.info("[DRY RUN] no API call was made")
        return

    budget = [args.quota_budget]
    added = 0
    for channel_id, creator_id, title, _vc, _stored, _oldest in channels:
        if budget[0] <= 2:
            log.warning("quota budget used up; stopping")
            break
        try:
            with conn.cursor() as cur:
                cur.execute("select video_id from youtube_videos where channel_id = %s", (channel_id,))
                known = {r[0] for r in cur.fetchall()}
            ids = older_upload_ids(channel_id, cutoff, known, budget, args.max_new_per_creator)
            n = 0
            for start in range(0, len(ids), 50):
                if budget[0] <= 0:
                    break
                resp = youtube_api_get("videos", id=",".join(ids[start:start + 50]), part="snippet,statistics,contentDetails")
                budget[0] -= 1
                for v in resp.get("items", []):
                    with conn.cursor() as cur:
                        upsert_youtube_video(cur, v, channel_id, creator_id, None)
                    n += 1
                conn.commit()
            added += n
            log.info("%s: %d older videos added (%d quota units left)", (title or channel_id)[:30], n, budget[0])
        except Exception as e:  # stop at the first API/DB error, as the other collectors do
            conn.rollback()
            log.error("STOPPING at %s: %s", title or channel_id, str(e)[:200])
            break
    log.info("done: %d videos added, %d quota units used", added, args.quota_budget - budget[0])


if __name__ == "__main__":
    main()
