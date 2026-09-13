"""Evaluate account_classify.py against the stored hand-labelled held-out sets.

WHY THIS EXISTS. The "57% held-out accuracy" that this loop was asked to fix was a one-off
measurement nobody had stored, so it could not be reproduced or re-checked -- which is how it
sat unresolved for rounds. `heldout_accounts.json` now holds the labelled sets, and this script
is the thing that reads them, so a number can be re-derived in seconds instead of rebuilt.

⚠️ A SET STOPS BEING HELD-OUT THE MOMENT YOU TUNE ON IT. set1 and set2 have both been tuned
against, so their scores are optimistic and are labelled as such below. Only a set built AFTER
the last lexicon change is a clean generalization estimate. `--propose` exists to build the
next one.

Labels are human judgements read off each real bio. Never regenerate them from classifier
output -- that measures self-consistency, not accuracy.

Run:
  python eval_account_classify.py                  # score every stored set
  python eval_account_classify.py --propose 25     # candidates for a NEW set, to hand-label
"""

import argparse
import io
import json
import os

import psycopg2

from account_classify import classify_from_profile, load_known_orgs
from orchestrator import ENV

SETS_PATH = os.path.join(os.path.dirname(__file__), "heldout_accounts.json")


def load_sets() -> dict:
    with io.open(SETS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def score(rows, orgs) -> tuple[int, int, list]:
    ok = 0
    misses = []
    for r in rows:
        got, why = classify_from_profile(r["name"], r["bio"], r["handle"], known_orgs=orgs)
        if got == r["label"]:
            ok += 1
        else:
            misses.append((r["handle"], got, r["label"], why))
    return ok, len(rows), misses


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--propose", type=int, default=0,
                     help="Print N accounts with real bios that appear in NO stored set, as "
                          "candidates for a fresh held-out set. They are printed unlabelled "
                          "on purpose -- a human reads the bio and assigns the label.")
    ap.add_argument("--verbose", action="store_true", help="List every miss.")
    args = ap.parse_args()

    data = load_sets()
    conn = psycopg2.connect(ENV["DATABASE_URL"])
    orgs = load_known_orgs(conn)

    if args.propose:
        seen = {r["handle"].lower() for k, v in data.items()
                if k.startswith("set") for r in (v if isinstance(v, list) else [])}
        # ALSO exclude the tuned suite. Without this the proposer happily offered
        # @technicalguruji and @ajinkyarahane, both of which the lexicon was tuned against --
        # labelling those into "set3" would have produced a clean-looking number that is not
        # clean at all, which is the exact failure this whole item exists to stop repeating.
        from test_account_classify import CASES
        seen |= {c[0].lower() for c in CASES}
        with conn.cursor() as cur:
            cur.execute("""
                select username, coalesce(full_name, ''), coalesce(bio, '')
                from instagram_profiles
                where length(coalesce(bio, '')) > 25
                order by md5(username)
            """)
            fresh = [r for r in cur.fetchall() if r[0].lower() not in seen][: args.propose]
        conn.close()
        print(f"{len(fresh)} candidates not present in any stored set "
               f"(label these by hand, then add as set3):\n")
        for h, n, b in fresh:
            print(f"  handle: {h}\n  name  : {n!r}\n  bio   : {' '.join(b.split())[:150]}\n")
        return

    print(f"{'set':<8}{'source':<28}{'n':>4}{'correct':>9}{'accuracy':>10}   status")
    for key in sorted(k for k in data if k.startswith("set") and not k.endswith("_source")):
        rows = data[key]
        if not isinstance(rows, list):
            continue
        ok, n, misses = score(rows, orgs)
        src = data.get(f"{key}_source", "?")
        status = "TUNED ON — optimistic" if key in data.get("_tuned_on", []) else "clean"
        print(f"{key:<8}{src[:27]:<28}{n:>4}{ok:>9}{100*ok/n:>9.1f}%   {status}")
        if args.verbose:
            for h, got, want, why in misses:
                print(f"        MISS {h[:22]:<24} got={got:<21} want={want}")
                print(f"             {why[:96]}")
    conn.close()


if __name__ == "__main__":
    main()
