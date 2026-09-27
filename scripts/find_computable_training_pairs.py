"""Enumerates ALL computable GAIL training pairs against the current real
graph (CAPSTONE_NEXT_STEPS.md P0.4 round 2: 259 creators, 161 resolved
collaboration pairs, 32 sponsorship events).

Only one pair (mrbeast -> CarryMinati) had been individually confirmed
before this script existed. This checks all 32 events x all their
collaborators x all 3 content platforms, not just the one known case, and
is read-only (matches this track's established pattern for direct-DB checks
Track C's API doesn't expose -- see HANDOFF.md Lesson 5).

A pair is "computable" when: (a) the sponsored creator has >=1 resolved
collaborator, AND (b) that collaborator has >=1 dated post on the SAME
platform as the event BEFORE the event date and >=1 AFTER it (real
before/after engagement is only comparable within a platform -- Instagram
like/comment counts and YouTube view counts aren't the same unit).

Usage: DATABASE_URL=... .venv\\Scripts\\python.exe scripts\\find_computable_training_pairs.py
Writes computable_pairs.json (scratch-relative, printed at the end) for
scripts/build_real_hetero_data.py to consume.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import psycopg2

PLATFORM_TABLES = {
    "instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
    "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
    "reddit": ("reddit_posts", "posted_at", "score", "num_comments"),
}


def norm(h: str) -> str:
    h = h.strip().lower()
    for p in ("@", "u/", "r/"):
        if h.startswith(p):
            h = h[len(p):]
    return h


def resolved_pairs(cur) -> dict[str, set[str]]:
    """creator_id -> set of resolved collaborator creator_ids (both directions)."""
    cur.execute("select creator_id::text, youtube_handle, instagram_handle, reddit_handles from creators")
    owners = {"youtube": defaultdict(set), "instagram": defaultdict(set), "reddit": defaultdict(set)}
    for cid, yt, ig, rh in cur.fetchall():
        if yt:
            owners["youtube"][norm(yt)].add(cid)
        if ig:
            owners["instagram"][norm(ig)].add(cid)
        for h in rh or []:
            owners["reddit"][norm(h)].add(cid)
    handle_map = {p: {h: next(iter(o)) for h, o in d.items() if len(o) == 1} for p, d in owners.items()}

    cur.execute(
        "select creator_id::text, platform, handle from creator_related_accounts "
        "where relation_type = 'frequent_collaborator'"
    )
    neighbors: dict[str, set[str]] = defaultdict(set)
    for cid, platform, handle in cur.fetchall():
        if not handle:
            continue
        target = handle_map.get(platform, {}).get(norm(handle))
        if target and target != cid:
            neighbors[cid].add(target)
            neighbors[target].add(cid)
    return neighbors


def content_dates_and_engagement(cur, creator_id: str, platform: str, event_date) -> dict:
    table, date_col, e1, e2 = PLATFORM_TABLES[platform]
    cur.execute(
        f"select {date_col}, coalesce({e1},0) + coalesce({e2},0) as engagement "
        f"from {table} where creator_id::text = %s and {date_col} is not null "
        f"order by {date_col}",
        (creator_id,),
    )
    rows = cur.fetchall()
    before = [(d, e) for d, e in rows if d < event_date]
    after = [(d, e) for d, e in rows if d > event_date]
    return {"n_total": len(rows), "n_before": len(before), "n_after": len(after), "before": before, "after": after}


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL required")
        return 1
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    cur.execute("select creator_id::text, name from creators")
    names = dict(cur.fetchall())

    neighbors = resolved_pairs(cur)
    print(f"Resolved graph: {sum(len(v) for v in neighbors.values()) // 2} distinct pairs, "
          f"{len(neighbors)} creators with >=1 neighbor.")

    cur.execute(
        "select creator_id::text, brand_id::text, platform, content_id, posted_at "
        "from creator_sponsorship_events order by posted_at nulls last"
    )
    events = cur.fetchall()
    print(f"\n{len(events)} total sponsorship events. Checking each against the graph...\n")

    computable = []
    for i, (cid, brand_id, platform, content_id, posted_at) in enumerate(events, 1):
        cname = names.get(cid, cid)
        if posted_at is None:
            print(f"[{i}/{len(events)}] {cname} ({platform}, {content_id}): event has NO posted_at -- skip.")
            continue
        their_neighbors = neighbors.get(cid, set())
        if not their_neighbors:
            print(f"[{i}/{len(events)}] {cname} ({platform}, {posted_at.date()}): 0 graph neighbors -- skip.")
            continue
        found_any = False
        for neighbor_id in their_neighbors:
            nname = names.get(neighbor_id, neighbor_id)
            # Check every platform the neighbor has content on, not just the event's platform --
            # a real before/after comparison must stay within one platform's engagement units,
            # but the NEIGHBOR's own most-active platform may differ from the event's platform.
            for plat in PLATFORM_TABLES:
                d = content_dates_and_engagement(cur, neighbor_id, plat, posted_at)
                if d["n_before"] > 0 and d["n_after"] > 0:
                    found_any = True
                    before_avg = sum(e for _, e in d["before"]) / len(d["before"])
                    after_avg = sum(e for _, e in d["after"]) / len(d["after"])
                    print(f"[{i}/{len(events)}] {cname} ({platform}, {posted_at.date()}) -> "
                          f"{nname} on {plat}: {d['n_before']} before / {d['n_after']} after -- "
                          f"COMPUTABLE (avg engagement before={before_avg:.1f}, after={after_avg:.1f})")
                    computable.append({
                        "sponsored_creator_id": cid,
                        "sponsored_creator_name": cname,
                        "event_platform": platform,
                        "event_content_id": content_id,
                        "event_date": str(posted_at),
                        "neighbor_id": neighbor_id,
                        "neighbor_name": nname,
                        "neighbor_platform": plat,
                        "n_before": d["n_before"],
                        "n_after": d["n_after"],
                        "avg_engagement_before": before_avg,
                        "avg_engagement_after": after_avg,
                        "delta": after_avg - before_avg,
                    })
        if not found_any:
            neighbor_names = ", ".join(names.get(n, n) for n in their_neighbors)
            print(f"[{i}/{len(events)}] {cname} ({platform}, {posted_at.date()}): "
                  f"{len(their_neighbors)} neighbor(s) [{neighbor_names}], none straddle the event on any platform.")

    conn.close()

    print(f"\n=== TOTAL COMPUTABLE (event, neighbor, platform) TRIPLES: {len(computable)} ===")
    distinct_events = len({(c["sponsored_creator_id"], c["event_content_id"]) for c in computable})
    distinct_neighbor_creators = len({c["neighbor_id"] for c in computable})
    print(f"Distinct sponsorship events with >=1 computable pair: {distinct_events} of {len(events)}")
    print(f"Distinct neighbor creators involved: {distinct_neighbor_creators}")

    out_path = os.path.join(os.path.dirname(sys.argv[0]) if len(sys.argv) < 2 else sys.argv[1], "computable_pairs.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(computable, f, indent=2)
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
