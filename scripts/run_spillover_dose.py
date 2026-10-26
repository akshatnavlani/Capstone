"""Dose-response check for the shared-brand link: does a neighbour tied to the sponsoring creator by MORE shared brands show a bigger lift than at placebo dates? READ ONLY.

    PYTHONPATH=<checkout of review2-eesha-model> python scripts/run_spillover_dose.py --rows <dir>/training_pair_deltas.json [--out models/spillover_dose.json]

Same within-neighbour placebo comparison as scripts/run_spillover_placebo.py (event lift minus the same neighbour's mean lift at placebo dates +-90/120/150 days; events older
than 90 days only), but the rows are split by tie strength = the number of brands the two creators both promoted. If the link carried influence, the difference should grow
with tie strength. Reported per bin with a bootstrap over neighbours, plus a rank trend (Spearman of tie strength with the paired difference, bootstrap over neighbours).
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

import psycopg2
from dotenv import dotenv_values

from ml.engagement_lift import platform_lift, row_target
from ml.target_clustering import DEFAULT_WINDOW_DAYS, windowed_engagement

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_ranking_test import spearman  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
TABLES = {"instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
          "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
          "reddit": ("reddit_posts", "posted_at", "score", "num_comments")}
SHIFTS = [-150, -120, -90]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", default=str(ROOT / "models" / "spillover_dose.json"))
    ap.add_argument("--boot", type=int, default=3000)
    args = ap.parse_args()
    cur = psycopg2.connect(os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]).cursor()
    cur.execute("select creator_id::text from creator_verification where creator_id is not null and link_level in ('confirmed','probable')")
    core = {r[0] for r in cur.fetchall()}
    cur.execute("select e.creator_id::text, e.brand_id::text from creator_sponsorship_events e join brands b on b.brand_id = e.brand_id "
                "where e.creator_id is not null and b.category is not null and b.category <> 'not_a_brand' group by 1, 2")
    brands = defaultdict(set)
    for cid, b in cur.fetchall():
        brands[cid].add(b)
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
    rows = [r for r in json.load(open(args.rows, encoding="utf-8")) if r.get("relation") == "shared_brand" and r.get("robust_lift") is not None
            and datetime.fromisoformat(r["event_date"]) < cutoff]
    diffs = []
    for r in rows:
        when = datetime.fromisoformat(r["event_date"])
        base = [x for x in (lift_at(r["neighbour_id"], when + timedelta(days=d)) for d in SHIFTS) if x is not None]
        if base:
            tie = len(brands.get(r["event_creator_id"], set()) & brands.get(r["neighbour_id"], set()))
            diffs.append((r["neighbour_id"], tie, r["robust_lift"] - st.mean(base)))
    print(f"mature shared-brand rows with a placebo: {len(diffs)}", flush=True)
    rnd = random.Random(9)
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": len(diffs), "bins": {}}

    def per_neighbour(sub):
        by = defaultdict(list)
        for nb, _, d in sub:
            by[nb].append(d)
        return {k: st.mean(v) for k, v in by.items()}

    for label, keep in (("1 shared brand", lambda t: t == 1), ("2 shared brands", lambda t: t == 2), ("3 or more", lambda t: t >= 3)):
        sub = [x for x in diffs if keep(x[1])]
        means = per_neighbour(sub)
        if len(means) < 8:
            out["bins"][label] = {"rows": len(sub), "neighbours": len(means), "note": "too few neighbours"}
            print(f"{label:16s} rows {len(sub):5d} neighbours {len(means):3d} (too few)")
            continue
        keys = list(means)
        draws = sorted(st.median(means[rnd.choice(keys)] for _ in keys) for _ in range(args.boot))
        out["bins"][label] = {"rows": len(sub), "neighbours": len(means), "median_of_neighbour_means": st.median(means.values()), "ci95": [draws[int(.025 * args.boot)], draws[int(.975 * args.boot)]]}
        print(f"{label:16s} rows {len(sub):5d} neighbours {len(means):3d} | median paired difference {st.median(means.values()):+.3f} [{draws[int(.025 * args.boot)]:+.3f}, {draws[int(.975 * args.boot)]:+.3f}]")
    by_nb = defaultdict(list)
    for nb, t, d in diffs:
        by_nb[nb].append((t, d))
    nbs = [(st.mean(t for t, _ in v), st.mean(d for _, d in v)) for v in by_nb.values() if len(v) >= 2]
    if len(nbs) >= 15:
        rho = spearman([a for a, _ in nbs], [b for _, b in nbs])
        boots = sorted(spearman([x[0] for x in s], [x[1] for x in s]) for s in ([rnd.choice(nbs) for _ in nbs] for _ in range(args.boot)))
        out["trend"] = {"neighbours": len(nbs), "spearman_tie_strength_vs_paired_difference": rho, "ci95": [boots[int(.025 * args.boot)], boots[int(.975 * args.boot)]]}
        print(f"trend over {len(nbs)} neighbours: Spearman(tie strength, paired difference) = {rho:+.2f} [{boots[int(.025 * args.boot)]:+.2f}, {boots[int(.975 * args.boot)]:+.2f}]")
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
