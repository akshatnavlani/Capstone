"""YouTube vs Instagram for the SAME creator and the SAME moment, plus Granger causality. READ ONLY on the database; writes models/platform_pairs.json.

    python scripts/run_platform_pairs.py [--window 24] [--placebo 500] [--out models/platform_pairs.json]

SHIMONA'S IDEA (29 Oct 2026): one creator is on both platforms. When they post the same thing within 24 h, Instagram may get more reaction than YouTube, or YouTube more, or both
the same. A brand should see BOTH, not judge a creator from one platform ("weak on Instagram, great on YouTube").

PART 1, PAIRED COMPARISON. A pair = a YouTube video and an Instagram post of the same creator published within --window hours of each other (counts settled: at least 14 days old).
Raw counts cannot be compared across platforms, so each post is measured against the creator's OWN usual on that platform: reaction = log((likes+comments+1)/(median of the
creator's own items on that platform + 1)); YouTube items are compared with the creator's videos of the same kind (Short or long). Difference = Instagram reaction - YouTube
reaction (0.25 is about 28% better than usual relative to the other platform). Per creator: pairs, median difference, winner (Instagram / YouTube / balanced within +-0.25), and
'not enough pairs' below 3. text_overlap = share of the shorter text's words also in the other (YouTube title+description start vs Instagram caption): a rough check that the two
posts are about the same thing; pairs with overlap >= 0.15 are reported separately.
PART 2, GRANGER CAUSALITY (the project document's cross-platform temporal test). Per creator, daily series over the last 365 days: Y = YouTube comments arriving per day (log1p,
all the creator's videos), X = Instagram posts per day. Does X lagged 1-3 days help predict Y beyond Y's own 1-3 lags (and the other way round)? Pooled over creators with the
creator's own mean removed; F statistic; p from 500 placebo runs in which X is circularly shifted by a random 10-300 days within each creator (keeps its rhythm, breaks the link).
A second variant uses only comments arriving on videos older than 72 h, which removes the direct effect of an upload.
LIMITS: pairs within the window may not always be the same content (overlap check given); Instagram counts are read-time snapshots; comments were collected newest-first per video;
Granger is prediction, not cause; only 5,633 of 30,435 Instagram comments carry a time, so Instagram comment series are not used.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
V = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"
BALANCED = 0.25
MIN_PAIRS = 3
CROSSPOST_SHARE = 0.6   # a creator whose posts are at least this share cross-posted on BOTH platforms has no unpaired baseline and does not need one
WORD = re.compile(r"[a-z0-9]{3,}")


def words(t):
    return set(WORD.findall((t or "").lower()))


def overlap(a, b):
    wa, wb = words(a), words(b)
    return len(wa & wb) / max(min(len(wa), len(wb)), 1) if wa and wb else 0.0


def load():
    import psycopg2
    from dotenv import dotenv_values

    conn = psycopg2.connect(dotenv_values(ROOT / ".env")["DATABASE_URL"], connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute(f"select c.creator_id::text, c.name from creators c where c.creator_id in {V}")
    names = dict(cur.fetchall())
    cur.execute(f"select creator_id::text, video_id, extract(epoch from published_at)/3600.0, coalesce(duration_seconds,0)<=60, coalesce(like_count,0)+coalesce(comment_count,0), title, left(coalesce(description,''),400) from youtube_videos where creator_id in {V} and published_at < now()-interval '14 days'")
    yt = defaultdict(list)
    for c, vid, t, short, react, title, desc in cur.fetchall():
        yt[c].append({"id": vid, "t": float(t), "short": bool(short), "react": float(react), "text": f"{title or ''} {desc}"})
    cur.execute(f"select creator_id::text, post_id, extract(epoch from posted_at)/3600.0, coalesce(like_count,0)+coalesce(comment_count,0), caption from instagram_posts where creator_id in {V} and posted_at is not null and like_count is not null and like_count>=0 and posted_at < now()-interval '14 days'")
    ig = defaultdict(list)
    for c, pid, t, react, cap in cur.fetchall():
        ig[c].append({"id": pid, "t": float(t), "react": float(react), "text": cap or ""})
    cur.execute(f"select v.creator_id::text, (m.published_at at time zone 'utc')::date, (m.published_at - v.published_at) > interval '72 hours', count(*) from youtube_comments m join youtube_videos v using(video_id) where v.creator_id in {V} and m.published_at > now() - interval '400 days' group by 1,2,3")
    com = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for c, d, old, n in cur.fetchall():
        com[c][d][1 if old else 0] += int(n)
    cur.execute(f"select creator_id::text, (posted_at at time zone 'utc')::date from instagram_posts where creator_id in {V} and posted_at is not null")
    igd = defaultdict(lambda: defaultdict(int))
    for c, d in cur.fetchall():
        igd[c][d] += 1
    conn.close()
    return names, yt, ig, com, igd


def paired(names, yt, ig, window):
    """pairs plus a promotion-adjusted difference: an Instagram post that goes with a video, and a video that goes with an Instagram post, are both above the creator's usual just
    for being a cross-promoted post, so each side is also measured against the creator's UNPAIRED posts on that platform (needs >= 3 of them)."""
    rows = []
    for c in ig:
        if len(ig[c]) < 5:
            continue
        ig_med = float(np.median([p["react"] for p in ig[c]]))
        med = {k: float(np.median([v["react"] for v in yt[c] if v["short"] == (k == "short")])) for k in ("short", "long") if sum(v["short"] == (k == "short") for v in yt.get(c, [])) >= 5}
        i_r = {p["id"]: float(np.log((p["react"] + 1) / (ig_med + 1))) for p in ig[c]}
        y_r = {v["id"]: float(np.log((v["react"] + 1) / (med["short" if v["short"] else "long"] + 1))) for v in yt.get(c, []) if ("short" if v["short"] else "long") in med}
        pr = [(p, v) for p in ig[c] for v in yt.get(c, []) if v["id"] in y_r and abs(p["t"] - v["t"]) <= window]
        if not pr:
            continue
        pi, pv = {p["id"] for p, _ in pr}, {v["id"] for _, v in pr}
        un_i = [r for k, r in i_r.items() if k not in pi]
        un_y = [r for k, r in y_r.items() if k not in pv]
        # baseline per side: the creator's unpaired posts when there are enough; if most of the creator's posts on that platform ARE cross-posted there are no unpaired ones
        # and none are needed, because the creator's usual already is the cross-posted level (relative reactions are measured against the median of all posts, so baseline 0)
        share_i, share_y = len(pi) / max(len(i_r), 1), len(pv) / max(len(y_r), 1)
        base_i = float(np.median(un_i)) if len(un_i) >= 3 else (0.0 if share_i >= CROSSPOST_SHARE else None)
        base_y = float(np.median(un_y)) if len(un_y) >= 3 else (0.0 if share_y >= CROSSPOST_SHARE else None)
        how = "adjusted for promotion" if len(un_i) >= 3 and len(un_y) >= 3 else "partly plain (most of this creator's Instagram posts are cross-posted)"
        for p, v in pr:
            row = {"creator_id": c, "name": names.get(c), "youtube_video": v["id"], "instagram_post": p["id"], "gap_hours": round(p["t"] - v["t"], 1),
                   "youtube_vs_usual": round(y_r[v["id"]], 3), "instagram_vs_usual": round(i_r[p["id"]], 3), "difference": round(i_r[p["id"]] - y_r[v["id"]], 3),
                   "text_overlap": round(overlap(v["text"], p["text"]), 3), "adjusted_difference": None, "usable_difference": None, "basis": None}
            if base_i is not None and base_y is not None:
                row["adjusted_difference"] = round((i_r[p["id"]] - base_i) - (y_r[v["id"]] - base_y), 3)
                row["usable_difference"], row["basis"] = row["adjusted_difference"], how
            rows.append(row)
    return rows


