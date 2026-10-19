"""One day's Instagram reading, within a fixed page-load budget (run by the Windows task CapstoneInstagramDaily).

    python instagram_daily.py --dry-run      # prints today's plan, opens nothing (Chrome not needed)
    python instagram_daily.py                # does it

What it does, in this order, and nothing else:
  1. Stops quietly if Chrome with the OpenCLI extension is not connected (writes that to the log).
  2. Works out the page loads left today (cap minus the snapshot rows already written today, UTC day).
  3. REFRESH (about 60% of the budget): creators whose young posts still need a second reading come first, then the creators
     most likely to have new posts (frequent posters not looked at for a while); their newest posts (under 2 days old) are
     read, so each post builds a first-day-and-after growth curve. Same code as snapshot_instagram.py.
  4. NEW CREATORS (the rest): collects the next verified creators that have no Instagram data yet, most sponsored posts first
     (about 15 page loads each; same collector as run_instagram_safe: profile, 12 posts, comments with exact times).
  5. Stops the whole run at the first failure or sign of a block. Never retries, never rotates accounts.
Reads only: no likes, follows or comments. Everything is saved in Supabase; the only local file is a plain log in
%LOCALAPPDATA%\\CapstoneInstagram.
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

LOADS_PER_REFRESH = 3.5     # one profile page plus about 2-3 young posts
LOADS_PER_NEW_CREATOR = 10  # one profile page plus the newest NEW_CREATOR_POSTS posts (comments come with the post pages)
NEW_CREATOR_POSTS = 8       # older posts do not help the lag analysis; fewer posts means more creators per day
DEFAULT_DAILY_CAP = 130     # page loads per UTC day; 100-135 a day was measured safe (no block in about 700 loads over 6 days)
REFRESH_SHARE = 0.6
PAUSE_BETWEEN_NEW_CREATORS = 45
LOCK_HOURS = 3
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", ".")) / "CapstoneInstagram"
log = logging.getLogger("instagram_daily")


def split_budget(budget: int) -> tuple[int, int]:
    """(creators to refresh, new creators to collect) that fit in `budget` page loads."""
    if budget <= 0:
        return 0, 0
    refresh = int(budget * REFRESH_SHARE // LOADS_PER_REFRESH)
    new = int((budget - refresh * LOADS_PER_REFRESH) // LOADS_PER_NEW_CREATOR)
    return refresh, max(new, 0)


def chrome_connected() -> bool:
    """True when `opencli doctor` reports the extension connected."""
    exe = shutil.which("opencli")
    if not exe:
        return False
    try:
        out = subprocess.run([exe, "doctor"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "Extension: connected" in out


def done_today(cur) -> int:
    cur.execute("""select count(*) from post_snapshots where platform='instagram'
                   and fetched_at >= date_trunc('day', now() at time zone 'UTC') at time zone 'UTC'""")
    return cur.fetchone()[0]


def refresh_handles(cur, n: int) -> list[str]:
    """Instagram handles to re-read today, chosen for the lag analysis, which needs posts read EARLY and then again:
    1. creators with a post under 36 hours old that has fewer than 2 readings (time-critical: the second reading must come soon);
    2. then creators most likely to have new posts we have not seen: their posts per day over the last 14 days times the
       days since we last looked, highest first."""
    cur.execute("""
      select username from (
        select p.username, p.fetched_at,
          (select count(*) from instagram_posts ip
            where ip.creator_id = p.creator_id and ip.thumbnail_url is not null and ip.posted_at > now() - interval '36 hours'
              and (select count(*) from post_snapshots s where s.post_id = ip.post_id and s.platform = 'instagram') < 2) as urgent,
          (select count(*) from instagram_posts ip
            where ip.creator_id = p.creator_id and ip.thumbnail_url is not null and ip.posted_at > now() - interval '14 days') / 14.0
            * extract(epoch from now() - p.fetched_at) / 86400.0 as expected_new
        from instagram_profiles p
        where p.creator_id in (select creator_id from instagram_posts where thumbnail_url is not null)) t
      order by (urgent > 0) desc, expected_new desc, fetched_at asc limit %s""", (n,))
    return [r[0] for r in cur.fetchall()]


def new_creators(cur, n: int) -> list[tuple]:
    """(creator_id, handle) of verified creators with no new-style Instagram data, most sponsored events first."""
    cur.execute("""select cv.creator_id, cv.ig_handle,
                     (select count(*) from creator_sponsorship_events e where e.creator_id = cv.creator_id) sponsored
                   from creator_verification cv
                   where cv.link_level in ('confirmed', 'probable') and cv.creator_id is not null and cv.ig_handle is not null
                     and not exists (select 1 from instagram_posts p where p.creator_id = cv.creator_id and p.thumbnail_url is not null)
                   order by (cv.link_level = 'confirmed') desc, sponsored desc limit %s""", (n,))
    return [(r[0], r[1]) for r in cur.fetchall()]


def take_lock() -> bool:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lock = LOG_DIR / "running.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < LOCK_HOURS * 3600:
        return False
    lock.write_text(datetime.now(timezone.utc).isoformat())
    return True


def release_lock() -> None:
    try:
        (LOG_DIR / "running.lock").unlink()
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--daily-cap", type=int, default=DEFAULT_DAILY_CAP, help="max Instagram page loads per UTC day, across all runs")
    args = ap.parse_args()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(LOG_DIR / "daily.log", encoding="utf-8")])
    from db_retry import connect_with_retry
    from orchestrator import get_connection

    conn = connect_with_retry(get_connection)
    run_id = None
    if not args.dry_run:      # every real run leaves a row in Supabase, so a failure is never silent (the log file once was)
        with conn.cursor() as cur:
            cur.execute("insert into instagram_daily_runs default values returning run_id")
            run_id = cur.fetchone()[0]
        conn.commit()
    status, detail = "failed", "did not finish"
    try:
        status, detail = run(args, conn)
        return 1 if status == "failed" else 0
    except Exception:
        status, detail = "failed", traceback.format_exc()[-1500:]
        log.exception("the daily Instagram run crashed")
        return 1
    finally:
        if run_id:
            try:
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute("update instagram_daily_runs set status=%s, detail=%s, finished_at=now() where run_id=%s",
                                (status, (detail or "")[-1500:], run_id))
                conn.commit()
            except Exception:
                log.exception("could not record the run's outcome")


def run(args, conn) -> tuple[str, str]:
    """The day's work. Returns (status, detail) for instagram_daily_runs."""
    from orchestrator import Creator, InstagramWorker, RateLimiter
    with conn.cursor() as cur:
        budget = args.daily_cap - done_today(cur)
        n_refresh, n_new = split_budget(budget)
        handles, fresh = refresh_handles(cur, n_refresh), new_creators(cur, n_new)
    log.info("page loads left today about %d -> refresh %d creators, collect %d new creators", budget, len(handles), len(fresh))
    log.info("refresh: %s", ", ".join(handles) or "none")
    log.info("new: %s", ", ".join(h for _, h in fresh) or "none")
    if args.dry_run:
        log.info("[DRY RUN] nothing opened")
        return "dry_run", ""
    if budget <= 5:
        log.warning("today's budget is used up; not starting")
        return "budget_used", f"{budget} page loads left"
    if not chrome_connected():
        log.warning("Chrome with the OpenCLI extension is not connected; nothing done. Open Chrome signed in to Instagram.")
        return "chrome_not_connected", "opencli doctor did not report the extension connected"
    if not take_lock():
        log.warning("another run started less than %d hours ago; not starting", LOCK_HOURS)
        return "locked", f"another run started less than {LOCK_HOURS} hours ago"
    try:
        if handles:
            done = subprocess.run([sys.executable, str(Path(__file__).with_name("snapshot_instagram.py")), "--handles", *handles,
                                   "--max-age-days", "2", "--daily-cap", str(args.daily_cap)], capture_output=True, text=True)
            tail = "\n".join(((done.stdout or "") + "\n" + (done.stderr or "")).strip().splitlines()[-12:])
            log.info("refresh step output (last lines):\n%s", tail)
            if done.returncode != 0:
                log.error("the refresh step failed (exit %s); stopping the whole run", done.returncode)
                return "failed", f"refresh step exit {done.returncode}:\n{tail}"
        with conn.cursor() as cur:
            budget = args.daily_cap - done_today(cur)
        fresh = fresh[:max(int(budget // LOADS_PER_NEW_CREATOR), 0)]
        worker = InstagramWorker(RateLimiter(8.0), post_cap=NEW_CREATOR_POSTS, recency_days=365)
        for n, (cid, handle) in enumerate(fresh):
            with conn.cursor() as cur:
                cur.execute("""select creator_id, name, category, youtube_handle, instagram_handle, coalesce(reddit_handles,'{}'),
                                      coalesce(reddit_topic_subs,'{}') from creators where creator_id=%s""", (cid,))
                r = cur.fetchone()
            creator = Creator(r[0], r[1], r[2], r[3], r[4], list(r[5]), list(r[6]))
            worker.skipped_stale = 0
            worker.meta_match = {}
            try:
                worker.process_creator(creator, creator.instagram_handle, conn)
            except Exception as e:  # stop at the first failure
                log.error("STOPPING after a failure on %s: %s", handle, str(e)[:300].replace("\n", " "))
                worker._release_on_failure(creator.instagram_handle)
                return "failed", f"stopped after a failure on {handle}: {str(e)[:500]}"
            if n < len(fresh) - 1:
                time.sleep(PAUSE_BETWEEN_NEW_CREATORS)
        log.info("daily Instagram run finished")
        return "ok", f"refreshed {len(handles)} creators, collected {len(fresh)} new"
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
