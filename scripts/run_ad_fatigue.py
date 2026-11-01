"""Ad fatigue: does a creator's ORGANIC content get less reaction when they have posted more sponsored videos recently? READ ONLY on the database; writes models/ad_fatigue.json.

    python scripts/run_ad_fatigue.py [--placebo 500] [--window 30] [--out models/ad_fatigue.json]

QUESTION (29 Oct 2026): a brand wants to know whether a creator's audience is saturated with ads. If it is, the creator's NON-sponsored videos should do worse in weeks that follow
many sponsored videos.
METHOD. Only YouTube videos older than 30 days (counts settled) of creators with >= 30 such videos and >= 5 sponsored ones. For every non-sponsored video: LOAD = number of the creator's
sponsored videos published in the previous --window days. Outcomes, each compared with the creator's own videos: (a) log views, (b) log of (likes + comments) per view. Both outcome and load
have the creator's own time trend removed (straight line over time), so a creator who slowly grows or fades does not fake an effect. Per creator: slope of outcome on load; summary = median over
creators (1 unit = one more sponsored video in the previous 30 days; x100 is roughly percent); 95% interval by resampling creators.
PLACEBO. The creator's sponsored dates are moved by a random 30 days or more (wrapping around their history) and everything is recomputed; this keeps how often and how clustered the creator
sponsors but breaks the link to the videos' outcomes. p = share of placebo medians at least as negative as the real one (one-sided: fatigue means a negative slope).
LIMITS: sponsored labels are rules (60-95% right for the weaker tiers, misses unknown); association within a creator, not proof of cause (a busy season raises both the ads and the reaction);
organic videos that were mislabelled as organic dilute the effect.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
V = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"
MIN_VIDEOS, MIN_SPONSORED = 30, 5


def load():
    import psycopg2
    from dotenv import dotenv_values

    conn = psycopg2.connect(dotenv_values(ROOT / ".env")["DATABASE_URL"], connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute(f"""select creator_id::text, extract(epoch from published_at)/86400.0, is_sponsored, view_count, like_count, comment_count from youtube_videos
                    where creator_id in {V} and published_at < now() - interval '30 days' and view_count > 0 and like_count is not null and comment_count is not null and coalesce(duration_seconds,0) > 60""")
    by = {}
    for c, t, sp, v, l, m in cur.fetchall():
        by.setdefault(c, []).append((float(t), bool(sp), float(v), float(l + m)))
    conn.close()
    out = {}
    for c, rows in by.items():
        rows.sort()
        a = np.array(rows, float)
        if len(a) >= MIN_VIDEOS and a[:, 1].sum() >= MIN_SPONSORED:
            out[c] = a
    return out


def detrend(y, t):
    A = np.column_stack([np.ones_like(t), t - t.mean()])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return y - A @ beta


def slopes(data, window, shift_rng=None):
    out = {"views": [], "reaction_rate": []}
    for c, a in data.items():
        t, sp = a[:, 0], a[:, 1] > 0
        st = t[sp]
        if shift_rng is not None:
            span = t.max() - t.min()
            if span <= 2 * window:
                continue
            st = t.min() + np.mod(st - t.min() + shift_rng.uniform(window, span - window), span)
            st = np.sort(st)
        org = ~sp
        to = t[org]
        # sponsored videos in (t - window, t); a sponsored date equal to t cannot happen for an organic video except through the placebo shift, where ties count as not-before
        load = np.searchsorted(st, to, side="left") - np.searchsorted(st, to - window, side="left")
        lres = detrend(load.astype(float), to)
        if lres.std() < 1e-9:
            continue
        for key, y in (("views", np.log(a[org, 2])), ("reaction_rate", np.log((a[org, 3] + 1) / (a[org, 2] + 1)))):
            r = detrend(y, to)
            out[key].append(float((lres * r).sum() / (lres * lres).sum()))
    return out


def ci(vals, rng, reps=2000):
    v = np.asarray(vals)
    boots = [np.median(rng.choice(v, len(v))) for _ in range(reps)]
    return float(np.median(v)), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placebo", type=int, default=500)
    ap.add_argument("--window", type=float, default=30.0)
    ap.add_argument("--out", default=str(ROOT / "models" / "ad_fatigue.json"))
    args = ap.parse_args()
    data = load()
    n_org = sum(int((a[:, 1] == 0).sum()) for a in data.values())
    print(f"{len(data)} creators; {n_org} organic videos analysed; window {args.window:.0f} days")
    real = slopes(data, args.window)
    rng = np.random.default_rng(5)
    plac = [slopes(data, args.window, np.random.default_rng(500 + k)) for k in range(args.placebo)]
    res = []
    labels = {"views": "views (log) per extra sponsored video in the previous 30 days", "reaction_rate": "like+comment rate per view (log) per extra sponsored video in the previous 30 days"}
    for key in ("views", "reaction_rate"):
        m, lo, hi = ci(real[key], rng)
        pm = [float(np.median(p[key])) for p in plac if len(p[key]) >= 20]
        p_val = (1 + sum(x <= m for x in pm)) / (1 + len(pm))
        share_neg = float(np.mean(np.array(real[key]) < 0))
        row = {"outcome": labels[key], "creators": len(real[key]), "median_slope": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)], "placebo_median": round(float(np.median(pm)), 4),
               "p_one_sided_fatigue": round(p_val, 4), "share_of_creators_with_negative_slope": round(share_neg, 3)}
        res.append(row)
        print(f"{labels[key][:62]:62s} creators {row['creators']}  median {m:+.4f} [{lo:+.4f}, {hi:+.4f}]  placebo {row['placebo_median']:+.4f}  p {p_val:.4f}  negative for {100 * share_neg:.0f}% of creators")
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "window_days": args.window, "creators": len(data), "organic_videos": n_org, "placebo_runs": args.placebo, "results": res,
           "limits": "sponsored labels are rules, misses unknown; association within a creator, not proof of cause; YouTube only"}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