def summarise(rows, calibration=0.0):
    by = defaultdict(list)
    for r in rows:
        by[r["creator_id"]].append(r)
    out = []
    for c, rs in by.items():
        adj = np.array([r["usable_difference"] - calibration for r in rs if r["usable_difference"] is not None])   # minus the placebo level: unrelated posts also favour Instagram by that much
        raw = np.array([r["difference"] for r in rs])
        if len(adj) < MIN_PAIRS:
            winner = "not enough pairs"
        else:
            m = float(np.median(adj))
            winner = "Instagram" if m > BALANCED else "YouTube" if m < -BALANCED else "balanced"
        out.append({"creator_id": c, "name": rs[0]["name"], "pairs": len(rs), "pairs_with_adjustment": int(len(adj)), "median_difference_raw": round(float(np.median(raw)), 3),
                    "median_difference_adjusted": round(float(np.median(adj)), 3) if len(adj) else None, "share_instagram_better_adjusted": round(float((adj > 0).mean()), 2) if len(adj) else None, "basis": sorted({r["basis"] for r in rs if r["basis"]}),
                    "youtube_vs_usual_median": round(float(np.median([r["youtube_vs_usual"] for r in rs])), 3), "instagram_vs_usual_median": round(float(np.median([r["instagram_vs_usual"] for r in rs])), 3), "stronger_platform": winner})
    return sorted(out, key=lambda x: -x["pairs"])


