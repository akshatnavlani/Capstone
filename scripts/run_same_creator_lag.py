"""Same-creator cross-platform performance lag on real data (PendingWork S1). READ ONLY;
writes models/same_creator_lag.json.

    python scripts\\run_same_creator_lag.py

Question (the brand-facing one): for a creator who is on both YouTube and Instagram, when they do
better than usual on one platform, do they do better than usual on the other a day later?

Performance of a post = its comments relative to the creator's own typical level on that platform,
after removing the effect of the post's age (ml/temporal/performance_lag.py). Comments are used
because they are recorded for far more Instagram posts than likes are. Positive lag = the second
platform trails the first. Day resolution: most Instagram posts carry no time of day.

Limits, stated up front: only creators with enough measured posts on BOTH platforms can be used,
the Instagram side is the bottleneck, and the database holds one snapshot per post (no growth curve),
so this measures day-to-day performance, not follower growth.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIN_POSTS = 6


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    from sqlalchemy import create_engine, text

    from ml.temporal.performance_lag import daily_series, performance_lag_test, performance_scores

    with create_engine(url).connect() as c:
        q = lambda sql: c.execute(text(sql)).all()
        names = {r[0]: r[1] for r in q("select creator_id::text, name from creators")}
        yt = q("""select creator_id::text, published_at, comment_count, coalesce(fetched_at, now()) from youtube_videos
                  where creator_id is not null and published_at is not null and comment_count is not null""")
        ig = q("""select creator_id::text, posted_at, comment_count, coalesce(fetched_at, now()) from instagram_posts
                  where creator_id is not null and posted_at is not null and comment_count is not null""")

    def per_creator(rows):
        by: dict[str, list] = {}
        for cid, ts, cm, fetched in rows:
            by.setdefault(cid, []).append((ts, cm, fetched))
        out = {}
        for cid, items in by.items():
            days = np.array([int(t.timestamp() // 86400) for t, _, _ in items])
            age = np.array([(f - t).total_seconds() / 86400 for t, _, f in items])
            z = performance_scores([cm for _, cm, _ in items], age, MIN_POSTS)
            if z is not None:
                out[cid] = daily_series(days, z)
        return out

    yts, igs = per_creator(yt), per_creator(ig)
    both = [cid for cid in yts if cid in igs]
    print(f"creators with enough measured comments (>= {MIN_POSTS} posts) on YouTube: {len(yts)}, Instagram: {len(igs)}, BOTH: {len(both)}")
    for cid in both:
        print(f"   {names.get(cid, cid)[:30]:30s} YouTube days {len(yts[cid]):3d} | Instagram days {len(igs[cid]):3d}")

    res = performance_lag_test([(yts[c], igs[c]) for c in both], lags=range(-3, 4), n_placebo=3000, seed=0)
    print("\nLAG PROFILE: YouTube performance on day d vs Instagram performance on day d + lag")
    print("   (positive lag = Instagram trails YouTube; negative = YouTube trails Instagram)")
    print(f"   {'lag':>4s} {'pairs':>6s} {'corr':>7s} {'placebo p':>10s}   detectable |corr| ~")
    for k, n, r, p in zip(res.lags, res.n_pairs, res.corr, res.p_values):
        det = 1.96 / np.sqrt(n) if n else float("nan")
        mark = "  <- the 24h question" if k == 1 else ""
        print(f"   {k:4d} {n:6d} {r:7.3f} {p:10.3f}   {det:.2f}{mark}")
    print("   the lag-1 row is the pre-specified hypothesis; the other lags are exploratory (7 lags tested, so a single p near 0.05 is not evidence)")

    (ROOT / "models" / "same_creator_lag.json").write_text(json.dumps({
        "creators": [names.get(c, c) for c in both], "lags": res.lags, "pairs": res.n_pairs,
        "corr": [None if np.isnan(x) else x for x in res.corr], "p": res.p_values, "min_posts": MIN_POSTS}, indent=2), encoding="utf-8")
    print("\nsaved models/same_creator_lag.json")


if __name__ == "__main__":
    main()
