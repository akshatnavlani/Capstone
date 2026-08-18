"""Detect Instagram posts filed under the wrong creator.

WHY THIS EXISTS (found 2026-08-19). A profile grid mixes in posts owned by OTHER accounts --
tagged posts and Instagram "collab" posts, which appear on every collaborator's grid. The
orchestrator's grid selector took every /p/ and /reel/ link and wrote them all with
`username=<handle>, creator_id=<that creator>`, so another account's post -- and its
engagement counts -- were recorded as this creator's.

`own_post_paths()` in orchestrator.py now filters these at collection time. This script finds
the ones already stored, because a post's own og:description names its true owner:

    "885 likes, 33 comments - <owner> on May 9, 2026: "caption...""

Measured on first run: 2 of 14 random posts (14.3%) and 3 of 52 sponsored posts (5.8%) were
misattributed. Two of the three sponsored ones were really owned by BRAND accounts
(duroflexworld, reliancejewels), which is a label error, not just an attribution nit.

READ-ONLY by default. `--fix` is deliberately not implemented: re-attributing a sponsorship
event changes the collaboration graph and the computable-pair count that Track B trains on,
so it is the user's call, not this script's.

Run: python audit_post_ownership.py [--sponsored-only] [--limit N]
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import time

import psycopg2

from orchestrator import ENV, _OG_JS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ownership")

_OC = shutil.which("opencli")
SESSION = "ownaudit"

# "- <owner> on <Month> <D>, <YYYY>" -- anchored on the month name so a username containing
# " on " cannot be mistaken for the separator.
OWNER = re.compile(r"-\s*([A-Za-z0-9_.]+)\s+on\s+(?:January|February|March|April|May|June|July|"
                    r"August|September|October|November|December)\s", re.I)


def oc(*args, timeout=120):
    env = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        env["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    return subprocess.run([_OC, "browser", SESSION, *args], capture_output=True, text=True,
                           timeout=timeout, env=env, encoding="utf-8", errors="replace")


def real_owner(post_id: str) -> str | None:
    oc("open", f"https://www.instagram.com/p/{post_id}/")
    oc("wait", "time", "4")
    try:
        desc = json.loads((oc("eval", _OG_JS).stdout or "").strip())
    except Exception:
        return None
    m = OWNER.search(desc or "")
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sponsored-only", action="store_true",
                     help="Only sponsorship events -- these gate computable training pairs, "
                          "so a wrong owner here is a label error, not just bad metadata.")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    where = "username is not null"
    if args.sponsored_only:
        where += " and (is_sponsored or has_paid_partnership_label)"
    order = "post_id" if args.sponsored_only else "random()"

    conn = psycopg2.connect(ENV["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute(f"select post_id, username from instagram_posts where {where} "
                     f"order by {order}" + (f" limit {int(args.limit)}" if args.limit else ""))
        rows = cur.fetchall()
    conn.close()
    log.info("auditing %d posts%s", len(rows), "  [sponsored only]" if args.sponsored_only else "")

    ok = bad = unknown = 0
    misattributed = []
    for pid, user in rows:
        owner = real_owner(pid)
        if owner is None:
            unknown += 1
        elif owner.lower() == user.lower():
            ok += 1
        else:
            bad += 1
            misattributed.append((pid, user, owner))
            log.warning("MISATTRIBUTED %s: stored as %s, really %s", pid, user, owner)
        time.sleep(5)
    oc("close")

    resolvable = ok + bad
    log.info("checked=%d resolvable=%d correct=%d misattributed=%d no_og=%d",
              len(rows), resolvable, ok, bad, unknown)
    if resolvable:
        log.info("contamination rate: %d/%d = %.1f%%", bad, resolvable, 100 * bad / resolvable)
    for pid, user, owner in misattributed:
        print(f"  {pid}  stored={user}  real={owner}")


if __name__ == "__main__":
    main()
