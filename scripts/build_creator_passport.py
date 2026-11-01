"""Creator Passport: one record per creator that gathers every analysis we have, plus the five novelty analyses built on 1 Nov 2026. READ ONLY on the database; writes models/creator_passport.json.

    python scripts/build_creator_passport.py [--out models/creator_passport.json]

Sections per creator (each carries its own sample size and says "not enough data" instead of guessing):
  platform_strength   YouTube vs Instagram against the creator's own usual (from models/platform_pairs.json)
  mood                comment sentiment per platform and the gap between them (models/temporal_sentiment.json + passport_stats.mood_gap)
  speed               share of the first week's views that arrive in the first 24 h on YouTube (2-hourly growth readings)
  sponsored           engagement of sponsored posts against the creator's own organic posts of the same format, per platform; buying signals and disclosure (models/promotion_behaviour.json)
  fatigue             sponsored posts in the last 30 days against the creator's usual rate
  network             links to other creators (collaboration/@mention and shared brand) and how many linked creators were sponsored in the last 30 days
  clash_events        brands this creator was sponsored by in the last 120 days, with category and evidence tier (the API filters these by the brief's category)
  predicted_instagram for creators with no Instagram data: a leave-one-out-tested estimate of their Instagram level from YouTube features (flagged unreliable if it does not beat size alone)
  evidence            the same A-D grade the recommendations use (backend/app/evidence.py)
The summary block holds the group-level result of each novelty analysis, with placebo or leave-one-out checks.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from passport_stats import matched_differences, mood_gap, placebo_pooled, pooled, prediction_report, _ridge_fit, _ridge_predict  # noqa: E402
from app.evidence import grade_evidence  # noqa: E402

DAY = 86400.0
SHORT_SECONDS = 180
YT_WINDOW, IG_WINDOW = 45.0, 90.0
IMMATURE_DAYS = 14
CLASH_DAYS = 120


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        m = re.search(r"^DATABASE_URL=(.+)$", (ROOT / ".env").read_text(encoding="utf-8"), re.M)
        url = m.group(1).strip().strip('"')
    return url.replace("postgresql+psycopg2://", "postgresql://")


def load(name: str):
    return json.loads((ROOT / "models" / name).read_text(encoding="utf-8"))


def sponsored_penalty(by_creator: dict[str, dict], window: float) -> tuple[dict[str, dict], dict]:
    """by_creator[c] = {"spons": [(day, fmt, y)], "organic": [(day, fmt, y)]}. Returns per-creator results and the pooled result with placebo."""
    per, medians, org, nspons = {}, [], {}, {}
    for c, d in by_creator.items():
        diffs = matched_differences(d["spons"], d["organic"], window)
        if len(diffs) >= 3:
            med = float(np.median(diffs))
            per[c] = {"sponsored_posts": len(d["spons"]), "matched": len(diffs), "median_log_difference": round(med, 3), "approx_percent": round(100 * (math.exp(med) - 1), 1), "enough": len(diffs) >= 5}
            medians.append(med)
        if len(d["spons"]) >= 3:
            org[c], nspons[c] = d["organic"], len(d["spons"])
    pool = pooled(medians)
    pool["placebo"] = placebo_pooled(org, nspons, window, runs=200)
    if pool["mean"] is not None:
        pool["approx_percent"] = round(100 * (math.exp(pool["mean"]) - 1), 1)
        pool["ci95_percent"] = [round(100 * (math.exp(x) - 1), 1) for x in pool["ci95"]]
    return per, pool


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "models" / "creator_passport.json"))
    args = ap.parse_args()
    conn = psycopg2.connect(database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    now = datetime.now(timezone.utc)
    now_d = now.timestamp() / DAY

    cur.execute("select creator_id::text, name, category, youtube_handle, instagram_handle from creators")
    creators = {r[0]: {"creator_id": r[0], "name": r[1], "category": r[2], "youtube_handle": r[3], "instagram_handle": r[4]} for r in cur.fetchall()}
    cur.execute("select creator_id::text, max(subscriber_count) from youtube_channels where creator_id is not null group by 1")
    subs = {c: s for c, s in cur.fetchall() if s}

    # ---- YouTube and Instagram posts ---------------------------------------------------------------------------------------------------------
    cur.execute("""select creator_id::text, video_id, extract(epoch from published_at), duration_seconds, view_count, like_count, comment_count, is_sponsored
                   from youtube_videos where creator_id is not null and published_at is not null and view_count is not null""")
    yt = defaultdict(list)
    for c, vid, ts, dur, views, likes, comments, sp in cur.fetchall():
        yt[c].append({"id": vid, "t": float(ts), "fmt": "short" if (dur or 0) <= SHORT_SECONDS else "long", "views": views, "likes": likes, "comments": comments, "sp": bool(sp)})
    cur.execute("""select creator_id::text, extract(epoch from posted_at), media_type, like_count, comment_count, (coalesce(is_sponsored,false) or coalesce(has_paid_partnership_label,false))
                   from instagram_posts where creator_id is not null and posted_at is not null""")
    ig = defaultdict(list)
    for c, ts, mt, likes, comments, sp in cur.fetchall():
        ig[c].append({"t": float(ts), "fmt": str(mt), "likes": likes, "comments": comments, "sp": bool(sp)})
    print(f"creators {len(creators)}; with YouTube videos {len(yt)}; with Instagram posts {len(ig)}", flush=True)

    # ---- sponsored response by platform --------------------------------------------------------------------------------------------------------
    def build(items, y_of, window_filter):
        by = {}
        for c, rows in items.items():
            sp, og = [], []
            for r in rows:
                y = y_of(r)
                if y is None or (now_d - r["t"] / DAY) < window_filter:
                    continue
                (sp if r["sp"] else og).append((r["t"] / DAY, r["fmt"], y))
            if sp and og:
                by[c] = {"spons": sp, "organic": og}
        return by

    yt_views_per, yt_views_pool = sponsored_penalty(build(yt, lambda r: math.log1p(r["views"]), IMMATURE_DAYS), YT_WINDOW)
    yt_likes_per, yt_likes_pool = sponsored_penalty(build(yt, lambda r: math.log1p(r["likes"]) if r["likes"] is not None else None, IMMATURE_DAYS), YT_WINDOW)
    ig_likes_per, ig_likes_pool = sponsored_penalty(build(ig, lambda r: math.log1p(r["likes"]) if r["likes"] is not None and r["likes"] >= 0 else None, 3), IG_WINDOW)
    print("sponsored response: YouTube views", yt_views_pool["creators"], "creators", yt_views_pool.get("approx_percent"), "| YouTube likes", yt_likes_pool.get("approx_percent"), "| Instagram likes", ig_likes_pool["creators"], "creators", ig_likes_pool.get("approx_percent"), flush=True)

    # ---- attention speed on YouTube -----------------------------------------------------------------------------------------------------------
    cur.execute("select post_id, extract(epoch from fetched_at), view_count from post_snapshots where platform='youtube' and view_count is not null order by post_id, fetched_at")
    reads = defaultdict(list)
    for pid, ts, v in cur.fetchall():
        reads[pid].append((float(ts), float(v)))
    pub = {v["id"]: (c, v["t"]) for c, vs in yt.items() for v in vs}
    speed_by = defaultdict(list)
    for pid, rs in reads.items():
        if pid not in pub:
            continue
        c, t0 = pub[pid]
        age = [((ts - t0) / 3600.0, v) for ts, v in rs]
        if not age or age[0][0] > 6 or age[0][0] < 0:
            continue
        late = [(a, v) for a, v in age if 150 <= a <= 175]
        before = [(a, v) for a, v in age if 16 <= a <= 24]
        after = [(a, v) for a, v in age if 24 < a <= 32]
        if not late or not before or not after:
            continue
        (a1, v1), (a2, v2) = before[-1], after[0]
        v24 = v1 + (v2 - v1) * (24 - a1) / (a2 - a1)
        total = late[-1][1]
        if total > 100:
            speed_by[c].append(max(0.0, min(1.0, v24 / total)))
    speed = {c: {"videos": len(v), "share_first_24h": round(float(np.median(v)), 3)} for c, v in speed_by.items() if len(v) >= 3}
    all_speed = [x for v in speed_by.values() for x in v]
    print(f"attention speed: {len(all_speed)} videos with a full first week, {len(speed)} creators with 3+", flush=True)

    # ---- sponsorship events: fatigue, clash ----------------------------------------------------------------------------------------------------
    cur.execute("""select e.creator_id::text, extract(epoch from e.posted_at), e.platform, e.sponsorship_evidence, b.name, b.category, e.brand_id::text, e.content_id
                   from creator_sponsorship_events e left join brands b on b.brand_id = e.brand_id where e.creator_id is not null and e.posted_at is not null""")
    ev = defaultdict(list)
    for c, ts, plat, tier, bname, bcat, bid, cid in cur.fetchall():
        ev[c].append({"t": float(ts), "platform": plat, "tier": tier, "brand": bname, "category": bcat, "brand_id": bid, "content": cid})
    fatigue = {}
    for c, es in ev.items():
        last30 = len({e["content"] for e in es if now_d - e["t"] / DAY <= 30})
        year = [e for e in es if 30 < now_d - e["t"] / DAY <= 395]
        usual = len({e["content"] for e in year}) / 12.0
        fatigue[c] = {"sponsored_last_30d": last30, "usual_per_30d": round(usual, 2), "above_usual": bool(last30 >= max(3, 2 * usual))}
    clash = {}
    for c, es in ev.items():
        recent = {}
        for e in sorted(es, key=lambda e: -e["t"]):
            if now_d - e["t"] / DAY > CLASH_DAYS or not e["brand"] or e["category"] in (None, "not_a_brand"):
                continue
            rec = recent.setdefault(e["brand"], {"brand": e["brand"], "category": e["category"], "last_seen": datetime.fromtimestamp(e["t"], timezone.utc).date().isoformat(), "tier": e["tier"], "posts": 0})
            rec["posts"] += 1
        if recent:
            clash[c] = sorted(recent.values(), key=lambda r: r["last_seen"], reverse=True)[:15]

    # ---- links -------------------------------------------------------------------------------------------------------------------------------
    cur.execute("""select distinct x.creator_id::text, c2.creator_id::text from creator_related_accounts x
                   join creators c2 on (lower(c2.instagram_handle) = lower(x.handle) or (x.platform = 'youtube' and lower(c2.youtube_handle) = lower(x.handle))) and c2.creator_id <> x.creator_id""")
    nb = defaultdict(set)
    for a, b in cur.fetchall():
        nb[a].add(b)
        nb[b].add(a)
    brand_creators = defaultdict(set)
    for c, es in ev.items():
        for e in es:
            if e["brand_id"] and e["category"] not in (None, "not_a_brand") and now_d - e["t"] / DAY <= 365:
                brand_creators[e["brand_id"]].add(c)
    shared = defaultdict(set)
    for cs in brand_creators.values():
        for a in cs:
            shared[a] |= cs - {a}
    sponsored_recent = {c for c, f in fatigue.items() if f["sponsored_last_30d"] > 0}

    # ---- existing results --------------------------------------------------------------------------------------------------------------------
    sent = {r["creator_id"]: r for r in load("temporal_sentiment.json")["creators"]}
    pairs = {r["creator_id"]: r for r in load("platform_pairs.json")["creators"]}
    promo = {r["creator_id"]: r for r in load("promotion_behaviour.json")["creators"]}
    fat_global = load("ad_fatigue.json")["results"][0]

    # ---- predict the missing platform ---------------------------------------------------------------------------------------------------------
    def yt_features(c):
        vs = yt.get(c, [])
        if len(vs) < 10 or c not in subs:
            return None
        last = sorted(vs, key=lambda v: -v["t"])[:60]
        views = [v["views"] for v in last]
        lpv = [v["likes"] / max(v["views"], 1) for v in last if v["likes"] is not None]
        cpv = [v["comments"] / max(v["views"], 1) for v in last if v["comments"] is not None]
        recent90 = [v for v in vs if now_d - v["t"] / DAY <= 90]
        ys = sent.get(c, {}).get("platforms", {}).get("youtube", {}).get("score", 0.5)
        return [math.log1p(subs[c]), math.log1p(float(np.median(views))), float(np.median(lpv)) if lpv else 0.0, float(np.median(cpv)) if cpv else 0.0, len(recent90) / 3.0,
                sum(v["fmt"] == "short" for v in vs) / len(vs), sum(v["sp"] for v in vs) / len(vs), ys, 1.0 if creators[c]["category"] == "fitness_influencer" else 0.0]
    NAMES = ["log subscribers", "log median views", "likes per view", "comments per view", "uploads per 30 days", "Shorts share", "sponsored share", "YouTube mood", "fitness creator"]
    train_ids, X, Y = [], [], []
    for c in creators:
        f = yt_features(c)
        likes = [p["likes"] for p in ig.get(c, []) if p["likes"] is not None and p["likes"] >= 0]
        if f and len(likes) >= 5:
            train_ids.append(c), X.append(f), Y.append(math.log1p(float(np.median(likes))))
    X, Y = np.array(X), np.array(Y)
    report = prediction_report(X, Y, size_col=0) if len(Y) >= 20 else None
    predicted = {}
    if report:
        model = _ridge_fit(X, Y, 5.0)
        lo, hi = report["residual_p10_p90"]
        for c in creators:
            if c in train_ids or ig.get(c):
                continue
            f = yt_features(c)
            if f:
                p = float(_ridge_predict(model, np.array([f]))[0])
                predicted[c] = {"typical_likes": int(round(math.expm1(p))), "range_80": [int(round(math.expm1(p + lo))), int(round(math.expm1(p + hi)))], "reliable": report["beats_size_only"]}
        print(f"prediction: {report}; predicted for {len(predicted)} creators without Instagram data", flush=True)

    # ---- assemble ------------------------------------------------------------------------------------------------------------------------------
    cur.execute("select creator_id::text, count(*) from post_snapshots where creator_id is not null group by 1")
    n_reads = dict(cur.fetchall())
    out_creators, gaps = [], []
    for c, base in creators.items():
        s = sent.get(c)
        plats = (s or {}).get("platforms", {})
        mood = None
        if "youtube" in plats and "instagram" in plats:
            mood = {"youtube": plats["youtube"], "instagram": plats["instagram"], **mood_gap(plats["youtube"]["score"], plats["youtube"]["n"], plats["instagram"]["score"], plats["instagram"]["n"])}
            gaps.append(mood)
        elif plats:
            mood = {k: v for k, v in plats.items() if k in ("youtube", "instagram", "reddit")} | {"label": "only one platform has scored comments, so no gap can be computed"}
        pr = pairs.get(c)
        coverage = "youtube+instagram" if yt.get(c) and ig.get(c) else "youtube" if yt.get(c) else "instagram" if ig.get(c) else "none"
        linked = nb.get(c, set())
        basis = "inferred" if linked else "isolated"
        tinfo = {"basis": "scored", "n_comments": sum(p["n"] for p in plats.values())} if plats else None
        grade, notes = grade_evidence(basis, tinfo, {"basis": "scored"} if (yt.get(c) or ig.get(c)) else None, coverage)
        sp_block = {"youtube_views": yt_views_per.get(c), "youtube_likes": yt_likes_per.get(c), "instagram_likes": ig_likes_per.get(c)}
        pm = promo.get(c)
        out_creators.append({
            **base,
            "coverage": {"platforms": coverage, "youtube_videos": len(yt.get(c, [])), "instagram_posts": len(ig.get(c, [])), "growth_readings": n_reads.get(c, 0)},
            "platform_strength": ({k: pr[k] for k in ("pairs", "stronger_platform", "youtube_vs_usual_median", "instagram_vs_usual_median", "basis")} if pr else None),
            "mood": mood,
            "speed": speed.get(c),
            "sponsored": {**sp_block, "buying_signals": (pm or {}).get("response"), "disclosure": (pm or {}).get("disclosure")},
            "fatigue": fatigue.get(c),
            "network": {"linked_creators": len(linked), "linked_sponsored_last_30d": len(linked & sponsored_recent), "shared_brand_creators": len(shared.get(c, ()))},
            "clash_events": clash.get(c, []),
            "predicted_instagram": predicted.get(c),
            "evidence": {"grade": grade, "notes": notes},
        })
    flagged = [g for g in gaps if g["significant"]]
    summary = {
        "creators": len(out_creators),
        "mood_gap": {"creators_with_both": len(gaps), "flagged": len(flagged), "warmer_on_instagram": sum(g["gap"] > 0 for g in flagged), "warmer_on_youtube": sum(g["gap"] < 0 for g in flagged),
                     "median_gap": round(float(np.median([g["gap"] for g in gaps])), 3) if gaps else None,
                     "note": "gap = Instagram minus YouTube comment mood (0..1); flagged only when it is at least 0.10 and clears 1.96 worst-case standard errors"},
        "sponsored_response": {"youtube_views": yt_views_pool, "youtube_likes": yt_likes_pool, "instagram_likes": ig_likes_pool,
                               "note": "each sponsored post against the same creator's organic posts of the same format within 45 days (YouTube) or 90 days (Instagram); log scale; placebo = fake sponsored posts drawn from organic ones"},
        "speed": {"videos": len(all_speed), "creators": len(speed), "median_share_first_24h": round(float(np.median(all_speed)), 3) if all_speed else None,
                  "note": "YouTube only; Instagram has too few growth readings; needs a reading in the first 6 h, around 24 h and at about 7 days"},
        "prediction": {"features": NAMES, **(report or {"n": int(len(Y))})},
        "fatigue": {"creators_above_usual": sum(f["above_usual"] for f in fatigue.values()), "global_test": {k: fat_global[k] for k in ("outcome", "creators", "median_slope", "ci95", "placebo_median", "p_one_sided_fatigue")},
                    "note": "the group test finds no clear fatigue effect, so 'above usual' is a fact about recent ad load, not a prediction of lower engagement"},
        "clash": {"creators_with_recent_brand_posts": len(clash), "window_days": CLASH_DAYS},
    }
    out = {"as_of": now.isoformat(timespec="seconds"), "summary": summary, "creators": out_creators,
           "limits": ["Sponsored labels are rule-based detections with a hand-checked sample; creators with a standing affiliate code on every video are labelled sponsored on all of them (see CAPSTONE_NEXT_STEPS.md).",
                      "Engagement is attention, not sales. Sponsored-post comparisons are observational within a creator and say nothing about cause.",
                      "Comment sentiment stores only a mean and a count, so mood-gap uncertainty is a worst-case bound.",
                      "Instagram growth readings are too few for an Instagram attention-speed estimate."]}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("saved", args.out, f"({Path(args.out).stat().st_size // 1024} KB)")
    print(json.dumps({k: v for k, v in summary.items() if k != "prediction"}, indent=1)[:3500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
