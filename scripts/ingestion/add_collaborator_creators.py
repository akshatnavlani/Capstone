"""Add real creators that OUR sponsoring creators mention (collaborators we do not hold yet), their YouTube history, and the links that make them neighbours. 31 Oct 2026.

    python add_collaborator_creators.py --dry-run          # plan only
    python add_collaborator_creators.py                   # the real run (about 500 YouTube quota units)

WHY. Spillover is measured on creators who have a sponsored collaborator. Only 19 observations (8 creators) qualify, because few real collaborators sit inside our creator set and 41 of
the neighbours we do hold have no posts collected. Mining @mentions in our 121 sponsoring creators' titles, descriptions and captions (models/collaborator_candidates_31oct.json) found
real creators mentioned by 2-5 of them. A mention is weaker evidence than a co-author post; it is the same evidence populate_edges.py already uses (mentions in captions).

WHAT IT DOES (all idempotent):
  1. For each shortlisted handle: look the channel up by the SAME handle (1 quota unit), skip it if there is none, upsert the creator (category set by hand below) and its youtube_channels
     row, then add up to --max-videos videos back to --days days (no comments, no brand guess: brand_id stays NULL, as in youtube_backfill_history.py).
  2. Write one creator_related_accounts row per (sponsoring creator who mentioned the handle -> the new creator), platform 'youtube', relation 'frequent_collaborator'.
  3. ALIAS LINKS: three accounts we already hold under another handle (Ranveer Allahbadia, Elvish Yadav, Karan Aujla): the mentions of their other handle get a link row using the handle we hold.
No brand accounts are added (standing rule). No Instagram handle is guessed: a wrong handle would attach a stranger's posts to a real creator.
"""
import argparse
import json
import re
import time

import psycopg2
from datetime import datetime, timedelta, timezone

from orchestrator import get_connection, get_or_create_creator, log, upsert_youtube_video, youtube_api_get
from youtube_backfill_history import older_upload_ids

# handle on YouTube/Instagram as mentioned -> category (allowed: athlete, team, league, fitness_influencer, lifestyle_influencer, other)
SHORTLIST = {
    "mindwithmuscle": "fitness_influencer", "jeetselalaesthetics": "fitness_influencer", "nawingoldenboy": "fitness_influencer", "taarunsgill": "fitness_influencer",
    "bhuwanchauhan": "fitness_influencer", "unstopablesid": "fitness_influencer", "siddhantraisikand": "fitness_influencer", "urbangabru_official": "fitness_influencer",
    "tigerfitnessclub5656": "fitness_influencer", "foodpharmer": "other", "krishashok": "other", "drniranjanhiranandani": "other", "rashmishetty": "other", "drpal": "other",
    # second batch (31 Oct 2026, evening): the people left in the mention list once brands, politicians and global celebrities were dropped
    "ronniecoleman8": "athlete", "sam_sulek": "fitness_influencer", "rajatdalal7821": "fitness_influencer", "drimranpatelofficial": "other", "askdrjain": "other",
}
# mentioned handle -> Instagram handle of the creator we already hold
ALIASES = {"ranveerallahbadia": "beerbiceps", "thesocialfactory": "elvish_yadav", "karanaujlaofficial": "karanaujla"}
MENTION = re.compile(r"@([a-z0-9_.]{4,30})", re.I)


def mentioners(cur, wanted: set[str]) -> dict[str, dict[str, int]]:
    """handle -> {sponsoring creator_id: number of posts that mention it}."""
    cur.execute("""select creator_id::text from youtube_videos where is_sponsored and creator_id is not null
                   union select creator_id::text from instagram_posts where (is_sponsored or has_paid_partnership_label) and creator_id is not null""")
    sponsoring = [r[0] for r in cur.fetchall()]
    found: dict[str, dict[str, int]] = {h: {} for h in wanted}
    for cid in sponsoring:
        texts = []
        cur.execute("select coalesce(title,'') || ' ' || coalesce(description,'') from youtube_videos where creator_id = %s", (cid,))
        texts += [r[0] for r in cur.fetchall()]
        cur.execute("select caption from instagram_posts where creator_id = %s", (cid,))
        texts += [r[0] for r in cur.fetchall()]
        for t in texts:
            for m in {h.lower().rstrip(".") for h in MENTION.findall(t or "")}:
                if m in wanted:
                    found[m][cid] = found[m].get(cid, 0) + 1
    return found


