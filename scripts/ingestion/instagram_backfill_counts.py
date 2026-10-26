"""One-time fill-in of like/comment counts for OLD Instagram posts that were saved without them (by the first collector).

    python instagram_backfill_counts.py --posts-file posts.json --limit 40
    python instagram_backfill_counts.py --posts-file posts.json --dry-run          # prints the plan, opens nothing

WHY: a sponsorship event only yields a training pair for GAIL when the neighbour has posts WITH engagement counts both before and after
the event. 13 of the 49 unmeasurable pairs (24 Oct 2026) had Instagram posts on both sides whose counts had never been saved. Reading those
posts once fills the counts (an old post's current count is its settled count), so no waiting is needed.

`posts.json` is a list of {"post_id": shortcode, "username": handle}. Each page read appends a `post_snapshots` row, so the read counts against
the same daily page-load budget as instagram_daily.py (DEFAULT_DAILY_CAP page loads per UTC day, counted from those rows). Same safety rules as
snapshot_instagram.py: GAP_SECONDS between loads, stop the whole run at the first sign of a block or after two failures in a row. Reads only.
"""
import argparse
import json
from datetime import datetime, timezone

from audit_post_ownership import _OG_VERIFIED_JS, OWNER, load_seen, save_seen
from instagram_daily import DEFAULT_DAILY_CAP, chrome_connected, done_today
from orchestrator import RateLimiter, get_connection, log, og_approx_counts, parse_og_description, record_post_snapshot, run_opencli
from snapshot_instagram import GAP_SECONDS, MAX_CONSECUTIVE_FAILURES, looks_blocked


def owner_of(og_text: str) -> str | None:
    """The account that really owns the post, from its own og:description ("885 likes, 33 comments - <owner> on May 9, 2026: ...")."""
    m = OWNER.search(og_text or "")
    return m.group(1) if m else None


def same_page(code: str, url: str | None) -> bool:
    """True when the page that was read is the requested post (a read can describe a different page if `open` had not finished)."""
    return bool(url) and code in url


def pending_posts(cur, wanted: list[dict]) -> list[dict]:
    """The wanted posts that still have no like or comment count (so a re-run never repeats a finished read)."""
    ids = [w["post_id"] for w in wanted]
    cur.execute("select post_id from instagram_posts where post_id = any(%s) and (like_count is null or comment_count is null)", (ids,))
    missing = {r[0] for r in cur.fetchall()}
    return [w for w in wanted if w["post_id"] in missing]


DAILY_REVIEW_SQL = """
    select p.post_id, p.username from instagram_posts p
    where p.creator_id in (select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed', 'probable'))
      and (p.like_count is null or p.comment_count is null)
    order by exists (select 1 from creator_sponsorship_events e where e.creator_id = p.creator_id) desc, p.posted_at desc"""


def posts_to_fill(cur, n: int) -> list[dict]:
    """Posts of the verified 150 that still have no counts and were never owner-checked, sponsoring creators first (shared-brand neighbours are sponsors too)."""
    seen = load_seen()
    cur.execute(DAILY_REVIEW_SQL)
    return [{"post_id": pid, "username": user} for pid, user in cur.fetchall() if pid not in seen][:n]


