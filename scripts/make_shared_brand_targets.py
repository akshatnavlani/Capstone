"""Training targets for creators linked by a SHARED BRAND (two creators who both have a sponsored post for the same brand), using Eesha's own lift definition.

WHY (26 Oct 2026): `pair_count` (Track A) only counts an (event, neighbour) pair when the sponsored creator LISTS a collaborator who is also one of our
creators. Of 880 listed collaborators only 7 are inside the verified 150, so GAIL trains on about 20 examples whatever the graph looks like. This script adds the
same kind of (event, neighbour, lift) rows for shared-brand neighbours, which is the only way the shared-brand relation becomes TRAINING data and not just graph edges.

    PYTHONPATH=<checkout of review2-eesha-model> python scripts/make_shared_brand_targets.py --base <dir> --out <dir>

<dir> for --base holds the files written by scripts/export_feature_store.py plus training_pair_deltas.json (from compute_training_pair_deltas.py).
Needs ml.engagement_lift and ml.target_clustering, which live on Eesha's branch and are not on this one. READ ONLY on the database.

First it recomputes every one of her collaboration lifts in memory and stops if any differs, so the shared-brand rows use exactly her definition (same windows,
same fully-measured-posts rule). Writes into --out: training_pair_deltas.json (her rows + the shared-brand rows, `relation` marks which is which, `mean_lift` set to
the robust median lift as her leave-one-out script reads that field) and co_occurrence_edges.json with the shared-brand edges added as a weaker association.
Shared-brand exposure is an EXPLORATORY relation (niche overlap can contribute); keep it labelled that way in any write-up.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

from ml.engagement_lift import platform_lift, row_target
from ml.target_clustering import DEFAULT_WINDOW_DAYS, cluster_events, cluster_weights, summarize, windowed_engagement

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
TABLES = {"instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
          "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
          "reddit": ("reddit_posts", "posted_at", "score", "num_comments")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    base, out = Path(args.base), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in ("creators.json", "collab_edges.json", "sponsorship_edges.json"):
        shutil.copy(base / f, out / f)

    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]
    cur = psycopg2.connect(url).cursor()
    series = defaultdict(list)   # (creator, platform) -> [(date, engagement)], fully measured posts only (her layer-2 rule)
    for platform, (table, dcol, e1, e2) in TABLES.items():
        cur.execute(f"select creator_id::text, {dcol}, {e1}, {e2} from {table} where creator_id is not null and {dcol} is not null "
                    f"and {e1} is not null and {e2} is not null order by {dcol}")
        for cid, d, a, b in cur.fetchall():
            series[(cid, platform)].append((d, a + b))
    print("engagement series loaded:", len(series), flush=True)

    def lifts_for(neighbour: str, event_date) -> dict:
        res = {}
        for platform in TABLES:
            rows = series.get((neighbour, platform))
            if not rows:
                continue
            before, after = windowed_engagement(rows, event_date, DEFAULT_WINDOW_DAYS)
            if before and after:
                res[platform] = platform_lift(before, after)
        return res

    # 1. validate against her file
    her = json.load(open(base / "training_pair_deltas.json", encoding="utf-8"))
    bad = checked = 0
    for r in her:
        if r["mean_lift"] is None:
            continue
        pl = lifts_for(r["neighbour_id"], dt.datetime.fromisoformat(r["event_date"]))
        checked += 1
        if set(pl) != set(r["platform_lifts"]) or abs(row_target(pl, "median") - r["robust_lift"]) > 1e-9:
            bad += 1
    print(f"CHECK against her file: {checked} lift rows recomputed in memory, {bad} differ", flush=True)
    if bad:
        sys.exit("my computation does not reproduce hers: stopping, nothing written")

    # 2. shared-brand pairs: every other creator who also has a sponsored post for the event's brand
    cur.execute("""select e.creator_id::text, e.brand_id::text, e.platform, e.content_id, e.posted_at from creator_sponsorship_events e
                   where e.creator_id is not null and e.brand_id is not null and e.posted_at is not null""")
    events = cur.fetchall()
    by_brand = defaultdict(set)
    for c, b, *_ in events:
        by_brand[b].add(c)
    rows = []
    for creator, brand, platform, item, when in events:
        for nb in by_brand[brand] - {creator}:
            pl = lifts_for(nb, when)
            if not pl:
                continue
            rows.append({"event_creator_id": creator, "event_item_id": item, "event_platform": platform, "event_date": str(when),
                         "neighbour_id": nb, "platform_lifts": pl, "mean_lift": row_target(pl, "mean"), "robust_lift": row_target(pl, "median"),
                         "computable_same_platform": True, "relation": "shared_brand", "brand_id": brand})
    print(f"shared-brand (event, neighbour) rows with a same-platform lift: {len(rows)} from {len({r['event_item_id'] for r in rows})} events", flush=True)
    have = {(r["event_item_id"], r["neighbour_id"]) for r in her}
    rows = [r for r in rows if (r["event_item_id"], r["neighbour_id"]) not in have]
    clusters = cluster_events(rows, window_days=DEFAULT_WINDOW_DAYS)
    for r, cid, w in zip(rows, clusters, cluster_weights(clusters)):
        r["cluster_id"], r["cluster_weight"] = cid, w
    st = summarize(clusters)
    lifts = [r["robust_lift"] for r in rows]
    print(f"after E2 clustering ({DEFAULT_WINDOW_DAYS}-day window): {st['rows']} rows -> {st['clusters']} independent observations; "
          f"{len({r['neighbour_id'] for r in rows})} distinct neighbours; largest cluster {st['largest'][0][1]} rows ({st['max_cluster_share']:.0%})")
    print(f"robust lift: median {statistics.median(lifts):+.3f} | mean {statistics.mean(lifts):+.3f} | stdev {statistics.pstdev(lifts):.3f} | max|lift| {max(abs(x) for x in lifts):.2f}")

    # 3. write
    union = [dict(r, relation="collaboration") for r in her] + rows
    for r in union:
        if r.get("robust_lift") is not None:
            r["mean_lift"] = r["robust_lift"]          # her leave-one-out reads `mean_lift`; this makes it test the median target
    json.dump(union, open(out / "training_pair_deltas.json", "w", encoding="utf-8"))
    co = json.load(open(base / "co_occurrence_edges.json", encoding="utf-8"))
    pairs = defaultdict(int)
    for creators in by_brand.values():
        cs = sorted(creators)
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                pairs[(cs[i], cs[j])] += 1
    sk, tk = [k for k in co[0] if "source" in k][0], [k for k in co[0] if "target" in k][0]
    extra = []
    for (a, b), n in pairs.items():
        extra.append({sk: a, tk: b, "weight": float(n)})
        extra.append({sk: b, tk: a, "weight": float(n)})
    json.dump(co + extra, open(out / "co_occurrence_edges.json", "w", encoding="utf-8"))
    print(f"edges: {len(co)} co-occurrence + {len(extra)} shared-brand (directed) written | rows in deltas file: {len(union)} "
          f"({len(her)} collaboration + {len(rows)} shared-brand)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
