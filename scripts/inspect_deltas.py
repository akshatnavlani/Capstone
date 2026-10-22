"""Read-only diagnostic on training_pair_deltas.json.

WHY. The lift distribution from the first live run is outlier-dominated
(median +0.045, mean +1.732, max +34.72, stdev 6.89 on an effective N of 19).
Two explanations fit that shape and they point to different fixes:

  (a) real spillover that is genuinely heavy-tailed  -> keep the rows, model
      the tail (log1p target, robust loss)
  (b) thin-data artifacts -- a lift computed from one post before and one
      after is noise wearing a number        -> filter on a minimum post count

This script does not guess between them. It prints the post counts behind
every lift so the answer is visible, then shows what the distribution would
look like under a few minimum-post thresholds.

Writes nothing. Touches no database.

Run from the repo root:
    python scripts/inspect_deltas.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

PATH = Path("training_pair_deltas.json")


def _min_counts(row: dict) -> tuple[int, int]:
    """Thinnest before/after post counts across the platforms used for a row.

    The MINIMUM, not the mean: a row averaging a well-measured platform with a
    one-post platform is only as trustworthy as its weakest side.
    """
    lifts = row["platform_lifts"].values()
    return (
        min(v["n_before"] for v in lifts),
        min(v["n_after"] for v in lifts),
    )


def _describe(values: list[float]) -> str:
    if not values:
        return "n=0"
    if len(values) == 1:
        return f"n=1   median={values[0]:+.3f}"
    ordered = sorted(values)
    return (
        f"n={len(values):<4} "
        f"median={statistics.median(ordered):+.3f}  "
        f"mean={statistics.mean(ordered):+.3f}  "
        f"stdev={statistics.pstdev(ordered):.3f}  "
        f"max|v|={max(abs(v) for v in ordered):.3f}"
    )


def main() -> int:
    if not PATH.exists():
        print(f"{PATH} not found. Run scripts/compute_training_pair_deltas.py first.")
        return 1

    rows = [r for r in json.loads(PATH.read_text(encoding="utf-8"))
            if r.get("mean_lift") is not None]
    if not rows:
        print("No rows with a computable lift.")
        return 1

    rows.sort(key=lambda r: -abs(r["mean_lift"]))

    print("Every computed lift, with the post counts behind it")
    print("(n_before / n_after are the THINNEST platform used for that row)\n")
    print(f"{'lift':>10}  {'n_bef':>5} {'n_aft':>5}  {'clust_w':>7}  neighbour  platforms")
    print("-" * 78)
    for r in rows:
        before, after = _min_counts(r)
        flag = "  <-- thin" if min(before, after) <= 2 else ""
        print(
            f"{r['mean_lift']:>+10.3f}  {before:>5} {after:>5}  "
            f"{r.get('cluster_weight', 1.0):>7.3f}  "
            f"{r['neighbour_id'][:8]}   "
            f"{','.join(sorted(r['platform_lifts']))}{flag}"
        )

    print("\n\nWhat a minimum-post threshold would do to the distribution")
    print("(the question: does the tail survive when thin rows are dropped?)\n")
    for threshold in (1, 2, 3, 5):
        kept = [r for r in rows if min(_min_counts(r)) >= threshold]
        values = [r["mean_lift"] for r in kept]
        clusters = len({r.get("cluster_id", r["neighbour_id"]) for r in kept})
        print(f"  >= {threshold} posts each side:  {_describe(values)}")
        print(f"{'':<24}effective N (clusters) = {clusters}")

    print(
        "\nReading it: if the extreme lifts all sit on rows marked 'thin', they are\n"
        "measurement noise and a threshold is the fix. If large lifts survive at\n"
        ">= 5 posts a side, the tail is real and belongs in the model, not the bin."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())