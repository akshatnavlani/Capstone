"""Audience-overlap graph: two creators are linked when the same people comment on both. READ ONLY on the database; no API quota.

    python scripts/build_audience_overlap.py [--min-shared 3] [--top-k 6] [--out models/audience_overlap.json] [--edges exports/training_inputs_26oct/audience_overlap_edges.json]

WHY (29 Oct 2026): only 95 of 150 creators have any link in the graph and 7 real collaboration pairs sit inside the 150. YouTube comments we already hold carry the
commenter's handle (229,263 comments, 114,743 distinct commenters on the 150). A person who comments on two creators is evidence the two share an audience. Edge weight is
cosine similarity of the two creators' commenter sets, each commenter counted 1/log2(1+number of creators they comment on) so one spammer commenting on everyone adds little.
An edge is kept when at least --min-shared people comment on both and it is among the creator's --top-k strongest.

CHECK: audience overlap must beat chance at joining creators of the same category (creators.category), or it is not carrying signal; the result is written next to the edges.
LIMIT: "same commenter handle" is a handle on YouTube; the same person may use other handles elsewhere (we do not match across platforms) and a handle can be a bot.
Edges are directed both ways (as mention_edges.json), weight in (0,1].
"""
import argparse
import itertools
import json
import math
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
V = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"


def build(by_author, min_shared, top_k):
    """by_author: {handle: set(creator_id)}. Returns {(a,b): (shared, weight)} for a<b."""
    size = Counter()
    shared = Counter()
    wshared = defaultdict(float)
    for _, cs in by_author.items():
        for c in cs:
            size[c] += 1
        if 2 <= len(cs) <= 30:
            w = 1.0 / math.log2(1 + len(cs))
            for p in itertools.combinations(sorted(cs), 2):
                shared[p] += 1
                wshared[p] += w
    cand = {p: (n, wshared[p] / math.sqrt(size[p[0]] * size[p[1]])) for p, n in shared.items() if n >= min_shared}
    keep = set()
    nb = defaultdict(list)
    for (a, b), (n, w) in cand.items():
        nb[a].append((w, b))
        nb[b].append((w, a))
    for c, lst in nb.items():
        for w, o in sorted(lst, reverse=True)[:top_k]:
            keep.add(tuple(sorted((c, o))))
    return {p: cand[p] for p in keep}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-shared", type=int, default=3)
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--out", default=str(ROOT / "models" / "audience_overlap.json"))
    ap.add_argument("--edges", default=str(ROOT / "exports" / "training_inputs_26oct" / "audience_overlap_edges.json"))
    args = ap.parse_args()
    import psycopg2
    from dotenv import dotenv_values

    conn = psycopg2.connect(dotenv_values(ROOT / ".env")["DATABASE_URL"], connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute(f"select c.author_handle, v.creator_id::text from youtube_comments c join youtube_videos v on v.video_id=c.video_id where v.creator_id in {V} and c.author_handle is not null group by 1,2")
    by_author = defaultdict(set)
    for a, c in cur.fetchall():
        by_author[a].add(c)
    cur.execute(f"select creator_id::text, category from creators where creator_id in {V}")
    cat = {c: k for c, k in cur.fetchall()}
    conn.close()

    edges = build(by_author, args.min_shared, args.top_k)
    linked = {c for p in edges for c in p}
    degree = Counter(c for p in edges for c in p)

    # does overlap beat chance at joining creators of the same category?
    same = lambda p: cat.get(p[0]) is not None and cat.get(p[0]) == cat.get(p[1])  # noqa: E731
    obs = sum(same(p) for p in edges) / max(len(edges), 1)
    ids = sorted(cat)
    rng = random.Random(7)
    allpairs = list(itertools.combinations(ids, 2))
    chance = sum(same(p) for p in allpairs) / len(allpairs)
    perm = []
    for _ in range(2000):
        sample = rng.sample(allpairs, len(edges))
        perm.append(sum(same(p) for p in sample) / len(edges))
    p_val = (1 + sum(x >= obs for x in perm)) / (1 + len(perm))

    out = {
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {"min_shared_commenters": args.min_shared, "top_k_per_creator": args.top_k},
        "commenters": len(by_author), "commenters_on_2plus_creators": sum(len(s) >= 2 for s in by_author.values()),
        "undirected_edges": len(edges), "directed_edges": 2 * len(edges), "creators_linked": len(linked),
        "median_degree": float(sorted(degree.values())[len(degree) // 2]) if degree else 0.0, "max_degree": max(degree.values()) if degree else 0,
        "same_category_share_of_edges": round(obs, 3), "same_category_share_of_random_pairs": round(chance, 3), "p_value_against_random_pairs": round(p_val, 4),
        "limit": "same handle on YouTube comments only; handle may be a bot; no match across platforms. Overlap is shared audience, not influence.",
    }
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    rows = []
    for (a, b), (n, w) in sorted(edges.items()):
        rows.append({"source_creator_id": a, "target_creator_id": b, "weight": round(w, 4), "shared_commenters": n})
        rows.append({"source_creator_id": b, "target_creator_id": a, "weight": round(w, 4), "shared_commenters": n})
    Path(args.edges).write_text(json.dumps(rows), encoding="utf-8")
    print(json.dumps(out, indent=1))
    print("edges saved", args.edges)
    return 0


if __name__ == "__main__":
    sys.exit(main())
