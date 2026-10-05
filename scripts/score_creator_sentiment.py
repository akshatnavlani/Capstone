"""Per-creator brand-safety scores from real comments (PendingWork S1, step 1).

Read-only on the database. Writes a local JSON file; nothing is written to
Supabase. First run downloads the sentiment model (see ml/temporal/sentiment.py)
into the Hugging Face cache.

Usage (from the repo root, venv active):
    python scripts/score_creator_sentiment.py                     # trial: 20 creators
    python scripts/score_creator_sentiment.py --limit-creators 0  # all creators (slow on CPU)

DATABASE_URL is taken from the environment, else from backend/.env.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.temporal.sentiment import SentimentScorer, score_with_checkpoint, shrunk_mean  # noqa: E402

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Newest `cap` comments per creator per platform.
QUERIES = {
    "youtube": """
        select creator_id, name, text from (
          select cr.creator_id, cr.name, c.text,
                 row_number() over (partition by cr.creator_id order by c.published_at desc) rn
          from youtube_comments c
          join youtube_videos v on v.video_id = c.video_id
          join creators cr on cr.creator_id = v.creator_id
          where c.text is not null) t where rn <= %s""",
    "instagram": """
        select creator_id, name, text from (
          select cr.creator_id, cr.name, c.text,
                 row_number() over (partition by cr.creator_id order by c.fetched_at desc) rn
          from instagram_comments c
          join instagram_posts p on p.post_id = c.post_id
          join creators cr on cr.creator_id = p.creator_id
          where c.text is not null) t where rn <= %s""",
    "reddit": """
        select creator_id, name, text from (
          select cr.creator_id, cr.name, c.body as text,
                 row_number() over (partition by cr.creator_id order by c.fetched_at desc) rn
          from reddit_comments c
          join reddit_posts p on p.post_id = c.post_id
          join creators cr on cr.creator_id = p.creator_id
          where c.body is not null) t where rn <= %s""",
}


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env = (Path(__file__).resolve().parent.parent / "backend" / ".env").read_text(encoding="utf-8")
        url = re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    return url.replace("postgresql+psycopg2://", "postgresql://")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-per-creator", type=int, default=100, help="newest comments per creator per platform")
    ap.add_argument("--limit-creators", type=int, default=20, help="0 = all creators; else the N with most comments")
    ap.add_argument("--out", default="temporal_sentiment.json")
    args = ap.parse_args()

    conn = psycopg2.connect(database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()

    rows = []  # (creator_id, name, platform, text)
    for platform, sql in QUERIES.items():
        cur.execute(sql, (args.max_per_creator,))
        rows += [(str(cid), name, platform, text) for cid, name, text in cur.fetchall()]
    conn.close()
    print(f"loaded {len(rows)} comments")

    totals = defaultdict(int)
    for cid, _, _, _ in rows:
        totals[cid] += 1
    keep = set(totals) if args.limit_creators == 0 else set(
        sorted(totals, key=totals.get, reverse=True)[: args.limit_creators]
    )
    rows = [r for r in rows if r[0] in keep]
    print(f"scoring {len(rows)} comments for {len(keep)} creators (first run downloads the model)")

    scorer = SentimentScorer()
    # A comment's key is its creator, platform and text, so a rerun recognises
    # comments it already scored even if the database row order changes.
    keys = [hashlib.sha1(f"{r[0]}|{r[2]}|{r[3]}".encode("utf-8")).hexdigest() for r in rows]
    checkpoint = Path(args.out + ".checkpoint.json")
    scores = score_with_checkpoint(
        scorer.score, keys, [r[3] for r in rows], checkpoint,
        on_progress=lambda done, total: print(f"  scored {done}/{total} (checkpoint saved)", flush=True),
    )

    by_creator: dict[str, dict] = {}
    for (cid, name, platform, text), s in zip(rows, scores):
        c = by_creator.setdefault(cid, {"creator_id": cid, "name": name, "all": [], "platforms": defaultdict(list), "texts": []})
        c["all"].append(s)
        c["platforms"][platform].append(s)
        c["texts"].append((s, platform, text))

    # Scores only in the saved file: raw comment text is other people's content
    # and must not end up in a committed artifact. Samples are printed instead.
    results, samples = [], {}
    for c in by_creator.values():
        overall, n = shrunk_mean(c["all"])
        samples[c["creator_id"]] = sorted((t for t in c["texts"] if t[0] == t[0]), key=lambda t: t[0])[:3]
        results.append({
            "creator_id": c["creator_id"],
            "name": c["name"],
            "safety_score": round(overall, 4),
            "n_comments": n,
            "platforms": {p: {"score": round(shrunk_mean(v)[0], 4), "n": shrunk_mean(v)[1]} for p, v in c["platforms"].items()},
        })
    results.sort(key=lambda r: r["safety_score"])

    non_latin = sum(1 for r in rows if DEVANAGARI.search(r[3])) / max(len(rows), 1)
    Path(args.out).write_text(json.dumps({"share_devanagari": round(non_latin, 4), "creators": results}, indent=2), encoding="utf-8")
    checkpoint.unlink(missing_ok=True)  # final output is written; the resume file is no longer needed

    print(f"\nshare of comments containing Devanagari script: {non_latin:.1%} (English-trained model; read scores with this in mind)")
    print(f"\n{'safety':>7} {'n':>5}  creator")
    for r in results:
        print(f"{r['safety_score']:7.3f} {r['n_comments']:5d}  {r['name']}")
    print("\nlowest-scoring comments for the 3 least-safe creators (sanity check):")
    for r in results[:3]:
        print(f"-- {r['name']}")
        for s, p, t in samples[r["creator_id"]]:
            print(f"   [{s:.3f}] ({p}) {t[:160]}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
