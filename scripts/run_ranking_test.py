"""Out-of-time ranking test (Eesha's PDF, item D2). READ ONLY on the database.

    python scripts/run_ranking_test.py [--cutoff 2026-01-01] [--scores gail_scores.json] [--out models/ranking_test.json]

Each method ranks creators using ONLY data before the cutoff. Then we look at what happened AFTER it: the creator's outcome = mean direct effect of their sponsored YouTube
videos in the outcome window (log views minus the creator's own typical video, see scripts/run_direct_effect.py; mature videos only). A good ranking puts creators with the
higher outcome at the top. Scores: Spearman correlation (95% interval resampling creators), Precision@10 (share of the method's top 10 that are in the top third of outcomes)
and NDCG@10, each next to what a random order gives.

Methods built in, all from pre-cutoff data: popularity (median log views), engagement rate (likes + comments per view), activity (number of videos), sponsorship share, and
PAST DIRECT EFFECT (the creator's own earlier sponsored-video effect: is the effect a stable trait?). `--scores` takes a JSON {creator_id: score} (for example GAIL's output
built ONLY from data before the cutoff) and adds it as another method. A model trained on all the data cannot be tested this way: it has already seen the outcome window.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_direct_effect import effects  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


def ndcg_at(order, gain, k=10):
    dcg = sum(gain[c] / math.log2(i + 2) for i, c in enumerate(order[:k]))
    ideal = sorted(gain.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cutoff", default="2026-01-01")
    ap.add_argument("--scores")
    ap.add_argument("--min-events", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "models" / "ranking_test.json"))
    args = ap.parse_args()
    cutoff = datetime.fromisoformat(args.cutoff).replace(tzinfo=timezone.utc)
    mature_end = datetime.now(timezone.utc) - timedelta(days=90)
    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]
    cur = psycopg2.connect(url).cursor()
    cur.execute("select creator_id::text, published_at, view_count, like_count, comment_count, is_sponsored from youtube_videos "
                "where creator_id is not null and published_at is not null and view_count is not null order by published_at")
    vids = defaultdict(list)
    for cid, d, v, l, c, sp in cur.fetchall():
        if d <= mature_end:
            vids[cid].append({"date": d, "sponsored": bool(sp), "views": math.log1p(v), "rate": math.log((((l or 0) + (c or 0)) + 1) / (v + 1))})
    methods = {"popularity (median log views)": {}, "engagement rate": {}, "activity (videos before cutoff)": {}, "sponsorship share": {}, "past direct effect": {}}
    outcome = {}
    for cid, posts in vids.items():
        before = [p for p in posts if p["date"] < cutoff]
        if len(before) < 20:
            continue
        spons_after = [(p, e) for p, e in effects(posts, "sponsored", "views") if cutoff <= p["date"]]
        if len(spons_after) < args.min_events:
            continue
        # PRE-cutoff features use only posts before the cutoff
        past = [e for p, e in effects(before, "sponsored", "views")]
        methods["popularity (median log views)"][cid] = st.median(p["views"] for p in before)
        methods["engagement rate"][cid] = st.median(p["rate"] for p in before)
        methods["activity (videos before cutoff)"][cid] = float(len(before))
        methods["sponsorship share"][cid] = sum(p["sponsored"] for p in before) / len(before)
        if past:
            methods["past direct effect"][cid] = st.mean(past)
        outcome[cid] = st.mean(e for _, e in spons_after)
    if args.scores:
        methods["supplied scores (--scores)"] = {c: float(s) for c, s in json.load(open(args.scores, encoding="utf-8")).items() if c in outcome}
    print(f"cutoff {args.cutoff}: {len(outcome)} creators with >= {args.min_events} sponsored videos after it (outcome = mean direct effect on views)")
    rnd = random.Random(11)
    result = {"cutoff": args.cutoff, "creators": len(outcome), "outcome": "mean log-views effect of sponsored videos after the cutoff vs the creator's own typical video", "methods": {}}
    top_third = set(sorted(outcome, key=outcome.get, reverse=True)[: max(len(outcome) // 3, 1)])
    gain = {c: outcome[c] - min(outcome.values()) for c in outcome}
    rand_ndcg = st.mean(ndcg_at(rnd.sample(list(outcome), len(outcome)), gain) for _ in range(2000)) if outcome else float("nan")
    for name, sc in methods.items():
        ids = [c for c in outcome if c in sc]
        if len(ids) < 12:
            result["methods"][name] = {"creators": len(ids), "note": "too few creators"}
            print(f"{name:34s} creators {len(ids)} (too few)")
            continue
        rho = spearman([sc[c] for c in ids], [outcome[c] for c in ids])
        boots = sorted(spearman([sc[c] for c in b], [outcome[c] for c in b]) for b in ([rnd.choice(ids) for _ in ids] for _ in range(2000)))
        order = sorted(ids, key=lambda c: sc[c], reverse=True)
        p10 = sum(1 for c in order[:10] if c in top_third) / min(10, len(order))
        sub_gain = {c: gain[c] for c in ids}
        n10 = ndcg_at(order, sub_gain)
        rn = st.mean(ndcg_at(rnd.sample(ids, len(ids)), sub_gain) for _ in range(2000))
        result["methods"][name] = {"creators": len(ids), "spearman": rho, "spearman_ci95": [boots[50], boots[1949]], "precision_at_10": p10,
                                   "precision_at_10_random": len([c for c in ids if c in top_third]) / len(ids), "ndcg_at_10": n10, "ndcg_at_10_random": rn}
        print(f"{name:34s} creators {len(ids):3d} | Spearman {rho:+.2f} [{boots[50]:+.2f}, {boots[1949]:+.2f}] | P@10 {p10:.2f} (random {result['methods'][name]['precision_at_10_random']:.2f}) | NDCG@10 {n10:.2f} (random {rn:.2f})")
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
