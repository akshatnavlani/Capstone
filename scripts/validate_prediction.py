"""READ-ONLY out-of-time check of the per-rupee ranking inputs (Track A, A1 + A2).

    python scripts/validate_prediction.py [--test-days 120] [--recent-days 90]

Test period: posts published between (today - 14 - test_days) and (today - 14);
everything a prediction uses comes from before the predicted post (A1) or before
the test period (A2 direct-effect scores). Same posts, scope and fitness-brand
rule as scripts/direct_effect.py. Writes models/prediction_check.json.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.direct_effect import Post, effects_by_creator, prior, settled, shrink  # noqa: E402
from ml.prediction_check import History, predict, score  # noqa: E402
from scripts.direct_effect import (FITNESS_CATS, FITNESS_CREATOR_CATEGORIES, QUERIES, WINDOW,  # noqa: E402
                                   database_url, read_csv)

METHODS = ("ours", "last_post", "all_time", "no_creator")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-days", type=int, default=120)
    ap.add_argument("--recent-days", type=int, default=90)
    args = ap.parse_args()

    cur = psycopg2.connect(database_url()).cursor()
    today = date.today()
    posts: list[Post] = []
    for platform, sql in QUERIES.items():
        cur.execute(sql)
        for cid, pid, d, e1, e2, sp, fmt in cur.fetchall():
            day = d.date() if isinstance(d, datetime) else d
            posts.append(Post(cid, platform, pid, day, float(e1) + float(e2), bool(sp), fmt))
    posts = settled(posts, today)

    cur.execute("select creator_id::text, name, category from creators")
    creators = {cid: (name, cat) for cid, name, cat in cur.fetchall()}
    overrides = {r["name"].strip().lower(): r["include"].strip().lower()
                 for r in read_csv(ROOT / "data" / "creator_scope_overrides.csv") if r.get("name")}

    def in_scope(cid: str) -> bool:
        ov = overrides.get((creators.get(cid, ("", ""))[0] or "").strip().lower())
        if ov is not None:
            return ov in ("yes", "true", "1")
        return creators.get(cid, ("", "other"))[1] in FITNESS_CREATOR_CATEGORIES

    posts = [p for p in posts if in_scope(p.creator)]
    cur.execute("select e.content_id::text, b.category from creator_sponsorship_events e "
                "left join brands b on b.brand_id = e.brand_id")
    db_cat = dict(cur.fetchall())
    labels = {r["content_id"]: r["fitness"].strip().lower() for r in read_csv(ROOT / "data" / "event_brand_labels.csv")}

    def fitness(p: Post) -> bool:
        if p.post_id in labels:
            return labels[p.post_id] == "yes"
        return db_cat.get(p.post_id) in FITNESS_CATS

    start, end = today - timedelta(days=14 + args.test_days), today - timedelta(days=14)
    hist: dict[tuple[str, str], History] = {}
    by_cp: dict[tuple[str, str], list[Post]] = {}
    for p in posts:
        by_cp.setdefault((p.creator, p.platform), []).append(p)
    for k, v in by_cp.items():
        hist[k] = History.of(v)
    # "no creator" baseline: platform+format mean of ordinary posts before the test period
    pool: dict[tuple[str, str], list[float]] = {}
    for p in posts:
        if not p.sponsored and p.day < start:
            pool.setdefault((p.platform, p.fmt), []).append(math.log(p.engagement + 1))
    pool_mean = {k: statistics.mean(v) for k, v in pool.items() if len(v) >= 20}

    def row(p: Post) -> dict:
        r = {"creator": p.creator, "platform": p.platform, "actual": math.log(max(p.engagement, 0) + 1)}
        r.update(predict(hist[(p.creator, p.platform)], p.day, p.fmt, args.recent_days))
        if (p.platform, p.fmt) in pool_mean:
            r["no_creator"] = pool_mean[(p.platform, p.fmt)]
        return r

    # ---- A1: ordinary posts in the test period
    a1 = [row(p) for p in posts if not p.sponsored and start <= p.day < end]
    a1 = [r for r in a1 if "ours" in r]                          # same posts for every method
    res = {"test_period": [start.isoformat(), end.isoformat()], "recent_days": args.recent_days, "A1": {}, "A2": {}}
    print(f"=== A1: normal engagement, ordinary posts {start}..{end} (log scale) ===")
    print(f"  {'method':11s} {'posts':>6s} {'MAE':>6s} {'median':>7s} {'bias':>7s} {'rank corr (posts)':>18s} {'rank corr (creators)':>21s}")
    for m in METHODS:
        s = score(a1, m)
        res["A1"][m] = s
        if s["n_posts"]:
            print(f"  {m:11s} {s['n_posts']:6d} {s['mae_log']:6.3f} {s['median_abs_err_log']:7.3f} {s['mean_bias_log']:+7.3f} "
                  f"{s['spearman_posts']:18.3f} {s['spearman_creators']:15.3f} (n={s['n_creators_ranked']})")
    for k in ("youtube", "instagram"):
        s = score([r for r in a1 if r["platform"] == k], "ours")
        res["A1"][f"ours_{k}"] = s
        if s["n_posts"]:
            print(f"  ours, {k:9s} {s['n_posts']:5d} posts  MAE {s['mae_log']:.3f}  creators rank corr "
                  f"{s['spearman_creators']:.3f}")
    resid = [r["actual"] - r["ours"] for r in a1]
    sd = statistics.pstdev(resid) if len(resid) > 1 else float("nan")

    # ---- A2: sponsored fitness posts in the test period, scores from before it
    before = [p for p in posts if p.day < start]
    eff = effects_by_creator([p for p in before if p.sponsored and fitness(p)], before, WINDOW)
    scores, pr = shrink(eff), (prior(eff) if eff else {"score": 0.0})
    a2 = []
    for p in posts:
        if p.sponsored and fitness(p) and start <= p.day < end:
            r = row(p)
            if "ours" not in r:
                continue
            s = scores.get(p.creator)
            r["basis"] = "measured" if s else "prior"
            r["no_effect"] = r["ours"]
            r["with_effect"] = r["ours"] + (s["score"] if s else pr["score"])
            a2.append(r)
    print(f"\n=== A2: sponsored fitness posts in the test period (direct-effect scores from before {start}) ===")
    print(f"  {len(a2)} posts ({sum(r['basis'] == 'measured' for r in a2)} with a measured creator score, "
          f"rest on the prior {pr['score']:+.3f})")
    for m in ("no_effect", "with_effect"):
        s = score(a2, m)
        res["A2"][m] = s
        if s["n_posts"]:
            print(f"  {m:11s} MAE {s['mae_log']:.3f}  bias {s['mean_bias_log']:+.3f}  rank corr posts {s['spearman_posts']:.3f}  "
                  f"creators {s['spearman_creators']:.3f} (n={s['n_creators_ranked']})")
    if a2 and sd == sd:
        z = 1.2816
        cover = sum(abs(r["actual"] - r["with_effect"]) <= z * sd for r in a2) / len(a2)
        bias = statistics.mean(r["actual"] - r["with_effect"] for r in a2)
        res["A2"]["coverage_80"] = cover
        res["A2"]["mean_bias"] = bias
        print(f"  80% interval (+-{z * sd:.2f} log) covers {cover:.0%} of real sponsored posts "
              f"(target about 80%); mean bias {bias:+.3f}")

    out = ROOT / "models" / "prediction_check.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=2, default=str))
    print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
