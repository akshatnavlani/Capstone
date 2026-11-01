"""Cross-platform posting-gap test. READ ONLY on the database; writes models/cross_platform_gap.json.

    python scripts/run_crossplatform_gap.py [--placebo 500] [--out models/cross_platform_gap.json]

QUESTION (Shimona's definition of lag): when a creator posts around the same time on YouTube and Instagram, with a gap between them (YouTube first, Instagram 12 h later ...),
does the size of the gap change how the audience reacts?

METHOD. Within each creator, every YouTube video (only those older than 30 days, so counts have settled) and every Instagram post with a like count gets a percentile
among that creator's OWN items of the same kind (long video / Short / Instagram post), so a creator is compared with themselves, never with a bigger creator.
An item is "paired" when the creator has an item on the other platform within 48 h; the pair gets its gap (hours, Instagram time minus YouTube time) and an order.
Effect for a gap group = the creator's mean percentile of paired items in the group minus the same creator's mean percentile of UNPAIRED items, averaged over creators
(95% interval by resampling creators). Creators need >= 8 items of that kind and both groups.
PLACEBO. The same test after moving every Instagram post by a random 7-60 days (hour of day kept) and re-deciding who is paired; the percentiles stay with the posts.
Nonzero placebo effect = pairing is confounded with the creator's posting rhythm. p = share of placebo runs with an effect at least as large as the real one.
LIMITS. Final counts, not the first 12-24 h (growth readings exist only since 11 Oct; those pairs are too few yet). Association within a creator, not proof of cause: a big
announcement is posted everywhere and is popular for its own reasons; the placebo removes posting-rhythm confounding only.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
V = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"
BINS = [("0-6 h", 0, 6), ("6-12 h", 6, 12), ("12-24 h", 12, 24), ("24-48 h", 24, 48)]
MIN_ITEMS = 8


def pct_within(values):
    """percentile (0..1, ties averaged) of each value among the list."""
    v = np.asarray(values, float)
    order = v.argsort().argsort()
    ranks = np.empty(len(v))
    for x in np.unique(v):
        m = v == x
        ranks[m] = order[m].mean()
    return ranks / max(len(v) - 1, 1)


def load():
    import psycopg2
    from dotenv import dotenv_values

    conn = psycopg2.connect(dotenv_values(ROOT / ".env")["DATABASE_URL"], connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute(f"select creator_id::text, extract(epoch from published_at)/3600.0, coalesce(duration_seconds,0)<=60, view_count from youtube_videos where creator_id in {V} and published_at < now() - interval '30 days' and view_count is not null and view_count > 0")
    yt = defaultdict(lambda: defaultdict(list))
    for c, t, short, views in cur.fetchall():
        yt[c]["short" if short else "long"].append((float(t), np.log1p(float(views))))
    cur.execute(f"select creator_id::text, extract(epoch from posted_at)/3600.0, like_count from instagram_posts where creator_id in {V} and posted_at is not null and like_count is not null and like_count >= 0")
    ig = defaultdict(list)
    for c, t, likes in cur.fetchall():
        ig[c].append((float(t), np.log1p(float(likes))))
    conn.close()
    return yt, ig


def items(rows):
    """rows [(t, value)] -> arrays (t, percentile among this list)."""
    t = np.array([r[0] for r in rows])
    return t, pct_within([r[1] for r in rows])


def effects(yt, ig, shift_rng=None):
    """Return {side: {group: [per-creator effect]}} for side in ig (Instagram posts) and yt_long / yt_short."""
    out = defaultdict(lambda: defaultdict(list))
    for c in ig:
        if len(ig[c]) < MIN_ITEMS:
            continue
        ti, pi = items(ig[c])
        if shift_rng is not None:
            sign = shift_rng.choice([-1.0, 1.0], size=len(ti))
            ti = ti + sign * shift_rng.uniform(7 * 24, 60 * 24, size=len(ti))
        for kind in ("long", "short"):
            rows = yt.get(c, {}).get(kind, [])
            if len(rows) < MIN_ITEMS:
                continue
            ty, py = items(rows)
            gap_ig = ti[:, None] - ty[None, :]           # Instagram time minus YouTube time, every pair
            near_ig = np.abs(gap_ig) <= 48
            nearest_ig = np.where(near_ig, np.abs(gap_ig), np.inf)
            has_pair_ig = near_ig.any(axis=1)
            has_pair_yt = near_ig.any(axis=0)
            # Instagram posts: group by their smallest absolute gap and the order for that nearest video
            j = nearest_ig.argmin(axis=1)
            g = gap_ig[np.arange(len(ti)), j]
            groups_ig = {}
            for name, lo, hi in BINS:
                groups_ig[name] = has_pair_ig & (np.abs(g) >= lo) & (np.abs(g) < hi)
            groups_ig["YouTube first (gap 0-48 h)"] = has_pair_ig & (g > 0)
            groups_ig["Instagram first (gap 0-48 h)"] = has_pair_ig & (g < 0)
            groups_ig["any pair within 48 h"] = has_pair_ig
            unpaired = ~has_pair_ig
            if unpaired.sum() >= 3:
                for name, m in groups_ig.items():
                    if m.sum() >= 2:
                        out[f"instagram_post_vs_{kind}_video"][name].append(float(pi[m].mean() - pi[unpaired].mean()))
            # YouTube videos: group by their nearest Instagram post
            i = nearest_ig.argmin(axis=0)
            gy = gap_ig[i, np.arange(len(ty))]
            unpaired_y = ~has_pair_yt
            if unpaired_y.sum() >= 3:
                groups_y = {name: has_pair_yt & (np.abs(gy) >= lo) & (np.abs(gy) < hi) for name, lo, hi in BINS}
                groups_y["YouTube first (gap 0-48 h)"] = has_pair_yt & (gy > 0)
                groups_y["Instagram first (gap 0-48 h)"] = has_pair_yt & (gy < 0)
                groups_y["any pair within 48 h"] = has_pair_yt
                for name, m in groups_y.items():
                    if m.sum() >= 2:
                        out[f"{kind}_video_vs_instagram_post"][name].append(float(py[m].mean() - py[unpaired_y].mean()))
    return out


def mean_ci(vals, rng, reps=2000):
    v = np.asarray(vals)
    if len(v) < 5:
        return None
    boots = [rng.choice(v, len(v)).mean() for _ in range(reps)]
    return float(v.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placebo", type=int, default=500)
    ap.add_argument("--out", default=str(ROOT / "models" / "cross_platform_gap.json"))
    args = ap.parse_args()
    yt, ig = load()
    rng = np.random.default_rng(11)
    real = effects(yt, ig)
    plac = [effects(yt, ig, np.random.default_rng(1000 + k)) for k in range(args.placebo)]
    res = []
    for side, groups in real.items():
        for name, vals in groups.items():
            ci = mean_ci(vals, rng)
            if ci is None:
                continue
            pl = [float(np.mean(p[side][name])) for p in plac if len(p.get(side, {}).get(name, [])) >= 5]
            p_val = (1 + sum(x >= ci[0] for x in pl)) / (1 + len(pl)) if pl else None
            row = {"side": side, "group": name, "creators": len(vals), "effect": round(ci[0], 3), "ci95": [round(ci[1], 3), round(ci[2], 3)],
                   "placebo_mean": round(float(np.mean(pl)), 3) if pl else None, "p_one_sided_vs_placebo": round(p_val, 4) if p_val is not None else None}
            res.append(row)
            print(f"{side:34s} {name:30s} creators {row['creators']:3d}  effect {row['effect']:+.3f} {row['ci95']}  placebo {row['placebo_mean']}  p {row['p_one_sided_vs_placebo']}")
    n_pairs = {}
    for c in ig:
        for kind in ("long", "short"):
            rows = yt.get(c, {}).get(kind, [])
            if rows and ig[c]:
                ty = np.array([r[0] for r in rows])
                n_pairs[kind] = n_pairs.get(kind, 0) + int(sum((np.abs(t - ty) <= 48).any() for t, _ in ig[c]))
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "unit": "difference in within-creator percentile (0-1) of paired minus unpaired items; 0.05 = five percentile points",
           "instagram_posts_with_a_video_within_48h": n_pairs, "placebo_runs": args.placebo, "results": res,
           "limits": "final counts, not first 12-24 h; association within a creator; placebo removes posting-rhythm confounding only; Instagram counts are read-time snapshots."}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("pairs", n_pairs, "saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
