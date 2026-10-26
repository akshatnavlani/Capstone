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

# A full-corpus audit is ~1,751 posts at ~10s each, so roughly 5 hours. Without a checkpoint any
# interruption -- a browser hiccup, a laptop sleep, a session ending -- throws the whole run
# away and it has to start from zero. Results are appended per post, so a resumed run only
# checks what it has not seen.
CHECKPOINT = os.path.join(os.path.dirname(__file__), "ownership_audit_checkpoint.json")


def load_seen() -> dict:
    try:
        with open(CHECKPOINT, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_seen(seen: dict) -> None:
    with open(CHECKPOINT, "w", encoding="utf-8") as fh:
        json.dump(seen, fh, ensure_ascii=False, indent=1)

# "- <owner> on <Month> <D>, <YYYY>" -- anchored on the month name so a username containing
# " on " cannot be mistaken for the separator.
OWNER = re.compile(r"-\s*([A-Za-z0-9_.]+)\s+on\s+(?:January|February|March|April|May|June|July|"
                    r"August|September|October|November|December)\s", re.I)


class Disconnected(RuntimeError):
    """No browser bridge. Not a throttle -- retrying cannot help, a human must act."""


def oc(*args, timeout=120):
    env = dict(os.environ)
    if ENV.get("OPENCLI_PROFILE"):
        env["OPENCLI_PROFILE"] = ENV["OPENCLI_PROFILE"]
    return subprocess.run([_OC, "browser", SESSION, *args], capture_output=True, text=True,
                           timeout=timeout, env=env, encoding="utf-8", errors="replace")


# Pacing. Measured 2026-08-19: wait=4/sleep=5 gives 9.4s per post, wait=2/sleep=1 gives 5.1s,
# and BOTH parsed 8 of 8. But that was an 8-post burst, and a burst proves nothing about
# sustained load -- exactly the error that produced the retracted Phase 1 concurrency clearance
# in HANDOFF.md. So this takes the middle setting rather than the fastest one, and a 429 is
# still never retried (run_opencli refuses), which keeps a real throttle visible in the log.
#
# ⚠️ REVERTED TO THE SLOW SETTING 2026-08-19. wait=3/sleep=3 (~7s) held for roughly 200 posts
# and then Instagram throttled: 1,496 consecutive page loads returned
# chrome-error://chromewebdata/, the network-layer throttle signature already documented in
# HANDOFF.md. The burst test that justified 7s measured 8 posts. It was the same mistake as the
# retracted Phase 1 concurrency clearance -- a burst is not evidence about sustained load, and
# knowing that in advance did not stop me making it.
WAIT_SECONDS = "4"
SLEEP_SECONDS = 6

# Stop once the throttle is obvious rather than grinding through the rest of the corpus.
MAX_CONSECUTIVE_UNKNOWN = 12

# ⚠️ A STRIKE BUDGET IS NOT A TIME BUDGET, learned 2026-08-20. The 12-strike abort was
# documented as catching a bad run "in ~2 minutes". That is only true when reads fail
# FAST. When the browser bridge is disconnected, every opencli call blocks for its own
# 45s connect timeout, so one post costs open+wait+eval+sleep = ~141s and twelve strikes
# takes 28 MINUTES. Measured, not estimated: a resumed run sat for 8 minutes without
# recording a single result or printing a single warning.
MAX_STALL_SECONDS = 180

# The failure that actually occurred was NOT a throttle, which is worth separating because
# the two look identical from inside the loop and call for opposite responses. A throttle
# means back off and retry later; a disconnected profile means nothing will EVER succeed
# until a human opens the Chrome profile with the OpenCLI extension. This project has
# already confused these once in the other direction -- `opencli doctor` misreading a
# disconnected daemon as a throttle -- so the signature is matched explicitly.
_DISCONNECTED = "is not connected"


# Read the canonical URL alongside the description, in ONE eval, so both describe the same
# page state. Without this the audit trusts whatever page happens to be loaded.
_OG_VERIFIED_JS = (
    "JSON.stringify({"
    "d: document.querySelector('meta[property=\"og:description\"]')?.content,"
    "u: document.querySelector('meta[property=\"og:url\"]')?.content || location.href"
    "})"
)


def real_owner(post_id: str) -> str | None:
    """Owner per the post's own og:description, or None if it cannot be trusted.

    ⚠️ VERIFIES THE PAGE IS ACTUALLY THE REQUESTED POST. Without this check the audit produced
    provably wrong readings: DC_DLAuzLnl's live og:description says `anushkasharma` on two
    consecutive reads, while the audit had recorded `virat.kohli`. `open` is not guaranteed to
    have completed -- or to have landed anywhere in particular -- by the time `eval` runs, so a
    read can describe a different page entirely. Five consecutive "misattributions", each to a
    different well-known creator, is what that looks like in the data.

    Returning None on a mismatch means the post is simply re-checked later, which is always
    preferable to recording a confident wrong owner and re-attributing real data on it.
    """
    r = oc("open", f"https://www.instagram.com/p/{post_id}/")
    if _DISCONNECTED in (r.stderr or ""):
        raise Disconnected((r.stderr or "").strip().splitlines()[0])
    oc("wait", "time", WAIT_SECONDS)
    try:
        payload = json.loads((oc("eval", _OG_VERIFIED_JS).stdout or "").strip())
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    url = payload.get("u") or ""
    if post_id not in url:
        log.warning("page mismatch for %s (loaded %s) -- discarding this read",
                     post_id, url[:70] or "<no url>")
        return None
    m = OWNER.search(payload.get("d") or "")
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sponsored-only", action="store_true",
                     help="Only sponsorship events -- these gate computable training pairs, "
                          "so a wrong owner here is a label error, not just bad metadata.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--recheck", action="store_true",
                     help="Re-audit posts already recorded in the checkpoint.")
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
    seen = load_seen()
    if not args.recheck:
        rows = [r for r in rows if r[0] not in seen]
    log.info("auditing %d posts (%d already done, resuming)%s", len(rows), len(seen),
              "  [sponsored only]" if args.sponsored_only else "")

    ok = bad = unknown = 0
    consecutive_unknown = 0
    stall_since = None
    misattributed = []
    for pid, user in rows:
        try:
            owner = real_owner(pid)
        except Disconnected as e:
            log.error("BROWSER BRIDGE IS DOWN, not a throttle: %s", e)
            log.error("Open the Chrome profile with the OpenCLI extension enabled, then "
                       "re-run -- the checkpoint resumes from here. Nothing was lost.")
            break
        if owner is None:
            # NOT CHECKPOINTED. An unreadable post is unfinished work, not a result. The first
            # full run recorded 1,496 of these as if they were answers, which permanently
            # excluded them from every resume -- the audit reported 1752/1752 "done" while only
            # 184 posts had actually been verified.
            unknown += 1
            consecutive_unknown += 1
            stall_since = stall_since or time.time()
            stalled_for = time.time() - stall_since
            if stalled_for >= MAX_STALL_SECONDS:
                log.error("%.0fs without a single readable page (%d attempts). Stopping: "
                           "whatever is wrong, it is not going to resolve inside this run.",
                           stalled_for, consecutive_unknown)
                break
            if consecutive_unknown >= MAX_CONSECUTIVE_UNKNOWN:
                log.error("%d consecutive unreadable pages -- Instagram is throttling "
                           "(chrome-error://chromewebdata/). Stopping so the run does not spend "
                           "hours hammering a blocked endpoint; re-run after a cooldown and the "
                           "checkpoint will resume where this left off.", consecutive_unknown)
                break
            time.sleep(SLEEP_SECONDS)
            continue
        consecutive_unknown = 0
        stall_since = None
        if owner.lower() == user.lower():
            ok += 1
        else:
            bad += 1
            misattributed.append((pid, user, owner))
            log.warning("MISATTRIBUTED %s: stored as %s, really %s", pid, user, owner)
        seen[pid] = {"stored": user, "real": owner}
        save_seen(seen)
        time.sleep(SLEEP_SECONDS)
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
