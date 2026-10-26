"""Re-attribute posts the ownership audit found filed under the wrong creator.

Reads `ownership_audit_checkpoint.json` and fixes every post whose real owner differs from the
stored username, applying the same rule the three user-approved re-attributions established:

  owner IS a creator in our set   -> re-point creator_id + username at that creator. The post
                                     is real content by a real creator, just filed wrongly.
  owner is NOT one of our creators -> username = the real owner, creator_id = NULL. The post is
                                     someone else's content; it belongs to no creator we track,
                                     and NULL says exactly that.

⚠️ NO brands row is invented here. The two brands created by hand (duroflexworld,
reliancejewels) were named explicitly by the user and are unambiguously brands. Most owners the
audit turns up are ordinary accounts -- @radhika_dhopavkar, @beercusp -- and guessing which are
"brands" would fabricate a classification the data does not support. A NULL creator_id already
carries the whole truth: not our creator's content.

WHY THIS MATTERS BEYOND TIDINESS. A misattributed post inflates the wrongful owner's ACTIVITY
WINDOW, and straddle checks ask whether a neighbour was active either side of an event date. So
a post that was never theirs can make another creator's pair look computable. That is how
Task 1's correction came out at -6 pairs rather than the -5 predicted from removing the events
alone.

`instagram_posts.username` has an FK to `instagram_profiles`, so the owner is inserted there
first (username only -- that does NOT make them a creator).

Run: python reattribute_posts.py [--dry-run]
"""

import argparse
import io
import json
import logging
import os

import psycopg2

from orchestrator import ENV

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reattribute")

CHECKPOINT = os.path.join(os.path.dirname(__file__), "ownership_audit_checkpoint.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with io.open(CHECKPOINT, encoding="utf-8") as fh:
        seen = json.load(fh)
    wrong = {pid: v for pid, v in seen.items()
             if v.get("real") and v["real"].lower() != v["stored"].lower()}
    log.info("audit has checked %d posts; %d are misattributed", len(seen), len(wrong))

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("select lower(instagram_handle), creator_id from creators "
                     "where instagram_handle is not null")
        creators = dict(cur.fetchall())

    to_creator = nulled = skipped = 0
    for pid, v in sorted(wrong.items()):
        owner = v["real"]
        with conn.cursor() as cur:
            cur.execute("select username, creator_id from instagram_posts where post_id=%s", (pid,))
            row = cur.fetchone()
            if not row:
                skipped += 1
                continue
            if row[0].lower() == owner.lower():
                skipped += 1          # already fixed by an earlier run
                continue
            if args.dry_run:
                dest = "creator " + owner if owner.lower() in creators else "NULL creator"
                log.info("[dry] %s: %s -> %s (%s)", pid, row[0], owner, dest)
                continue
            cur.execute("insert into instagram_profiles (username) values (%s) "
                         "on conflict (username) do nothing", (owner,))
            cid = creators.get(owner.lower())
            cur.execute("update instagram_posts set username=%s, creator_id=%s where post_id=%s",
                         (owner, cid, pid))
            if cid:
                to_creator += 1
                log.info("%s: %s -> %s (a creator we track)", pid, row[0], owner)
            else:
                nulled += 1
                log.info("%s: %s -> %s (not our creator; creator_id NULL)", pid, row[0], owner)
        conn.commit()

    conn.close()
    log.info("DONE re-pointed_to_creator=%d set_null=%d skipped=%d%s",
              to_creator, nulled, skipped, "  [DRY RUN]" if args.dry_run else "")


if __name__ == "__main__":
    main()
