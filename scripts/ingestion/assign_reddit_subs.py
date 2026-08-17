"""Assign topic subreddits to creators that have a REAL name but no Reddit configuration.

Reddit's topic-sub mode searches a subreddit for `creators.name` and verifies each hit
actually mentions them. That makes it useless for a creator whose name is still their
Instagram handle -- proven directly: r/Cricket search for "rohitsharma45" returns 0 results,
"Rohit Sharma" returns 10. So this only assigns subs to creators whose name looks like a
real, searchable name, and skips the rest rather than padding the "attempted" count with
queries that cannot match by construction.

Sub choice is by category, drawn ONLY from subreddits already in use elsewhere in this
project -- no invented communities. Sport is not in the schema, so cricket-vs-football is
inferred from existing graph signal (which teams/leagues a creator is connected to) and
falls back to the generic India subs when there is no signal.
"""

import argparse
import logging
import re

import psycopg2

from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reddit-subs")

# Only subs already proven in this repo's existing creator config.
CRICKET = ["Cricket", "IndianCricket"]
IPL = ["ipl", "Cricket"]
FOOTBALL = ["IndianFootball", "soccer"]
GENERIC = ["india", "IndianYoutubers"]
FITNESS = ["indianfitness", "india"]

CRICKET_HINTS = re.compile(r"cricket|ipl|kkr|rider|royals|titans|super\s?giants|"
                            r"mumbai indians|chennai|sunrisers|capitals|punjab kings", re.I)
FOOTBALL_HINTS = re.compile(r"\bfc\b|football|bengaluru fc|kerala blasters|mumbai city|"
                             r"chennaiyin|goa|isl|super league", re.I)

# US/other-sport entities. Caught 2026-08-18 in the dry run BEFORE applying: the
# category-only fallback was routing Philadelphia 76ers and Matthew Dellavedova to
# r/ipl+r/Cricket and Ohio State Football to r/IndianFootball. Those searches cannot match
# by construction, so they would burn requests AND inflate the "attempted" count with
# non-attempts. r/nba is already in use in this repo (LeBron James), so it is proven.
NBA_HINTS = re.compile(r"76ers|sixers|lakers|nba|delly|dellavedova|kevin love|"
                        r"tristan thompson|channing frye|bronny|maxey", re.I)
# No proven in-repo sub exists for US college sports or powerboat racing. Rather than invent
# a community, these are SKIPPED and reported -- an honest "no confident sub" beats a
# guaranteed-empty search.
NO_CONFIDENT_SUB = re.compile(r"ohio state|buckeyes|e1 series|college", re.I)


def looks_like_real_name(name: str, handle: str | None) -> bool:
    """A searchable human/organisation name, not a handle."""
    if not name:
        return False
    if handle and name.strip().lower() == handle.strip().lower():
        return False
    # a space means Reddit can actually match it as words
    return " " in name.strip()


def subs_for(name: str, category: str, connected_names: str) -> list[str]:
    """Topic subs for this creator, or [] when no sub can be chosen with confidence."""
    blob = f"{name} {connected_names}"
    # Order matters: the non-Indian checks must precede the category fallbacks, which
    # otherwise route every `team` to an IPL/ISL sub regardless of what sport it plays.
    if NO_CONFIDENT_SUB.search(blob):
        return []
    if NBA_HINTS.search(blob):
        return ["nba"]
    if category == "team":
        return IPL if CRICKET_HINTS.search(blob) else (FOOTBALL if FOOTBALL_HINTS.search(blob) else IPL)
    if category == "league":
        return FOOTBALL if FOOTBALL_HINTS.search(blob) else CRICKET
    if category == "athlete":
        if FOOTBALL_HINTS.search(blob):
            return FOOTBALL
        return CRICKET if CRICKET_HINTS.search(blob) else ["india", "Cricket"]
    if category == "fitness_influencer":
        return FITNESS
    return GENERIC


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("""
        select c.creator_id, c.name, c.category, c.instagram_handle,
               coalesce((select string_agg(distinct t.name, ' ')
                         from creator_related_accounts x
                         join creators t on lower(t.instagram_handle)=lower(x.handle)
                         where x.creator_id = c.creator_id), '')
        from creators c
        where coalesce(array_length(c.reddit_topic_subs,1),0) = 0
          and coalesce(array_length(c.reddit_handles,1),0) = 0
        order by c.name
    """)
    rows = cur.fetchall()

    eligible = [(cid, n, cat, ig, conn_names) for cid, n, cat, ig, conn_names in rows
                if looks_like_real_name(n, ig)]
    skipped = len(rows) - len(eligible)
    log.info("unconfigured creators=%d  eligible (real name)=%d  skipped (handle-as-name)=%d",
              len(rows), len(eligible), skipped)
    if args.limit:
        eligible = eligible[: args.limit]

    assigned = no_sub = 0
    for cid, name, cat, ig, conn_names in eligible:
        subs = subs_for(name, cat or "other", conn_names)
        if not subs:
            no_sub += 1
            log.info("   %-34s [%s] -> SKIP, no confident sub", name[:33], cat)
            continue
        assigned += 1
        log.info("   %-34s [%s] -> %s", name[:33], cat, subs)
        if not args.dry_run:
            cur.execute("update creators set reddit_topic_subs=%s, updated_at=now() "
                         "where creator_id=%s", (subs, cid))
    if not args.dry_run:
        conn.commit()
    log.info("DONE assigned=%d skipped_no_confident_sub=%d%s",
              assigned, no_sub, "  [DRY RUN]" if args.dry_run else "")
    conn.close()


if __name__ == "__main__":
    main()