def build_series(com, igd, creators, old_only):
    end = datetime.now(timezone.utc).date()
    days = [end.fromordinal(end.toordinal() - k) for k in range(365, 0, -1)]
    S = {}
    for c in creators:
        if sum(igd[c].values()) < 5 or not com.get(c):
            continue
        y = np.array([np.log1p(com[c][d][1] if old_only else sum(com[c][d])) if d in com[c] else 0.0 for d in days])
        x = np.array([float(igd[c].get(d, 0)) for d in days])
        if y.std() > 0 and x.std() > 0:
            S[c] = (y, x)
    return S


def granger_f(S, lags=3, cause=1, shifts=None):
    """pooled F test: does series `cause` (0=y,1=x) lagged help predict the other, beyond its own lags; creator mean removed."""
    rss_r = rss_u = 0.0
    n_obs = 0
    for c, (y, x) in S.items():
        a, b = (y, x) if cause == 1 else (x, y)       # a = predicted series, b = predictor
        if shifts is not None:
            b = np.roll(b, int(shifts[c]))
        T = len(a)
        A = np.column_stack([a[lags - k - 1:T - k - 1] for k in range(lags)])
        B = np.column_stack([b[lags - k - 1:T - k - 1] for k in range(lags)])
        t = a[lags:]
        A = A - A.mean(0)
        B = B - B.mean(0)
        t = t - t.mean()
        for X, which in ((A, "r"), (np.column_stack([A, B]), "u")):
            beta, *_ = np.linalg.lstsq(X, t, rcond=None)
            rss = float(((t - X @ beta) ** 2).sum())
            if which == "r":
                rss_r += rss
            else:
                rss_u += rss
        n_obs += len(t)
    k_u = len(S) * 2 * lags
    return ((rss_r - rss_u) / (len(S) * lags)) / (rss_u / max(n_obs - k_u, 1))


