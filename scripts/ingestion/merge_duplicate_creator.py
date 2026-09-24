"""Merge a duplicate `creators` row into its canonical twin, content and all.

WHY THIS EXISTS. A Reddit collection run on 2026-08-20 created a SECOND creators row named
"Athletics" alongside the original from 2026-08-10, and both accumulated real Reddit content --
so one creator's data was split across two identities. The orchestrator's duplicate guard
logged "Possible duplicate creator by name ... NOT auto-merged, flagging for manual review"
and then inserted anyway: the guard warns, it does not block.

Root cause, fixed separately in `get_or_create_creator`: identity matching keyed only on
youtube_handle / instagram_handle, so a creator with NEITHER had no key at all and was
re-created on every single run.

THE COLLISION THAT MAKES THIS NON-TRIVIAL. `reddit_post_creators` is keyed on
(post_id, creator_id). 19 of the duplicate's 40 links point at posts ALREADY linked to the
canonical row, so a blind re-point violates the primary key. Those 19 are redundant -- the
canonical row already asserts that exact link -- so they are dropped rather than merged, and
only the genuinely new links move across. Arithmetic stated up front so the result can be
checked rather than trusted: 40 + 40 - 19 = 61 distinct posts on the survivor.

ORDER MATTERS. The duplicate row is deleted only AFTER every one of the six creator_id tables
is confirmed empty for it. If anything still references it, the row stays and the script says
so -- a dangling creator is recoverable, silently destroyed content is not.

Run: python merge_duplicate_creator.py --keep <uuid> --dup <uuid> [--apply]
     (default is a dry run; --apply is required to write)
"""

import argparse
import logging

import psycopg2

from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("merge")

# Every table carrying a creator_id. Checked before deletion, so a new one appearing in the
# schema shows up as "still referenced" rather than being silently orphaned.
CREATOR_TABLES = ("instagram_posts", "youtube_videos", "reddit_posts", "reddit_post_creators",
                   "instagram_profiles", "creator_related_accounts")

# Tables whose rows must move from dup -> keep.
MOVE = ("reddit_post_creators", "reddit_posts", "instagram_posts", "youtube_videos")


def counts(cur, cid):
    out = {}
    for t in CREATOR_TABLES:
        try:
            cur.execute(f"select count(*) from {t} where creator_id = %s", (cid,))
            out[t] = cur.fetchone()[0]
        except psycopg2.Error:
            cur.connection.rollback()
            out[t] = None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", required=True, help="canonical creator_id (survives)")
    ap.add_argument("--dup", required=True, help="duplicate creator_id (deleted)")
    ap.add_argument("--apply", action="store_true", help="actually write; default is a dry run")
    args = ap.parse_args()

    if args.keep == args.dup:
        raise SystemExit("--keep and --dup are the same row")

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select creator_id::text, name from creators where creator_id::text in (%s,%s)",
                 (args.keep, args.dup))
    found = dict(cur.fetchall())
    if len(found) != 2:
        raise SystemExit(f"expected both rows to exist, found: {found}")
    if found[args.keep].lower() != found[args.dup].lower():
        raise SystemExit(f"refusing to merge rows with different names: {found} -- this script "
                          "merges a row into its own duplicate, not two different creators")
    log.info("merging duplicate of %r", found[args.keep])

    before_keep, before_dup = counts(cur, args.keep), counts(cur, args.dup)
    log.info("before  keep=%s", {k: v for k, v in before_keep.items() if v})
    log.info("before  dup =%s", {k: v for k, v in before_dup.items() if v})

    cur.execute("""select count(distinct post_id) from reddit_post_creators
                    where creator_id::text in (%s,%s)""", (args.keep, args.dup))
    expected_links = cur.fetchone()[0]
    log.info("expected reddit_post_creators on survivor after merge: %d", expected_links)

    if not args.apply:
        log.info("DRY RUN -- nothing written. Re-run with --apply.")
        return

    # 1. Drop only the links the survivor already asserts; keeping them would break the PK.
    cur.execute("""delete from reddit_post_creators d
                    where d.creator_id::text = %s
                      and exists (select 1 from reddit_post_creators k
                                   where k.creator_id::text = %s and k.post_id = d.post_id)""",
                 (args.dup, args.keep))
    log.info("redundant link rows removed: %d", cur.rowcount)

    # 2. Move everything that remains.
    for t in MOVE:
        try:
            cur.execute(f"update {t} set creator_id = %s::uuid where creator_id::text = %s",
                         (args.keep, args.dup))
            if cur.rowcount:
                log.info("%s re-pointed: %d", t, cur.rowcount)
        except psycopg2.Error as e:
            conn.rollback()
            raise SystemExit(f"re-point of {t} failed, nothing committed: {e}")
    conn.commit()

    # 3. Delete only once the duplicate is provably empty everywhere.
    left = counts(cur, args.dup)
    still = {k: v for k, v in left.items() if v}
    if still:
        log.error("NOT deleting %s -- still referenced by %s", args.dup, still)
        return
    cur.execute("delete from creators where creator_id::text = %s", (args.dup,))
    conn.commit()
    log.info("duplicate creator row deleted")

    after = counts(cur, args.keep)
    log.info("after   keep=%s", {k: v for k, v in after.items() if v})
    got = after.get("reddit_post_creators")
    log.info("VERIFY reddit_post_creators = %s, expected %d -> %s", got, expected_links,
              "OK" if got == expected_links else "MISMATCH")
    conn.close()


if __name__ == "__main__":
    main()
