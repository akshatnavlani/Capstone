"""Cross-platform lag detection + Granger causality on real data
(PendingWork S1, steps 2-3). Read-only on the database; writes a local JSON.

For each creator, builds regular time series of activity on each platform over
the period both series cover, then tests pairs:

  yt_posts -> yt_comments    positive control: comments MUST follow videos. If
                             this is not detected the method is broken.
  yt_posts -> reddit_posts   the 12-24h cross-platform hypothesis (hour-level
                             bins; Reddit rows are posts mentioning the creator)
  ig_posts -> reddit_posts   day-level only: Instagram dates carry no time of day
  yt_posts -> ig_posts       day-level only

Lag in bins; positive = the second series trails the first. Statistical
significance at this sample size is suggestive, not conclusive. Granger is
skipped (with a message) if scipy is not installed.

Usage:  python scripts/run_temporal_lag.py [--out temporal_lag.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.temporal.lag import pooled_lag_test  # noqa: E402
from ml.temporal.series import bin_counts, to_epoch_hours  # noqa: E402

SERIES_SQL = {
    "yt_posts": "select creator_id, published_at from youtube_videos where creator_id is not null and published_at is not null",
    "yt_comments": """select v.creator_id, c.published_at from youtube_comments c
                      join youtube_videos v on v.video_id = c.video_id
                      where v.creator_id is not null and c.published_at is not null""",
    "reddit_posts": "select creator_id, posted_at from reddit_posts where creator_id is not null and posted_at is not null",
    "ig_posts": "select creator_id, posted_at from instagram_posts where creator_id is not null and posted_at is not null",
}

# (cause, effect, bin_hours, max_lag in bins)
PAIRS = [
    ("yt_posts", "yt_comments", 12, 4),
    ("yt_posts", "reddit_posts", 12, 4),
    ("ig_posts", "reddit_posts", 24, 3),
    ("yt_posts", "ig_posts", 24, 3),
]
MIN_EVENTS = 10   # per series, inside the shared window
MIN_BINS = 20


def database_url() -> str:
    import os

    url = os.environ.get("DATABASE_URL")
    if not url:
        env = (Path(__file__).resolve().parent.parent / "backend" / ".env").read_text(encoding="utf-8")
        url = re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    return url.replace("postgresql+psycopg2://", "postgresql://")


def load_events() -> dict[str, dict[str, np.ndarray]]:
    conn = psycopg2.connect(database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    events: dict[str, dict[str, list]] = {name: defaultdict(list) for name in SERIES_SQL}
    for name, sql in SERIES_SQL.items():
        cur.execute(sql)
        for cid, ts in cur.fetchall():
            events[name][str(cid)].append(ts)
    conn.close()
    return {name: {cid: to_epoch_hours(v) for cid, v in d.items()} for name, d in events.items()}


def build_pair_series(cause_h: np.ndarray, effect_h: np.ndarray, bin_hours: float):
    """Series over the window both platforms cover, or None if too thin."""
    start = max(cause_h.min(), effect_h.min())
    end = min(cause_h.max(), effect_h.max())
    if end <= start:
        return None
    start = np.floor(start / bin_hours) * bin_hours
    x = bin_counts(cause_h, start, end, bin_hours)
    y = bin_counts(effect_h, start, end, bin_hours)
    if len(x) < MIN_BINS or x.sum() < MIN_EVENTS or y.sum() < MIN_EVENTS:
        return None
    return x, y


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="temporal_lag.json")
    ap.add_argument("--n-perm", type=int, default=500)
    args = ap.parse_args()

    have_granger = True
    try:
        from ml.temporal.granger import best_lag_pvalue, fisher_combine, granger_pvalues
    except Exception:  # scipy missing
        have_granger = False
        print("note: scipy not available, skipping Granger (pip install scipy)\n")

    events = load_events()
    report = []
    for cause, effect, bin_hours, max_lag in PAIRS:
        creators = set(events[cause]) & set(events[effect])
        pairs, granger_p = [], []
        for cid in creators:
            built = build_pair_series(events[cause][cid], events[effect][cid], bin_hours)
            if built is None:
                continue
            pairs.append(built)
            if have_granger:
                pv = granger_pvalues(built[0], built[1], max_lag=max_lag)
                if pv:
                    granger_p.append(best_lag_pvalue(pv)[1])

        entry = {"cause": cause, "effect": effect, "bin_hours": bin_hours,
                 "creators_with_both": len(creators), "creators_usable": len(pairs)}
        print(f"== {cause} -> {effect}  (bins of {bin_hours}h, +/-{max_lag} bins)")
        print(f"   creators with both: {len(creators)}, usable (>= {MIN_EVENTS} events, >= {MIN_BINS} bins): {len(pairs)}")
        if pairs:
            r = pooled_lag_test(pairs, max_lag=max_lag, n_perm=args.n_perm)
            entry.update({"best_lag_bins": r.best_lag, "best_lag_hours": r.best_lag * bin_hours,
                          "best_corr": round(r.best_corr, 4), "lag_p_value": round(r.p_value, 4),
                          "profile": {int(l): (None if np.isnan(c) else round(float(c), 4)) for l, c in zip(r.lags, r.profile)}})
            print(f"   lag: best {r.best_lag} bins = {r.best_lag * bin_hours}h, corr {r.best_corr:.3f}, p = {r.p_value:.3f}")
        else:
            print("   not enough data to test")
        if granger_p:
            entry["granger_creators"] = len(granger_p)
            entry["granger_combined_p"] = round(fisher_combine(granger_p), 6)
            print(f"   Granger: {len(granger_p)} creators testable, combined p = {entry['granger_combined_p']}")
        elif have_granger:
            print("   Granger: no creator had a long enough series")
        report.append(entry)
        print()

    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
