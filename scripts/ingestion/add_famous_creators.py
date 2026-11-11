"""Add well-known creators in the niches our data is thin on (meditation, perfume, gaming, smartphones, makeup and skincare), with their YouTube history. 3 Nov 2026.

    python add_famous_creators.py --dry-run          # look every handle up (1 quota unit each), write nothing
    python add_famous_creators.py                   # the real run (about 25 quota units per creator)

WHY. Review 2 feedback: the data was mostly fitness, and a brief for perfume, gaming or Bangalore meditation found nobody. Every handle below was checked on 3 Nov 2026
against the YouTube API (the channel exists, has the expected name and a real subscriber count); look-alike handles with a few hundred subscribers were left out.

WHAT IT DOES (idempotent): per handle, look the channel up, skip it if we already hold that channel_id, upsert the creator and its youtube_channels row, then add up to --max-videos videos
back to --days days (no comments, brand_id NULL, same as add_collaborator_creators.py). No brand accounts, no Instagram guessing (standing rules).
"""
import argparse
from datetime import datetime, timedelta, timezone

from orchestrator import get_connection, get_or_create_creator, log, upsert_youtube_video, youtube_api_get
from youtube_backfill_history import older_upload_ids

# YouTube handle -> category (allowed: athlete, team, league, fitness_influencer, lifestyle_influencer, other)
SHORTLIST = {
    # 8 Nov 2026: the guide asked for Baba Ramdev (held) and other famous Indian yoga/fitness names, plus Bangalore yoga and meditation groups.
    # Found with search.list and checked: official channel, Indian, real subscriber count (models/famous_search_8nov.json); fan pages left out.
    "theshilpashettykundra": "fitness_influencer", "rujutadiwekarofficial": "fitness_influencer", "yasminbodyimage": "fitness_influencer",
    "anshuka-yoga": "fitness_influencer", "indiarunswithmilind": "fitness_influencer", "bharatthakurartisticyoga": "fitness_influencer",
    "aksharyoga": "lifestyle_influencer", "srisrischoolofyoga.": "lifestyle_influencer", "bodhischoolofyoga": "lifestyle_influencer",
    "yogabharatibangalore": "lifestyle_influencer", "sanatanyogastudiobangalore8869": "lifestyle_influencer",
    "pyramidvalleyinternational": "lifestyle_influencer", "mahabodhisocietybengaluru": "lifestyle_influencer",
    "meditationstudycirclebangalore": "lifestyle_influencer", "heartfulnessmeditationkannada": "lifestyle_influencer",
    # meditation, yoga and spiritual wellness
    "sadhguru": "lifestyle_influencer", "ishafoundation": "lifestyle_influencer", "gurudev": "lifestyle_influencer", "artofliving-official": "lifestyle_influencer",
    "meditationsbygurudev": "lifestyle_influencer", "bkshivani": "lifestyle_influencer", "gaurgopaldas": "lifestyle_influencer", "heartfulness": "lifestyle_influencer",
    "shreansdaga": "lifestyle_influencer", "vipassanameditation": "lifestyle_influencer",
    # perfume and fragrance
    "perfumegyaan": "lifestyle_influencer", "perfumeguru": "lifestyle_influencer", "fragrantix": "lifestyle_influencer", "thakurrr.sniffstories": "lifestyle_influencer",
    "scentimentalforever": "lifestyle_influencer", "theperfumereviewr": "lifestyle_influencer",
    # gaming (Triggered Insaan, MortaL and CarryMinati are already held)
    "TechnoGamerzOfficial": "lifestyle_influencer", "DynamoGaming": "lifestyle_influencer", "Mythpat": "lifestyle_influencer", "LokeshGamer": "lifestyle_influencer",
    "TotalGaming093": "lifestyle_influencer",
    # smartphones and gadgets (Technical Guruji is already held)
    "TrakinTech": "lifestyle_influencer", "TechBurner": "lifestyle_influencer", "GeekyRanjit": "lifestyle_influencer", "Techwiser": "lifestyle_influencer",
    "GadgetsToUse": "lifestyle_influencer",
    # makeup, beauty and skincare
    "makeupbyparulgarg": "lifestyle_influencer", "justkaushal": "lifestyle_influencer", "corallista": "lifestyle_influencer", "draanchalmd": "other",
    "vanitarattan": "other", "debasreebanerjee": "lifestyle_influencer", "pkmakeupstudio": "lifestyle_influencer", "skindiaries": "lifestyle_influencer",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=1460)
    ap.add_argument("--max-videos", type=int, default=600)
    ap.add_argument("--quota-budget", type=int, default=1500)
    ap.add_argument("--only", nargs="+", help="only these handles from the shortlist")
    args = ap.parse_args()
    shortlist = {h: c for h, c in SHORTLIST.items() if not args.only or h in args.only}
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("select channel_id from youtube_channels")
        held = {r[0] for r in cur.fetchall()}

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    budget = [args.quota_budget]
    added_creators = added_videos = 0
    for handle, category in shortlist.items():
        if budget[0] <= 0:
            log.warning("quota budget used up; stopping before @%s", handle)
            break
        resp = youtube_api_get("channels", forHandle="@" + handle, part="snippet,statistics,contentDetails")
        budget[0] -= 1
        items = resp.get("items", [])
        if not items:
            log.warning("@%s: no YouTube channel under this handle; skipped", handle)
            continue
        ch = items[0]
        channel_id, snip, stats = ch["id"], ch["snippet"], ch["statistics"]
        if channel_id in held:
            log.info("@%s (%s): already held; skipped", handle, snip.get("title"))
            continue
        if args.dry_run:
            log.info("[DRY RUN] would add @%s -> %s (%s), %s subscribers, %s videos", handle, snip.get("title"), category, stats.get("subscriberCount"), stats.get("videoCount"))
            continue
        creator = get_or_create_creator(conn, snip.get("title") or handle, category, youtube_handle=handle)
        with conn.cursor() as cur:
            cur.execute("""insert into youtube_channels (channel_id, creator_id, channel_handle, title, description, subscriber_count, view_count, video_count, country)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (channel_id) do update set subscriber_count=excluded.subscriber_count, fetched_at=now(), updated_at=now()""",
                        (channel_id, creator.creator_id, handle, snip.get("title"), snip.get("description"), stats.get("subscriberCount"), stats.get("viewCount"),
                         stats.get("videoCount"), snip.get("country")))
            cur.execute("select video_id from youtube_videos where channel_id = %s", (channel_id,))
            known = {r[0] for r in cur.fetchall()}
        conn.commit()
        ids = older_upload_ids(channel_id, cutoff, known, budget, args.max_videos)
        n = 0
        for start in range(0, len(ids), 50):
            if budget[0] <= 0:
                break
            vr = youtube_api_get("videos", id=",".join(ids[start:start + 50]), part="snippet,statistics,contentDetails")
            budget[0] -= 1
            for v in vr.get("items", []):
                with conn.cursor() as cur:
                    upsert_youtube_video(cur, v, channel_id, creator.creator_id, None)
                n += 1
            conn.commit()
        added_creators += 1
        added_videos += n
        log.info("@%s -> %s (%s): %d videos added, %d quota units left", handle, snip.get("title"), category, n, budget[0])

    log.info("done: %d creators, %d videos added, %d quota units used", added_creators, added_videos, args.quota_budget - budget[0])


if __name__ == "__main__":
    main()
