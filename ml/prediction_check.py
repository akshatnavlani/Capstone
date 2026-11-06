"""Out-of-time checks for the per-rupee ranking inputs (Track A, tasks A1-A2).

A1, normal engagement. For every ordinary post p in the test period, predict
log(engagement + 1) from the creator's posts BEFORE p only:
  ours       mean log engagement of ordinary posts of p's format in the previous
             `recent_days` (falls back to all formats), as in creator_value.csv
  last_post  the creator's most recent ordinary post of that format
  all_time   mean over all the creator's earlier ordinary posts of that format
  no_creator mean over every creator's earlier ordinary posts of that format on the
             platform (what you know without the creator's own history)

A2, sponsored posts. Direct-effect scores are estimated from sponsored posts
before the cutoff only; for each sponsored post after it the prediction is
ours + score (creator's own shrunken score, or the population prior).

Scoring: mean absolute error on the log scale, Spearman across posts, and
Spearman across creators (each creator's mean actual vs mean prediction; the
ranking use), plus interval coverage for A2.
"""

from __future__ import annotations

import math
import statistics
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, timedelta

from ml.direct_effect import Post


def _log(p: Post) -> float:
    return math.log(max(p.engagement, 0) + 1)


@dataclass
class History:
    """Ordinary posts of one creator on one platform, sorted by day."""
    days: list
    posts: list

    @classmethod
    def of(cls, posts: list[Post]) -> "History":
        ps = sorted((p for p in posts if not p.sponsored), key=lambda p: p.day)
        return cls([p.day for p in ps], ps)

    def before(self, day: date) -> list[Post]:
        return self.posts[:bisect_left(self.days, day)]


def predict(hist: History, day: date, fmt: str, recent_days: int = 90, min_posts: int = 3) -> dict:
    """Predictions for a post on `day` in format `fmt` from this creator's earlier ordinary posts."""
    prior = hist.before(day)
    same = [p for p in prior if p.fmt == fmt]
    recent = [p for p in same if p.day >= day - timedelta(days=recent_days)]
    if len(recent) < min_posts:
        recent = [p for p in prior if p.day >= day - timedelta(days=recent_days)]
    out = {}
    if len(recent) >= min_posts:
        out["ours"] = statistics.mean(_log(p) for p in recent)
    if same:
        out["last_post"] = _log(same[-1])
        out["all_time"] = statistics.mean(_log(p) for p in same)
    return out


def spearman(x: list[float], y: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    if len(x) < 3:
        return float("nan")
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def score(rows: list[dict], method: str, min_creator_posts: int = 3) -> dict:
    """rows: {creator, actual, <method>: prediction}. Rows without the method are skipped."""
    use = [r for r in rows if method in r]
    if not use:
        return {"n_posts": 0}
    err = [abs(r[method] - r["actual"]) for r in use]
    by_c: dict[str, list[dict]] = {}
    for r in use:
        by_c.setdefault(r["creator"], []).append(r)
    cs = [v for v in by_c.values() if len(v) >= min_creator_posts]
    return {"n_posts": len(use), "n_creators": len(by_c), "mae_log": statistics.mean(err),
            "mean_bias_log": statistics.mean(r["actual"] - r[method] for r in use),
            "median_abs_err_log": statistics.median(err),
            "spearman_posts": spearman([r[method] for r in use], [r["actual"] for r in use]),
            "spearman_creators": spearman([statistics.mean(r[method] for r in v) for v in cs],
                                          [statistics.mean(r["actual"] for r in v) for v in cs]),
            "n_creators_ranked": len(cs)}