def add_link(cur, from_creator: str, platform: str, handle: str) -> int:
    cur.execute("""insert into creator_related_accounts (creator_id, platform, handle, relation_type) values (%s, %s, %s, 'frequent_collaborator')
                   on conflict (creator_id, platform, handle) do nothing""", (from_creator, platform, handle))
    return cur.rowcount


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=1460)
    ap.add_argument("--max-videos", type=int, default=600)
    ap.add_argument("--quota-budget", type=int, default=1500)
    ap.add_argument("--only", nargs="+", help="only these handles from the shortlist (a re-run for new entries)")
    ap.add_argument("--shortlist", help="JSON file whose 'shortlist' maps handle -> category, used instead of SHORTLIST "
                                        "(e.g. models/collaborator_shortlist_6nov.json); alias links are then skipped")
    args = ap.parse_args()
    if args.shortlist:
        with open(args.shortlist, encoding="utf-8") as f:
            source = json.load(f)["shortlist"]
        args.only = args.only or list(source)  # --only also switches the alias pass off
    else:
        source = SHORTLIST
    shortlist = {h: c for h, c in source.items() if not args.only or h in args.only}
    conn = get_connection()
    with conn.cursor() as cur:
        who = mentioners(cur, set(shortlist) | (set(ALIASES) if not args.only else set()))
    for h, d in who.items():
        log.info("@%s: mentioned by %d sponsoring creators (%d posts)", h, len(d), sum(d.values()))
    if args.dry_run:
        log.info("[DRY RUN] no database write and no API call")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    budget = [args.quota_budget]
    new_links = added_videos = 0
    def add_one(conn, handle: str, category: str) -> tuple[int, int]:
        """One shortlisted handle: channel, videos, links. Returns (videos added, new link rows)."""
        links = 0
        resp = youtube_api_get("channels", forHandle="@" + handle, part="snippet,statistics,contentDetails")
        budget[0] -= 1
        items = resp.get("items", [])
        if not items:
            log.warning("@%s: no YouTube channel under this handle; skipped", handle)
            return 0, 0
        ch = items[0]
        channel_id, snip, stats = ch["id"], ch["snippet"], ch["statistics"]
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
        with conn.cursor() as cur:
            for sponsoring in who[handle]:
                links += add_link(cur, sponsoring, "youtube", handle)
        conn.commit()
        log.info("@%s -> %s (%s): %d videos added, %d links, %d quota units left", handle, snip.get("title"), category, n, len(who[handle]), budget[0])
        return n, links

    for handle, category in shortlist.items():
        if not who[handle]:
            log.info("@%s: no sponsoring creator mentions it any more; skipped", handle)
            continue
        for attempt in range(3):  # 7 Nov: a dropped Azure connection stopped the run after 77 of 118
            try:
                n, links = add_one(conn, handle, category)
                added_videos += n
                new_links += links
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                log.warning("@%s: database connection lost (%s); reconnecting, attempt %d", handle, str(e).splitlines()[0][:80], attempt + 1)
                time.sleep(10 * (attempt + 1))
                conn = get_connection()

    with conn.cursor() as cur:
        for alias, held_ig in ({} if args.only else ALIASES).items():
            cur.execute("select creator_id from creators where lower(instagram_handle) = %s", (held_ig,))
            row = cur.fetchone()
            if not row:
                log.warning("alias @%s: no creator with Instagram handle %s; skipped", alias, held_ig)
                continue
            for sponsoring in who[alias]:
                if str(sponsoring) != str(row[0]):
                    new_links += add_link(cur, sponsoring, "instagram", held_ig)
    conn.commit()
    log.info("done: %d videos added, %d new link rows, %d quota units used", added_videos, new_links, args.quota_budget - budget[0])


if __name__ == "__main__":
    main()
