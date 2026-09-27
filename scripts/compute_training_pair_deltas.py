"""Real temporal engagement-delta computation for all canonical computable training pairs.

Round 3 of Phase 1: the graph and pair count have grown enough (54 pairs, orchestrator-verified
via Track A's canonical `pair_count.py`) that this is worth computing exhaustively instead of by
hand on a handful of examples. This script does NOT re-derive its own definition of "computable
pair" -- it imports Track A's canonical `pair_count.py` directly (module import, not a
reimplementation) so the 54-pair set used here is identical to the orchestrator-verified one, not
a hand-rolled variant that could disagree by a few rows the way past rounds did.

For each canonical (event, neighbour) row, computes a per-platform relative engagement lift
wherever the neighbour has BOTH before- and after-event dated activity on that SAME platform:

    lift = (after_avg - before_avg) / (before_avg + 1)

A pair's STRADDLE clause (in pair_count.py) is satisfied across all three platforms pooled
together -- a neighbour with before-only activity on Reddit and after-only activity on YouTube
still counts as a canonical pair, but has no single platform with both sides, so no lift is
computable for it on a like-for-like basis. Those pairs are reported separately and explicitly,
not silently dropped or averaged across incompatible units (views vs. likes vs. score).

READ-ONLY. Writes nothing to the DB. Writes `training_pair_deltas.json` locally.

Run (from repo root, with DATABASE_URL set):
    PYTHONPATH=. .venv/Scripts/python.exe scripts/compute_training_pair_deltas.py
"""

import json
import os
import statistics
import sys

TRACK_A_INGESTION = os.path.join(
    os.path.dirname(__file__), "..", "..", "track-a-data-infra", "scripts", "ingestion"
)
sys.path.insert(0, os.path.abspath(TRACK_A_INGESTION))

import psycopg2  # noqa: E402
from pair_count import CANDIDATES, ENV, compute  # noqa: E402

PLATFORM_TABLES = {
    "instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
    "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
    "reddit": ("reddit_posts", "posted_at", "score", "num_comments"),
}


def platform_engagement(cur, creator_id: str, platform: str, event_date):
    """Real (measured) engagement only.

    DATA-QUALITY FINDING (this round, two layers -- the first fix was insufficient
    on its own):

    Layer 1 -- fully-unmeasured posts: Instagram engagement columns are sparse --
    live check found only 507/1811 (28%) posts have like_count, 715/1811 (39.5%)
    have comment_count. Coalescing NULL to 0 (the naive approach) silently treats
    "never measured" as "measured zero engagement", producing multi-million-percent
    fake "lifts" on Virat Kohli / Anushka Sharma pairs, where most pre-2026 posts
    are entirely unmeasured (both columns NULL) and only late-2026 posts carry real
    6-8 digit values. First fix: exclude posts where BOTH columns are NULL.

    Layer 2 -- partial measurement, found AFTER applying layer 1 (LeBron James's
    top-lift pair still looked implausible): of Instagram's 507+208 partially/fully
    measured posts, 208 have comment_count but NULL like_count and ZERO have the
    reverse (like_count present, comment_count null) -- i.e. `like_count` (the
    larger-magnitude metric) is missing on a real, non-random subset of otherwise-
    measured posts. Same pattern on Reddit: 436 have both `score`+`num_comments`,
    2,312 have `num_comments` only (score always the one missing). A post counted
    "measured" under layer 1 alone can still be a comment-count-only stand-in for a
    like/score-dominated total, biasing whichever side (before/after) happens to
    hold more partially-measured posts. Fix: require BOTH engagement columns
    non-null (fully measured) to include a post at all.
    """
    table, date_col, e1, e2 = PLATFORM_TABLES[platform]
    cur.execute(
        f"select {date_col}, {e1}, {e2} "
        f"from {table} where creator_id::text = %s and {date_col} is not null "
        f"and {e1} is not null and {e2} is not null order by {date_col}",
        (creator_id,),
    )
    rows = cur.fetchall()
    before = [e1v + e2v for d, e1v, e2v in rows if d < event_date]
    after = [e1v + e2v for d, e1v, e2v in rows if d > event_date]
    return before, after


def main() -> int:
    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()

    summary = compute(cur)
    good_rows = [r for r in summary["_rows"] if r[5] > 0 and r[6] > 0]
    print(f"Canonical computable pairs (from pair_count.py): {len(good_rows)}")

    results = []
    same_platform_count = 0
    cross_platform_only_count = 0

    for row in good_rows:
        event_creator_id, item_id, event_platform, event_date, neighbour_id, _, _ = row
        platform_lifts = {}
        for platform in PLATFORM_TABLES:
            before, after = platform_engagement(cur, neighbour_id, platform, event_date)
            if before and after:
                before_avg = statistics.mean(before)
                after_avg = statistics.mean(after)
                lift = (after_avg - before_avg) / (before_avg + 1)
                platform_lifts[platform] = {
                    "n_before": len(before),
                    "n_after": len(after),
                    "avg_before": before_avg,
                    "avg_after": after_avg,
                    "lift": lift,
                }

        if platform_lifts:
            same_platform_count += 1
            mean_lift = statistics.mean(v["lift"] for v in platform_lifts.values())
        else:
            cross_platform_only_count += 1
            mean_lift = None

        results.append(
            {
                "event_creator_id": event_creator_id,
                "event_item_id": item_id,
                "event_platform": event_platform,
                "event_date": str(event_date),
                "neighbour_id": neighbour_id,
                "platform_lifts": platform_lifts,
                "mean_lift": mean_lift,
                "computable_same_platform": bool(platform_lifts),
            }
        )

    conn.close()

    computed = [r for r in results if r["mean_lift"] is not None]
    lifts = [r["mean_lift"] for r in computed]

    print(f"\nSame-platform-computable lifts: {same_platform_count} / {len(good_rows)}")
    print(f"Cross-platform-only straddle (no lift computed): {cross_platform_only_count} / {len(good_rows)}")

    if lifts:
        sorted_lifts = sorted(lifts)
        n = len(sorted_lifts)
        print("\nLift distribution (relative engagement lift, (after-before)/(before+1)):")
        print(f"  n        = {n}")
        print(f"  min      = {sorted_lifts[0]:.4f}")
        print(f"  p25      = {sorted_lifts[int(n * 0.25)]:.4f}")
        print(f"  median   = {statistics.median(sorted_lifts):.4f}")
        print(f"  mean     = {statistics.mean(sorted_lifts):.4f}")
        print(f"  p75      = {sorted_lifts[int(n * 0.75)]:.4f}")
        print(f"  max      = {sorted_lifts[-1]:.4f}")
        if n > 1:
            print(f"  stdev    = {statistics.stdev(sorted_lifts):.4f}")

        print("\nAll computed pairs, sorted by |lift| descending (outlier check):")
        for r in sorted(computed, key=lambda r: -abs(r["mean_lift"]))[:15]:
            print(
                f"  lift={r['mean_lift']:+.3f}  event={r['event_item_id'][:16]:<16} "
                f"({r['event_platform']})  neighbour={r['neighbour_id'][:8]}  "
                f"platforms={list(r['platform_lifts'].keys())}"
            )

    with open("training_pair_deltas.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nWrote training_pair_deltas.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
