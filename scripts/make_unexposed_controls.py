"""Give the spillover estimator an unexposed comparison group (positivity), then build planted-effect worlds on top of it.

PROBLEM: every creator with a measured lift is a neighbour of a sponsored creator, so exposure is 1 for all of them and an AIPW effect is not
identified (the zero-effect control returned +3.4). FIX: add creators with NO sponsored neighbour (and not sponsored themselves). Their
outcome is the same lift measure computed around dates drawn from the real event dates, so season, platform and growth stage match; the only
thing that differs is that nobody near them was sponsored.

Writes <out>/real (real exposed targets + unexposed creators) and <out>/beta_<b> (planted worlds: noise everywhere, +b*sd on the exposed only).
Arguments: <base_dir with the 5 export files> <out_dir> [seed]. READ ONLY on the database.
Needs ml.engagement_lift and ml.target_clustering (on Eesha's branch review2-eesha-model, not yet merged here): run with PYTHONPATH pointing at a checkout that has them.
"""
import json
import random
import shutil
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

from ml.engagement_lift import platform_lift, row_target
from ml.target_clustering import DEFAULT_WINDOW_DAYS, windowed_engagement

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TABLES = {"instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
          "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
          "reddit": ("reddit_posts", "posted_at", "score", "num_comments")}
FILES = ("creators.json", "collab_edges.json", "co_occurrence_edges.json", "sponsorship_edges.json")
DATES_PER_CREATOR = 5

base, out = Path(sys.argv[1]), Path(sys.argv[2])
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
rng = random.Random(seed)
rows = json.load(open(base / "training_pair_deltas.json", encoding="utf-8"))
exposed_rows = [r for r in rows if r.get("mean_lift") is not None]
exposed_nodes = {r["neighbour_id"] for r in exposed_rows}
creators = json.load(open(base / "creators.json", encoding="utf-8"))
all_ids = [c["creator_id"] for c in creators]

cur = psycopg2.connect(dotenv_values(r"C:\Users\Shimona\Documents\casptone\.env")["DATABASE_URL"]).cursor()
cur.execute("select distinct creator_id::text from creator_sponsorship_events")
own = {r[0] for r in cur.fetchall()}
neigh = defaultdict(set)
for f in ("collab_edges.json", "co_occurrence_edges.json"):
    for e in json.load(open(base / f, encoding="utf-8")):
        neigh[e["target_creator_id"]].add(e["source_creator_id"])
        neigh[e["source_creator_id"]].add(e["target_creator_id"])
has_sponsored_neighbour = {c: bool(neigh[c] & own) for c in all_ids}
unexposed = [c for c in all_ids if not has_sponsored_neighbour[c] and c not in own and c not in exposed_nodes]
print(f"creators {len(all_ids)} | sponsored themselves {len(own & set(all_ids))} | exposed with a measured lift {len(exposed_nodes)} | "
      f"candidates with no sponsored neighbour {len(unexposed)}")

series = defaultdict(list)
for platform, (table, dcol, e1, e2) in TABLES.items():
    cur.execute(f"select creator_id::text, {dcol}, {e1}, {e2} from {table} where creator_id is not null and {dcol} is not null "
                f"and {e1} is not null and {e2} is not null order by {dcol}")
    for cid, d, a, b in cur.fetchall():
        series[(cid, platform)].append((d, a + b))


def lift_at(cid, when):
    pl = {}
    for platform in TABLES:
        s = series.get((cid, platform))
        if s:
            before, after = windowed_engagement(s, when, DEFAULT_WINDOW_DAYS)
            if before and after:
                pl[platform] = platform_lift(before, after)
    return row_target(pl, "median") if pl else None


pool = sorted({r["event_date"] for r in exposed_rows})
extra = []
for c in unexposed:
    dates = rng.sample(pool, min(DATES_PER_CREATOR, len(pool)))
    lifts = [x for x in (lift_at(c, datetime.fromisoformat(d)) for d in dates) if x is not None]
    if lifts:
        t = st.median(lifts)
        extra.append({"event_creator_id": None, "event_item_id": None, "event_platform": None, "event_date": dates[0], "neighbour_id": c,
                      "platform_lifts": {}, "mean_lift": t, "robust_lift": t, "computable_same_platform": True,
                      "cluster_id": f"{c}#0", "cluster_weight": 1.0})
print(f"unexposed creators with a measurable lift: {len(extra)}")
ex_t = [r["mean_lift"] for r in exposed_rows]
un_t = [r["mean_lift"] for r in extra]
print(f"exposed rows {len(ex_t)}: median {st.median(ex_t):+.3f} sd {st.pstdev(ex_t):.3f} | unexposed {len(un_t)}: median {st.median(un_t):+.3f} sd {st.pstdev(un_t):.3f}")


def write(name, deltas):
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy(base / f, d / f)
    json.dump(deltas, open(d / "training_pair_deltas.json", "w", encoding="utf-8"))


write("real", exposed_rows + extra)
sd = st.pstdev([x for x in ex_t if abs(x) < 20])
labelled = sorted({r["neighbour_id"] for r in exposed_rows + extra})
for beta in (0.0, 0.5, 1.0):
    noise = {n: rng.gauss(0, sd) for n in labelled}
    planted = [{**r, "mean_lift": noise[r["neighbour_id"]] + (beta * sd if r["neighbour_id"] in exposed_nodes else 0.0),
                "robust_lift": None} for r in exposed_rows + extra]
    write(f"beta_{beta}", planted)
    print(f"wrote beta_{beta}: true effect = {beta * sd:+.3f} (sd of real lifts {sd:.3f})")
