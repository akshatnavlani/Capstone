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

import psycopg2  # noqa: E402

# Track A's canonical pair definition. Imported through _track_a because
# pair_count's own `from orchestrator import ENV` otherwise drags in the
# ingestion orchestrator, which refuses to import without the opencli browser
# tool on PATH. See scripts/_track_a.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _track_a import import_pair_count  # noqa: E402

_pair_count = import_pair_count()
CANDIDATES, ENV, compute = _pair_count.CANDIDATES, _pair_count.ENV, _pair_count.compute

from ml.engagement_lift import (  # noqa: E402
    PLATFORM_TABLES,
    platform_engagement,
    platform_lift,
    row_target,
)
from ml.target_clustering import (  # noqa: E402
    DEFAULT_WINDOW_DAYS,
    cluster_events,
    cluster_weights,
    summarize,
)

# Half-width of the engagement measurement window, in days. Also the gap at
# which two events on the same neighbour stop being treated as one observation.
WINDOW_DAYS = DEFAULT_WINDOW_DAYS





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
            before, after = platform_engagement(cur, neighbour_id, platform, event_date, WINDOW_DAYS)
            if before and after:
                # Shared with train_prod_model.py via ml/engagement_lift.py, so
                # the number inspected here is the number that trains.
                platform_lifts[platform] = platform_lift(before, after)

        if platform_lifts:
            same_platform_count += 1
            mean_lift = row_target(platform_lifts, statistic="mean")
            robust_lift = row_target(platform_lifts, statistic="median")
        else:
            cross_platform_only_count += 1
            mean_lift = None
            robust_lift = None

        results.append(
            {
                "event_creator_id": event_creator_id,
                "event_item_id": item_id,
                "event_platform": event_platform,
                "event_date": str(event_date),
                "neighbour_id": neighbour_id,
                "platform_lifts": platform_lifts,
                "mean_lift": mean_lift,
                "robust_lift": robust_lift,
                "computable_same_platform": bool(platform_lifts),
            }
        )

    # E2: label each row with the cluster of events it shares an engagement
    # change with, and a weight of 1/cluster_size. The honest sample size is the
    # number of CLUSTERS, not the number of rows -- a point the training script
    # and every confidence interval downstream depend on.
    lift_rows = [r for r in results if r["mean_lift"] is not None]
    clusters = cluster_events(lift_rows, window_days=WINDOW_DAYS)
    weights = cluster_weights(clusters)
    for row, cid, w in zip(lift_rows, clusters, weights):
        row["cluster_id"] = cid
        row["cluster_weight"] = w

    stats = summarize(clusters)
    print(f"\nE2 clustering (window {WINDOW_DAYS}d):")
    print(f"  lift-computable rows          {stats['rows']}")
    print(f"  distinct observations         {stats['clusters']}   <- effective N")
    print(f"  distinct neighbours           {len({r['neighbour_id'] for r in lift_rows})}"
          f"   (what per-creator averaging gave)")
    if stats["largest"]:
        cid, n = stats["largest"][0]
        print(f"  largest cluster               {n} rows ({stats['max_cluster_share']:.0%}) -- {cid}")
        if stats["max_cluster_share"] > 0.3:
            print("  !! one engagement change dominates the dataset; quote the")
            print("     cluster count, never the row count.")

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

        # Mean-based vs median-based target, side by side. If the median-based
        # column has a much smaller spread for the same rows, the extra variance
        # in the mean-based one is viral-post noise and not signal to model.
        robust = [r["robust_lift"] for r in computed]
        print("\nMean-based vs median-based target (same rows, same windows):")
        print(f"  {'':<10} {'mean-based':>12} {'median-based':>14}")
        print(f"  {'median':<10} {statistics.median(lifts):>12.4f} {statistics.median(robust):>14.4f}")
        print(f"  {'mean':<10} {statistics.mean(lifts):>12.4f} {statistics.mean(robust):>14.4f}")
        print(f"  {'max |v|':<10} {max(abs(v) for v in lifts):>12.4f} "
              f"{max(abs(v) for v in robust):>14.4f}")
        if n > 1:
            print(f"  {'stdev':<10} {statistics.stdev(lifts):>12.4f} "
                  f"{statistics.stdev(robust):>14.4f}")

        print("\nAll computed pairs, sorted by |lift| descending (outlier check):")
        for r in sorted(computed, key=lambda r: -abs(r["mean_lift"]))[:15]:
            print(
                f"  lift={r['mean_lift']:+.3f}  med={r['robust_lift']:+.3f}  "
                f"event={r['event_item_id'][:16]:<16} "
                f"({r['event_platform']})  neighbour={r['neighbour_id'][:8]}  "
                f"platforms={list(r['platform_lifts'].keys())}"
            )

    with open("training_pair_deltas.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nWrote training_pair_deltas.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())