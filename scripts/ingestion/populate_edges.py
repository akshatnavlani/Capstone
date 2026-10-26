"""Populate creator_related_accounts — the collaboration-edge source (P0.2).

That table had 0 rows and had never been written to by anything, for the whole project.
Six rounds of "0 edges" blocking Track B was a POPULATION gap, not a discovery problem.

Three constraints, each verified against the live DB / Track C's consuming code rather
than taken on trust (2026-08-11):
  1. `relation_type` must be EXACTLY the literal "frequent_collaborator". Track C's
     build_collaboration_edges() filters on that string and silently ignores anything
     else -- no error, just no edge. Hardcoded below as a constant; do not parameterise.
  2. BOTH endpoints must already exist as `creators` rows. The resolver matches the
     `handle` text against other creators' own handles and silently skips whatever it
     can't resolve. So this script only ever writes an edge when the mentioned handle is
     ALREADY a known creator -- writing speculative rows would inflate row counts while
     producing zero resolved edges, which is the exact failure mode the project's
     "row counts != resolved counts" rule warns about.
  3. platform CHECK is (youtube|instagram|reddit); UNIQUE(creator_id, platform, handle)
     makes re-runs idempotent.

Source of relationships: @mentions in post captions. A team account tagging a player
(or a creator tagging a collaborator) is a real, observable collaboration signal, and
captions are now trustworthy after the P0.1 backfill.

Run:  python populate_edges.py [--scrape-teams] [--dry-run]
  --scrape-teams also pulls recent posts for creators with category='team' first, since
  a freshly-promoted team account has no content yet and therefore no mentions to mine.
"""

import argparse
import logging
import os
import re
import shutil
import subprocess

import psycopg2
import yaml

from instagram_comment_extract import parse_caption

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("edges")

# Track C filters on this exact literal. Changing it silently yields zero edges.
RELATION_TYPE = "frequent_collaborator"

_OPENCLI = shutil.which("opencli")
_MENTION = re.compile(r"\[@([A-Za-z0-9_.]+)\]|@([A-Za-z0-9_.]{2,30})")


def load_env():
    env = dict(os.environ)
    with open(os.path.join(os.path.dirname(__file__), "..", "..", ".env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k, v)
    return env


ENV = load_env()


def run_opencli(*args, timeout=90):
    e = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        e["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    r = subprocess.run([_OPENCLI, *args], capture_output=True, text=True,
                        timeout=timeout, env=e, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"opencli {' '.join(args)}: {r.stdout}{r.stderr}")
    return yaml.safe_load(r.stdout)


def scrape_team_captions(conn, limit_posts=6):
    """Pull recent post captions for team-category creators so their tags can be mined.

    Uses the same open->find->open->extract path as the orchestrator, and the same
    anchored parse_caption. Verifies the extracted page URL matches the requested post
    (omitting that check is what corrupted the caption backfill earlier today).
    """
    with conn.cursor() as cur:
        cur.execute(
            "select creator_id, instagram_handle from creators "
            "where category='team' and instagram_handle is not null order by name"
        )
        teams = cur.fetchall()
    log.info("scraping %d team accounts for tagged collaborators", len(teams))

    found = []
    for creator_id, handle in teams:
        session = f"edge_{handle[:12]}"
        try:
            run_opencli("browser", session, "open", f"https://www.instagram.com/{handle}/")
            run_opencli("browser", session, "wait", "time", "2")
            res = run_opencli("browser", session, "find", "--css",
                               'a[href*="/reel/"], a[href*="/p/"]', "--limit", str(limit_posts))
            paths = list(dict.fromkeys(e["attrs"]["href"] for e in res.get("entries", [])))[:limit_posts]
        except RuntimeError as e:
            log.info("  %s: grid failed: %s", handle, str(e)[:70])
            continue

        for path in paths:
            post_id = path.strip("/").split("/")[-1]
            try:
                run_opencli("browser", session, "open", f"https://www.instagram.com{path}")
                run_opencli("browser", session, "wait", "time", "2")
                ex = run_opencli("browser", session, "extract")
                if not isinstance(ex, dict) or post_id not in (ex.get("url") or ""):
                    continue
                cap = parse_caption(ex.get("content") or "", handle)
            except RuntimeError:
                continue
            if cap:
                found.append((creator_id, handle, post_id, cap))
        try:
            run_opencli("browser", session, "close")
        except RuntimeError:
            pass
        log.info("  %s: %d captions", handle, sum(1 for f in found if f[1] == handle))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scrape-teams", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("select lower(instagram_handle), creator_id from creators "
                     "where instagram_handle is not null")
        known = {h: cid for h, cid in cur.fetchall()}
    log.info("known creators with instagram handles: %d", len(known))

    # (owner_creator_id, owner_handle, mentioned_handle)
    candidates: list[tuple[str, str, str]] = []

    # Source 1: captions already in the DB.
    with conn.cursor() as cur:
        cur.execute("select username, caption, creator_id from instagram_posts "
                     "where caption is not null and creator_id is not null")
        for uname, cap, cid in cur.fetchall():
            for m in _MENTION.finditer(cap):
                h = (m.group(1) or m.group(2) or "").lower().rstrip(".")
                if h and h in known and h != (uname or "").lower():
                    candidates.append((cid, uname, h))

    # Source 2: freshly scraped team posts (teams have no stored content yet).
    if args.scrape_teams:
        for creator_id, handle, _post_id, cap in scrape_team_captions(conn):
            for m in _MENTION.finditer(cap):
                h = (m.group(1) or m.group(2) or "").lower().rstrip(".")
                if h and h in known and h != handle.lower():
                    candidates.append((creator_id, handle, h))

    # Dedup: UNIQUE(creator_id, platform, handle) means one row per pair regardless of
    # how many posts evidenced it.
    unique = {(cid, h) for cid, _u, h in candidates}
    log.info("candidate mention-pairs=%d unique resolvable edges=%d", len(candidates), len(unique))
    for cid, h in sorted(unique, key=lambda x: x[1]):
        owner = next((u for c, u, hh in candidates if c == cid and hh == h), "?")
        log.info("   %s -> %s", owner, h)

    if args.dry_run:
        conn.close()
        return

    written = 0
    with conn.cursor() as cur:
        for cid, h in unique:
            cur.execute(
                """
                insert into creator_related_accounts (creator_id, platform, handle, relation_type)
                values (%s, 'instagram', %s, %s)
                on conflict (creator_id, platform, handle) do nothing
                """,
                (cid, h, RELATION_TYPE),
            )
            written += cur.rowcount
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("select count(*) from creator_related_accounts")
        total = cur.fetchone()[0]
    conn.close()
    log.info("DONE inserted=%d total_rows_in_table=%d", written, total)


if __name__ == "__main__":
    main()
