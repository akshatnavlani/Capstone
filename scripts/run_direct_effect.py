"""Direct effect: does a creator's OWN audience respond differently to the creator's own sponsored posts? (READ ONLY on the database.)

    python scripts/run_direct_effect.py [--out models/direct_effect.json] [--boot 5000]

For every sponsored post: effect = log(1 + engagement of the post) minus the median of log(1 + engagement) over the creator's 10 nearest NON-sponsored posts
on the same platform (within +-180 days, at least 5 needed). A creator is compared with ITSELF, so channel size and long-run growth cancel. Engagement:
YouTube = views (and, separately, (likes + comments) / views); Instagram = likes + comments. Only mature posts count (YouTube >= 90 days old, Instagram >= 30 days),
so a young post that is still collecting views is not read as a weak post.
SANITY CHECK ("placebo"): the same effect computed for non-sponsored posts, with the post itself and all sponsored posts left out of the comparison. It should sit near 0.
Intervals resample CREATORS (rows of one creator are not independent). Reported for all events and for strong-evidence events only (official label, disclosure tag,
spoken, creator comment). This is an association within creator, not proof of cause: sponsored posts can differ in topic or format. It is the first half of the causal
ranking the PDF asks for (direct effect); it is not spillover and does not touch GAIL.
"""
import argparse
import json
import math
import os
import random
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
STRONG = {"official_label", "disclosure_tag", "spoken", "creator_comment"}
K, MIN_K, HALF_WINDOW = 10, 5, timedelta(days=180)
MATURE_DAYS = {"youtube": 90, "instagram": 30}


def effects(posts, kind, metric):
    """posts: list of dict(date, sponsored, tier, m). Returns [(post, effect)] for posts of `kind` ('sponsored' or 'plain') that have enough comparison posts."""
    plain = [p for p in posts if not p["sponsored"] and p[metric] is not None]
    out = []
    for p in posts:
        if p[metric] is None or (p["sponsored"] != (kind == "sponsored")):
            continue
        near = sorted((q for q in plain if q is not p and abs(q["date"] - p["date"]) <= HALF_WINDOW), key=lambda q: abs(q["date"] - p["date"]))[:K]
        if len(near) >= MIN_K:
            out.append((p, p[metric] - st.median(q[metric] for q in near)))
    return out


def pooled(per_creator, boot, rnd):
    """per_creator: {creator: [effects]} -> median of creator means with a creator bootstrap interval."""
    means = {c: st.mean(v) for c, v in per_creator.items() if v}
    if not means:
        return None
    keys = list(means)
    draws = sorted(st.median(means[rnd.choice(keys)] for _ in keys) for _ in range(boot))
    return {"creators": len(means), "events": sum(len(v) for v in per_creator.values()), "median_of_creator_means": st.median(means.values()),
            "ci95": [draws[int(0.025 * boot)], draws[int(0.975 * boot)]], "creators_positive": sum(1 for m in means.values() if m > 0),
            "median_ratio_vs_own_typical_post": math.exp(st.median(means.values()))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "models" / "direct_effect.json"))
    ap.add_argument("--boot", type=int, default=5000)
    args = ap.parse_args()
    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]
    cur = psycopg2.connect(url).cursor()
    cur.execute("select content_id, sponsorship_evidence from creator_sponsorship_events")
    tier = dict(cur.fetchall())
    now = datetime.now(timezone.utc)
    series = defaultdict(list)
    cur.execute("select creator_id::text, video_id, published_at, view_count, like_count, comment_count, is_sponsored from youtube_videos where creator_id is not null and published_at is not null and view_count is not null")
    for cid, vid, d, v, l, c, sp in cur.fetchall():
        if now - d < timedelta(days=MATURE_DAYS["youtube"]):
            continue
        series[(cid, "youtube")].append({"date": d, "sponsored": bool(sp), "tier": tier.get(vid), "views": math.log1p(v), "rate": math.log((((l or 0) + (c or 0)) + 1) / (v + 1))})
    cur.execute("select creator_id::text, post_id, posted_at, like_count, comment_count, (is_sponsored or coalesce(has_paid_partnership_label, false)) from instagram_posts where creator_id is not null and posted_at is not null")
    for cid, pid, d, l, c, sp in cur.fetchall():
        if now - d < timedelta(days=MATURE_DAYS["instagram"]) or l is None or c is None:
            continue
        series[(cid, "instagram")].append({"date": d, "sponsored": bool(sp), "tier": tier.get(pid), "eng": math.log1p(l + c)})
    rnd = random.Random(5)
    result = {"as_of": now.isoformat(timespec="seconds"), "method": "log engagement of a sponsored post minus the median of the creator's 10 nearest non-sponsored posts (+-180 days, mature posts only)", "results": {}}
    for platform, metrics in (("youtube", ("views", "rate")), ("instagram", ("eng",))):
        for metric in metrics:
            for subset, keep in (("all_events", lambda p: True), ("strong_evidence_only", lambda p: p["tier"] in STRONG)):
                per_ev, per_plain = defaultdict(list), defaultdict(list)
                for (cid, plat), posts in series.items():
                    if plat != platform:
                        continue
                    for p, e in effects(posts, "sponsored", metric):
                        if keep(p):
                            per_ev[cid].append(e)
                    for p, e in effects(posts, "plain", metric):
                        per_plain[cid].append(e)
                real, plain = pooled(per_ev, args.boot, rnd), pooled(per_plain, args.boot, rnd)
                result["results"][f"{platform}/{metric}/{subset}"] = {"sponsored_posts": real, "placebo_non_sponsored_posts": plain}
                if real:
                    print(f"{platform:9s} {metric:6s} {subset:21s} creators {real['creators']:3d} events {real['events']:5d} | median effect {real['median_of_creator_means']:+.3f} "
                          f"[{real['ci95'][0]:+.3f}, {real['ci95'][1]:+.3f}] (x{real['median_ratio_vs_own_typical_post']:.2f}) positive for {real['creators_positive']} | placebo {plain['median_of_creator_means']:+.3f} [{plain['ci95'][0]:+.3f}, {plain['ci95'][1]:+.3f}]", flush=True)
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