def granger(S, placebo, seed):
    rng = np.random.default_rng(seed)
    res = {}
    for name, cause in (("Instagram posts -> YouTube comments", 1), ("YouTube comments -> Instagram posts", 0)):
        real = granger_f(S, cause=cause)
        null = [granger_f(S, cause=cause, shifts={c: rng.integers(10, 300) for c in S}) for _ in range(placebo)]
        res[name] = {"F": round(real, 3), "placebo_F_median": round(float(np.median(null)), 3), "p_value": round((1 + sum(f >= real for f in null)) / (1 + len(null)), 4)}
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--window", type=float, default=24.0)
    ap.add_argument("--placebo", type=int, default=500)
    ap.add_argument("--out", default=str(ROOT / "models" / "platform_pairs.json"))
    args = ap.parse_args()
    names, yt, ig, com, igd = load()
    rows = paired(names, yt, ig, args.window)
    # PLACEBO for the headline: the same comparison after moving every Instagram post by a random 7-60 days, so no post is a real partner of the video it is paired with.
    # If Instagram "wins" just as much there, the win is a difference between the two ways of counting reactions, not something about the matched posts.
    rng0 = np.random.default_rng(3)
    plac_med, plac_share = [], []
    for _ in range(min(args.placebo, 30)):
        ig_s = {c: [dict(p, t=p["t"] + rng0.choice([-1.0, 1.0]) * rng0.uniform(7 * 24, 60 * 24)) for p in ps] for c, ps in ig.items()}
        pr_rows = [r["usable_difference"] for r in paired(names, yt, ig_s, args.window) if r["usable_difference"] is not None]
        if len(pr_rows) >= 30:
            plac_med.append(float(np.median(pr_rows)))
            plac_share.append(float((np.array(pr_rows) > 0).mean()))
    placebo_out = {"runs": len(plac_med), "median_difference_placebo": round(float(np.mean(plac_med)), 3) if plac_med else None, "share_instagram_better_placebo": round(float(np.mean(plac_share)), 3) if plac_share else None}
    print("placebo (Instagram posts moved to other days):", placebo_out)
    calibration = placebo_out["median_difference_placebo"] or 0.0
    creators = summarise(rows, calibration)
    d = np.array([r["difference"] for r in rows]) if rows else np.array([0.0])
    da = np.array([r["usable_difference"] for r in rows if r["usable_difference"] is not None])
    if len(da):
        print(f"promotion-adjusted: {len(da)} pairs; median difference {np.median(da):+.2f}; Instagram better in {100 * (da > 0).mean():.0f}% (raw was {np.median(d):+.2f}, {100 * (d > 0).mean():.0f}%)")
    related = [r for r in rows if r["text_overlap"] >= 0.15]
    d_rel = np.array([r["difference"] for r in related]) if related else np.array([0.0])
    print(f"pairs within {args.window:.0f} h: {len(rows)} from {len(creators)} creators; with text overlap >= 0.15: {len(related)} from {len({r['creator_id'] for r in related})}")
    print(f"median difference (Instagram minus YouTube, vs each's usual): {np.median(d):+.2f}; Instagram better in {100 * (d > 0).mean():.0f}% of pairs")
    cnt = defaultdict(int)
    for c in creators:
        cnt[c["stronger_platform"]] += 1
    print("creators by stronger platform:", dict(cnt))
    gr = {}
    for label, old in (("all comments", False), ("comments on videos older than 72 h only", True)):
        S = build_series(com, igd, list(igd), old)
        gr[label] = {"creators": len(S), "tests": granger(S, args.placebo, 5)}
        print(f"Granger ({label}, {len(S)} creators):")
        for k, v in gr[label]["tests"].items():
            print(f"   {k}: F {v['F']} (placebo median {v['placebo_F_median']}), p {v['p_value']}")
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "window_hours": args.window,
           "pairs": len(rows), "creators_with_pairs": len(creators), "median_difference": round(float(np.median(d)), 3), "share_pairs_instagram_better": round(float((d > 0).mean()), 3),
           "adjusted_pairs": int(len(da)), "median_difference_adjusted": round(float(np.median(da)) - calibration, 3) if len(da) else None, "share_pairs_instagram_better_adjusted": round(float((da > 0).mean()), 3) if len(da) else None,
           "pairs_with_text_overlap": len(related), "median_difference_with_overlap": round(float(np.median(d_rel)), 3),
           "creators": creators, "pair_rows": rows, "placebo": placebo_out, "calibration_subtracted": calibration, "granger": gr,
           "limits": "pairs within the window may not always be the same content; Instagram counts are read-time snapshots; Granger is prediction not cause; Instagram comments mostly lack times"}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
