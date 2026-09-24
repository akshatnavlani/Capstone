"""A3 regression canary: live structural counts must match the snapshot.

WHAT IT CATCHES. `pair_count.py` is the canonical definition, but nothing
fails if ingestion or a schema change silently moves the numbers it reports
(creator count, graph size, co-occurrence volume) -- every downstream consumer
(Tracks B/C/D) would just train/serve on shifted data. This script compares
three exact structural counts plus a pairs floor against
`pair_count_snapshot.json` and exits nonzero with the diff.

READ-ONLY. Writes nothing, never touches approval_status or any data table.

SNAPSHOT SEMANTICS. Exact match for creators / collab_edge_pairs /
coocc_directed; floor (>=) for computable_pairs, which legitimately grows
with collection -- a shrink means data loss or a deliberate correction, both
of which deserve a loud conscious snapshot bump, not silence.

Exit codes: 0 = match, 1 = drift (fail loudly), 2 = skip (no DATABASE_URL).

Run: python pair_count_canary.py   (after any ingestion or schema change)
"""

import json
import sys
from pathlib import Path

import psycopg2

from orchestrator import ENV
from pair_count import PAIRS, compute

SNAPSHOT = Path(__file__).with_name("pair_count_snapshot.json")


def live_counts() -> dict:
    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()
    s = compute(cur)
    cur.execute("select count(*) from creators")
    creators = cur.fetchone()[0]
    cur.execute(
        """select count(*) from (
             select distinct a.creator_id, b.creator_id
               from reddit_post_creators a
               join reddit_post_creators b
                 on a.post_id = b.post_id and a.creator_id <> b.creator_id) t"""
    )
    coocc = cur.fetchone()[0]
    conn.close()
    return {
        "creators": creators,
        "collab_edge_pairs": s["collab_edge_pairs"],
        "coocc_directed": coocc,
        "computable_pairs": s["computable_pairs"],
    }


def main() -> int:
    if not ENV.get("DATABASE_URL"):
        print("SKIP: no DATABASE_URL (canary needs the live DB)")
        return 2
    snap = json.loads(SNAPSHOT.read_text())
    got = live_counts()
    errors = []
    for key in ("creators", "collab_edge_pairs", "coocc_directed"):
        if got[key] != snap[key]:
            errors.append(f"{key}: live {got[key]} != snapshot {snap[key]}")
    if got["computable_pairs"] < snap["computable_pairs_floor"]:
        errors.append(
            f"computable_pairs {got['computable_pairs']} < floor "
            f"{snap['computable_pairs_floor']} (shrink = data loss or a "
            "deliberate correction -- bump the snapshot consciously)"
        )
    if errors:
        print("CANARY FAIL -- counts moved:")
        for e in errors:
            print(f"  - {e}")
        print(
            "If ingestion legitimately grew the data, bump "
            "pair_count_snapshot.json deliberately with new live values + "
            "date. Never bump to silence unexplained drift."
        )
        return 1
    print(f"CANARY OK: {got}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
