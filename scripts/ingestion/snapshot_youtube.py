"""Record how YouTube videos grow, and pick up new uploads quickly.

    python snapshot_youtube.py                    # discover new uploads + snapshot young videos
    python snapshot_youtube.py --no-discover      # snapshot only (no per-channel upload check)
    python snapshot_youtube.py --max-age-days 14  # follow videos for 14 days instead of 7
    python snapshot_youtube.py --dry-run          # report what it would poll; calls nothing, writes nothing

Run it every 1 to 2 hours (Task Scheduler). Each run appends one `post_snapshots` row per young
video with the counts at that moment (the age of the video is fetched_at minus its published_at),
so a video's first 24 hours become a curve, not one number.

QUOTA (the YouTube Data API gives 10,000 units a day per key):
  discovery   1 unit per channel   (latest uploads of each channel)
  snapshots   1 unit per 50 videos
For 150 channels that is about 150 units plus a few per run, so 12 runs a day is about 2,000 units.
Pass --no-discover to cut the per-run cost to a handful of units; new uploads are then only found by
the daily collector (orchestrator.py), and the first hours of those videos are missed.

Needs YOUTUBE_API_KEY and DATABASE_URL in .env. Importing orchestrator also expects `opencli`
on PATH, as everywhere else in this folder.
"""

import argparse
import logging

from orchestrator import (RateLimiter, brand_id_for_text, get_connection, log,
                          upsert_youtube_video, youtube_api_get)

BATCH = 50  # videos.list accepts at most 50 ids per call
DISCOVER_LATEST = 10  # uploads checked per channel per run


def uploads_playlist_id(channel_id: str) -> str | None:
    """A channel's uploads playlist id is its channel id with the leading 'UC' swapped for 'UU'."""
    return "UU" + channel_id[2:] if channel_id.startswith("UC") and len(channel_id) > 2 else None


def chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-age-days", type=int, default=7, help="follow videos published this recently")
    ap.add_argument("--no-discover", action="store_true", help="skip the per-channel check for new uploads")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("select channel_id, creator_id from youtube_channels")
        channels = cur.fetchall()
        cur.execute("select video_id, channel_id, creator_id from youtube_videos "
                    "where published_at >= now() - make_interval(days => %s)", (args.max_age_days,))
        young = {vid: (ch, cr) for vid, ch, cr in cur.fetchall()}
        cur.execute("select video_id from youtube_videos")
        known = {r[0] for r in cur.fetchall()}
    owner = {ch: cr for ch, cr in channels}
    log.info("%d channels, %d videos younger than %d days, %d videos known",
             len(channels), len(young), args.max_age_days, len(known))

    if args.dry_run:
        discover_cost = 0 if args.no_discover else len(channels)
        snapshot_cost = -(-len(young) // BATCH)
        log.info("[DRY RUN] would use about %d quota units (%d discovery + %d snapshots); nothing was called",
                 discover_cost + snapshot_cost, discover_cost, snapshot_cost)
        return

    # The YouTube API needs no 3-second gap (that default is for Instagram); 0.25s keeps a run to about a minute,
    # so an hourly GitHub job stays inside the free 2,000 minutes a month.
    limiter = RateLimiter(0.25)
    new_ids: dict[str, str] = {}  # video_id -> channel_id for uploads we have never stored
    if not args.no_discover:
        for channel_id, _creator in channels:
            playlist = uploads_playlist_id(channel_id)
            if not playlist:
                continue
            limiter.wait()
            try:
                resp = youtube_api_get("playlistItems", playlistId=playlist, part="contentDetails",
                                       maxResults=DISCOVER_LATEST)
            except Exception as e:  # one broken channel must not stop the rest
                log.warning("discovery failed for %s: %s", channel_id, e)
                continue
            for item in resp.get("items", []):
                vid = item["contentDetails"]["videoId"]
                if vid not in known:
                    new_ids[vid] = channel_id
        log.info("found %d new uploads", len(new_ids))

    targets = {vid: ch for vid, (ch, _cr) in young.items()}
    targets.update(new_ids)
    written = 0
    for batch in chunks(sorted(targets), BATCH):
        limiter.wait()
        items = youtube_api_get("videos", id=",".join(batch), part="snippet,statistics,contentDetails").get("items", [])
        with conn.cursor() as cur:
            for v in items:
                channel_id = targets[v["id"]]
                vs = v["snippet"]
                brand_id = brand_id_for_text(cur, f"{vs.get('title', '')} {vs.get('description', '')}")
                upsert_youtube_video(cur, v, channel_id, owner.get(channel_id), brand_id)
                written += 1
        conn.commit()
    log.info("snapshotted %d videos (%d of them new)", written, len(new_ids))
    conn.close()


if __name__ == "__main__":
    main()