def read_and_fill(conn, todo: list[dict], limit: int) -> tuple[int, int, int]:
    """Open up to `limit` of the posts, verify page and owner, fill in the counts. Returns (page loads, posts that got counts, foreign posts detached).
    Stops the whole run at the first sign of a block or after two failures in a row. Shared by this script and the daily job."""
    limiter, loads, fails, filled, foreign = RateLimiter(GAP_SECONDS), 0, 0, 0, 0
    session = "backfill_counts"
    try:
        for w in todo[:limit]:
            code, handle = w["post_id"], w["username"]
            try:
                limiter.wait(); loads += 1
                run_opencli("browser", session, "open", f"https://www.instagram.com/p/{code}/")
                run_opencli("browser", session, "wait", "time", "3")
                raw = run_opencli("browser", session, "eval", _OG_VERIFIED_JS)
                try:
                    payload = raw if isinstance(raw, dict) else json.loads(raw)
                except (TypeError, ValueError):
                    payload = {}
                text, url = (payload.get("d") or ""), payload.get("u")
                if looks_blocked(text) or looks_blocked(str(raw)[:200]):
                    raise RuntimeError("block suspected: " + str(raw)[:80])
                if not same_page(code, url):
                    raise RuntimeError(f"the page read was not the requested post ({str(url)[:60]})")
                owner = owner_of(text)
                if owner and owner.lower() != (handle or "").lower():
                    # another account's post filed under this creator (the August collection bug): detach it, keep a backup, write no counts
                    with conn.cursor() as cur:
                        cur.execute("""create table if not exists instagram_posts_foreign_backup_20261026 (post_id text primary key, old_creator_id uuid, old_username text,
                                       real_owner text, was_sponsored boolean, like_count int, comment_count int, backed_up_at timestamptz default now())""")
                        cur.execute("""insert into instagram_posts_foreign_backup_20261026 (post_id, old_creator_id, old_username, real_owner, was_sponsored, like_count, comment_count)
                                       select post_id, creator_id, username, %s, is_sponsored, like_count, comment_count from instagram_posts where post_id=%s and creator_id is not null
                                       on conflict do nothing""", (owner, code))
                        cur.execute("update instagram_posts set creator_id = null where post_id=%s", (code,))
                    conn.commit()
                    seen = load_seen()
                    seen[code] = {"stored": handle, "real": owner}
                    save_seen(seen)
                    fails = 0
                    foreign += 1
                    log.warning("%s: FOREIGN, filed under %s but really %s; detached, no counts written", code, handle, owner)
                    continue
                og = parse_og_description(text)
                a_likes, a_comments = og_approx_counts(text)
                likes = og["likes"] if og["likes"] is not None else a_likes
                comments = og["comments"] if og["comments"] is not None else a_comments
                with conn.cursor() as cur:
                    cur.execute("update instagram_posts set like_count=coalesce(%s, like_count), comment_count=coalesce(%s, comment_count), fetched_at=now() "
                                "where post_id=%s returning creator_id", (likes, comments, code))
                    row = cur.fetchone()
                    record_post_snapshot(cur, "instagram", code, row[0] if row else None, None, likes, comments)
                conn.commit()
                if owner:
                    seen = load_seen()
                    seen[code] = {"stored": handle, "real": owner}
                    save_seen(seen)
                fails = 0
                filled += int(likes is not None or comments is not None)
                log.info("%s (%s): %s likes, %s comments", code, handle, likes, comments)
            except RuntimeError as e:
                conn.rollback()
                fails += 1
                log.error("%s: %s", code, str(e)[:200].replace("\n", " "))
                if looks_blocked(str(e)) or fails >= MAX_CONSECUTIVE_FAILURES:
                    log.error("stopping the whole run (block suspected or %d failures in a row)", fails)
                    break
    finally:
        try:
            run_opencli("browser", session, "close", timeout=20)
        except RuntimeError:
            pass
    log.info("done: %d page loads, %d posts got counts, %d foreign posts detached (%s)", loads, filled, foreign, datetime.now(timezone.utc).isoformat(timespec="minutes"))
    return loads, filled, foreign


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--posts-file", required=True)
    ap.add_argument("--limit", type=int, default=40, help="most page loads in this run")
    ap.add_argument("--daily-cap", type=int, default=DEFAULT_DAILY_CAP)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wanted = json.load(open(args.posts_file, encoding="utf-8"))
    conn = get_connection()
    with conn.cursor() as cur:
        todo = pending_posts(cur, wanted)
        used = done_today(cur)
    budget = min(args.limit, args.daily_cap - used)
    log.info("%d posts listed, %d still without counts; %d page loads used today, this run may use %d", len(wanted), len(todo), used, max(budget, 0))
    if args.dry_run or budget <= 0 or not todo:
        log.info("[DRY RUN or nothing to do] no page was opened")
        return
    if not chrome_connected():
        log.error("Chrome is not connected to OpenCLI; not starting")
        return

    read_and_fill(conn, todo, budget)


if __name__ == "__main__":
    main()
