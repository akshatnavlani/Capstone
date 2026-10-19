"""Scan videos' captions for spoken sponsors, in small batches, saving every result (see migration 20261014020000).

    python spoken_scan.py --limit 150            # scan up to 150 not-yet-scanned videos of brand-promoting creators
    python spoken_scan.py --dry-run              # how many videos are waiting
    python spoken_scan.py --shorts --limit 150   # Shorts (3 min or less) of creators who also have Instagram posts

YouTube refuses caption requests after about 10-20 in a row ('IpBlocked'). So: BATCH videos, GAP_SECONDS apart, then
REST_SECONDS of rest; when blocked, wait BLOCK_WAIT_SECONDS and carry on; give up after MAX_BLOCKS blocks in a row (everything
scanned so far is saved, a re-run resumes). Reads only; no YouTube API quota is used.
"""

import argparse
import json
import logging
import random
import time

from spoken_sponsor import spoken_evidence

BATCH = 8
GAP_SECONDS = 20
REST_SECONDS = 600
BLOCK_WAIT_SECONDS = 1200
MAX_BLOCKS = 3
log = logging.getLogger("spoken_scan")


def scan_one(api, video_id: str, languages=("hi", "en")):
    """(has_captions, language, characters, evidence). Raises when YouTube blocks the request."""
    listing = api.list(video_id)
    try:
        transcript = listing.find_transcript(list(languages))
    except Exception:
        transcript = next(iter(listing), None)
    if transcript is None:
        return False, None, 0, []
    text = " ".join(s.text for s in transcript.fetch())
    return True, transcript.language_code, len(text), spoken_evidence(text)


def main() -> None:
    import psycopg2
    from db_retry import connect_with_retry
    from orchestrator import get_connection
    from youtube_transcript_api import YouTubeTranscriptApi
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--shorts", action="store_true",
                    help="scan Shorts (3 minutes or less) of creators that also have Instagram posts, instead of videos over 4 minutes")
    args = ap.parse_args()
    conn = connect_with_retry(get_connection)
    length_rule = ("(v.duration_seconds <= 180 and exists (select 1 from instagram_posts p where p.creator_id = v.creator_id "
                   "and p.thumbnail_url is not null))" if args.shorts else "v.duration_seconds > 240")
    with conn.cursor() as cur:
        cur.execute(f"""select v.video_id from youtube_videos v join creator_verification cv on cv.creator_id = v.creator_id
                       where v.is_sponsored is not true and cv.sponsor_group = 'A' and v.published_at > now() - interval '150 days'
                         and {length_rule} and not exists (select 1 from spoken_scan s where s.video_id = v.video_id)""")
        todo = [r[0] for r in cur.fetchall()]
    random.Random(9).shuffle(todo)
    todo = todo[:args.limit]
    log.info("%d videos waiting to be scanned (limit %d)", len(todo), args.limit)
    if args.dry_run:
        return
    api, blocks, done, hits = YouTubeTranscriptApi(), 0, 0, 0
    i = 0

    def save(vid, has, lang, n, ev):
        """Save one result. The database closes a connection that sat idle through a long rest, so reconnect and retry once."""
        nonlocal conn
        for attempt in (1, 2):
            try:
                with conn.cursor() as cur:
                    cur.execute("insert into spoken_scan (video_id, has_captions, language, characters, evidence) values (%s,%s,%s,%s,%s::jsonb) on conflict do nothing",
                                (vid, has, lang, n, json.dumps(ev)))
                conn.commit()
                return
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                if attempt == 2:
                    raise
                log.warning("database connection was closed; reconnecting")
                conn = connect_with_retry(get_connection)

    while i < len(todo) and blocks < MAX_BLOCKS:
        batch = todo[i:i + BATCH]
        for vid in batch:
            try:
                has, lang, n, ev = scan_one(api, vid)
                blocks = 0
            except Exception as e:
                if "Block" in type(e).__name__:
                    blocks += 1
                    log.warning("blocked (%d in a row); waiting %d s", blocks, BLOCK_WAIT_SECONDS)
                    time.sleep(BLOCK_WAIT_SECONDS)
                    break                      # same batch starts again after the wait
                has, lang, n, ev = False, None, 0, []   # no captions for this video, or another harmless error
            save(vid, has, lang, n, ev)
            done += 1; hits += bool(ev); i += 1
            if ev:
                log.info("HIT %s %s", vid, ev)
            time.sleep(GAP_SECONDS)
        else:
            log.info("%d scanned, %d with a spoken sponsor; resting %d s", done, hits, REST_SECONDS)
            time.sleep(REST_SECONDS)
    log.info("finished: %d scanned, %d with a spoken sponsor%s", done, hits, "; stopped after repeated blocks" if blocks >= MAX_BLOCKS else "")


if __name__ == "__main__":
    main()
