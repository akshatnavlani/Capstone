"""SIMULATED validation on the REAL network (semi-synthetic benchmark). Writes only a local JSON; nothing goes to the database or to any real result.

    PYTHONPATH=<checkout of review2-eesha-model> python scripts/sim_semisynthetic_benchmark.py --rows <dir>/training_pair_deltas.json [--cache rows_cache.json]

WHAT IT DOES. Keeps every real (event, neighbour) row of the shared-brand relation with its REAL noise: the neighbour's real lift after the sponsored post (L) and its real
lift at placebo dates (P). Then it PLANTS a known spillover effect `delta` (added to L) and a fake pre-existing trend `tau` per neighbour (added to BOTH L and P, because a trend
that was already there shows up at every date), resamples neighbours with replacement (a new "study" each time) and asks two analysts:
  * NAIVE        "is the neighbour's lift after the sponsored post above zero?" (median over neighbours of L, bootstrap interval over neighbours)
  * PLACEBO      "is it above the same neighbour's lift at placebo dates?" (median of L - P, same interval)  -- the test used on the real data (Test A)
It reports, per planted effect: the average estimate, its error against the truth, and how often the interval excludes zero (detection rate; at delta = 0 that is the
false-alarm rate). It answers: does the placebo penalty remove an injected bias, and what spillover size could we have detected with the real sample?
Assumptions (stated on the dashboard): the planted trend is normal with mean 0.15 and sd 0.15 per neighbour; the effect is the same for every row. Neural GAIL is NOT in this
table: it needs Eesha's checkout and a training run (scripts/gail_acceptance.py, which failed 0 of 4 simulated checks on 26 Oct).
"""
import argparse
import json
import os
import random
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
TABLES = {"instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
          "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
          "reddit": ("reddit_posts", "posted_at", "score", "num_comments")}
SHIFTS = [-150, -120, -90]
DELTAS = [0.0, 0.1, 0.25, 0.5, 1.0]
TREND_MEAN, TREND_SD = 0.15, 0.15


def real_rows(rows_path: str):
    """[(neighbour, L, P)] for mature shared-brand rows that have placebo dates."""
    import psycopg2
    from dotenv import dotenv_values

    from ml.engagement_lift import platform_lift, row_target
    from ml.target_clustering import DEFAULT_WINDOW_DAYS, windowed_engagement

    cur = psycopg2.connect(os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]).cursor()
    series = defaultdict(list)
    for platform, (table, dcol, e1, e2) in TABLES.items():
        cur.execute(f"select creator_id::text, {dcol}, {e1}, {e2} from {table} where creator_id is not null and {dcol} is not null and {e1} is not null and {e2} is not null order by {dcol}")
        for cid, d, a, b in cur.fetchall():
            series[(cid, platform)].append((d, a + b))

    def lift_at(neighbour, when):
        pl = {}
        for platform in TABLES:
            s = series.get((neighbour, platform))
            if s:
                before, after = windowed_engagement(s, when, DEFAULT_WINDOW_DAYS)
                if before and after:
                    pl[platform] = platform_lift(before, after)
        return row_target(pl, "median") if pl else None

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    out = []
    for r in json.load(open(rows_path, encoding="utf-8")):
        if r.get("relation") != "shared_brand" or r.get("robust_lift") is None or datetime.fromisoformat(r["event_date"]) >= cutoff:
            continue
        when = datetime.fromisoformat(r["event_date"])
        base = [x for x in (lift_at(r["neighbour_id"], when + timedelta(days=d)) for d in SHIFTS) if x is not None]
        if base:
            out.append((r["neighbour_id"], float(r["robust_lift"]), float(st.mean(base))))
    return out


def simulate(rows, reps: int, inner: int, seed: int, affected_share: float = 1.0):
    by_nb = defaultdict(list)
    for nb, L, P in rows:
        by_nb[nb].append((L, P))
    nbs = list(by_nb)
    LP = {nb: np.array(v) for nb, v in by_nb.items()}
    rng = np.random.default_rng(seed)
    table = {}
    for delta in DELTAS:
        res = {"naive": [], "placebo": []}
        det = {"naive": 0, "placebo": 0}
        for _ in range(reps):
            pick = rng.choice(len(nbs), size=len(nbs), replace=True)
            tau = rng.normal(TREND_MEAN, TREND_SD, size=len(nbs))
            eff = delta * (rng.random(len(nbs)) < affected_share)   # the effect reaches only this share of neighbours
            naive = np.array([np.mean(LP[nbs[i]][:, 0] + e + t) for i, t, e in zip(pick, tau, eff)])
            placebo = np.array([np.mean(LP[nbs[i]][:, 0] + e + t - (LP[nbs[i]][:, 1] + t)) for i, t, e in zip(pick, tau, eff)])
            for name, v in (("naive", naive), ("placebo", placebo)):
                res[name].append(float(np.median(v)))
                idx = rng.integers(0, len(v), size=(inner, len(v)))
                lo = np.percentile(np.median(v[idx], axis=1), 2.5)
                det[name] += int(lo > 0)
        truth = delta * affected_share   # the average effect over all neighbours
        table[str(delta)] = {k: {"mean_estimate": float(np.mean(res[k])), "error_vs_truth": float(np.mean(res[k]) - truth), "detects_effect_share": det[k] / reps} for k in res}
    return table


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows")
    ap.add_argument("--cache", help="JSON cache of the real rows, so the slow step runs once")
    ap.add_argument("--out", default=str(ROOT / "models" / "sim_semisynthetic_benchmark.json"))
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--inner", type=int, default=300)
    args = ap.parse_args()
    if args.cache and Path(args.cache).exists():
        rows = [tuple(r) for r in json.load(open(args.cache, encoding="utf-8"))]
    else:
        rows = real_rows(args.rows)
        if args.cache:
            Path(args.cache).write_text(json.dumps(rows), encoding="utf-8")
    nbs = {r[0] for r in rows}
    print(f"real rows with placebo dates: {len(rows)} from {len(nbs)} neighbours; real median of L - P = {st.median(L - P for _, L, P in rows):+.3f}", flush=True)
    table = simulate(rows, args.reps, args.inner, seed=21)
    sparse = simulate(rows, args.reps, args.inner, seed=22, affected_share=0.2)
    print("SIMULATED planted effect | NAIVE estimate (error) detects | PLACEBO estimate (error) detects")
    for d, v in table.items():
        n, p = v["naive"], v["placebo"]
        print(f"   delta {float(d):4.2f}          | {n['mean_estimate']:+.3f} ({n['error_vs_truth']:+.3f}) {n['detects_effect_share']:.2f}      | {p['mean_estimate']:+.3f} ({p['error_vs_truth']:+.3f}) {p['detects_effect_share']:.2f}")
    print("SIMULATED, effect reaches only 20% of neighbours (planted effect = delta for them, 0.2 x delta on average): PLACEBO detection")
    for d, v in sparse.items():
        print(f"   delta {float(d):4.2f} (average effect {0.2 * float(d):.2f}) | PLACEBO estimate {v['placebo']['mean_estimate']:+.3f} detects {v['placebo']['detects_effect_share']:.2f}")
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "simulated": True, "real_rows": len(rows), "real_neighbours": len(nbs),
           "assumptions": {"planted_trend": f"normal, mean {TREND_MEAN}, sd {TREND_SD} per neighbour, added to the lift after the event and at placebo dates",
                           "planted_effect": "same for every row, added to the lift after the event only", "replications": args.reps, "interval": "2.5th percentile of a neighbour bootstrap above zero"},
           "table": table, "table_effect_reaches_20_percent_of_neighbours": sparse}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
