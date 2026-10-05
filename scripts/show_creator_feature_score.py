"""See how the creator feature score (PendingWork S2) works for any brand brief.

    python scripts\\show_creator_feature_score.py "cricket bat and gear"
    python scripts\\show_creator_feature_score.py "yoga and wellness classes" --top 15

Prints the creators with the highest score for that brief and, for each one,
what the score was built from: whether the creator has thumbnails and text
(relevance) and engagement / reach (metadata). Creators with nothing known
stay at exactly 0.5. Read only: it never writes to the database.
Takes about a minute (loading CLIP and BERT).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("brief", help="the product category / brief, e.g. 'running shoes'")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    os.environ["DATABASE_URL"] = re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    from ml._scipy_compat import avoid_blocked_scipy_solver

    avoid_blocked_scipy_solver()
    from sqlmodel import Session, create_engine

    from app import creator_features as cf
    from app.feature_store import build_creator_features
    from ml.creator_embeddings import QueryEmbedder
    from ml.feature_extraction import FeatureExtractor

    art = cf.load_artifact()
    if art is None:
        sys.exit("models/creator_embeddings.npz not found: run scripts\\compute_creator_embeddings.py first")
    with Session(create_engine(os.environ["DATABASE_URL"])) as s:
        names = {str(f.creator_id): f.name for f in build_creator_features(s)}

    print("loading CLIP and BERT...", flush=True)
    embedder = QueryEmbedder.from_extractor(FeatureExtractor(max_thumbnails=5))
    res = cf.score_query(args.brief, art, embedder)

    idx = {cid: i for i, cid in enumerate(art["ids"])}
    scores = np.array([v["score"] for v in res.values()])
    n_neutral = sum(v["basis"] == "neutral" for v in res.values())
    print(f"\nBrief: {args.brief!r}")
    print(f"{len(res)} creators scored: {len(res) - n_neutral} with real signal, {n_neutral} neutral (0.5, nothing known)")
    print(f"score range {scores.min():.2f} to {scores.max():.2f}, mean {scores.mean():.2f}\n")
    print(f"{'score':>5}  {'creator':32s} image text  engagement  reach")
    for cid, v in sorted(res.items(), key=lambda kv: -kv[1]["score"])[: args.top]:
        i = idx[cid]
        eng = art["engagement"][i]
        reach = art["log_reach"][i]
        print(f"{v['score']:5.2f}  {names.get(cid, cid)[:32]:32s} {'yes' if art['has_img'][i] else '-':5s} {'yes' if art['has_text'][i] else '-':4s} "
              f"{'%.4f' % eng if np.isfinite(eng) else '-':>10}  {'%.1f' % reach if np.isfinite(reach) else '-':>5}")
    print("\nHow to read it: relevance = how close the creator's thumbnails/text are to the brief (70%),")
    print("metadata = engagement and reach percentile (30%). Missing parts are skipped, never invented.")


if __name__ == "__main__":
    main()
