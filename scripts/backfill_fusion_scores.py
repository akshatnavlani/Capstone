"""Backfill the fusionscore table with one baseline row per creator (PendingWork S3).

DRY RUN BY DEFAULT: reads the database and prints what it would insert; writes
nothing. Pass --write to insert (shared Supabase data, so only do that on purpose).
Creators that already have a row are skipped, so re-running does not duplicate;
--refresh adds a newer row for every creator (GET /scores/{id} reads the latest).

A stored row is a baseline that does not depend on a brand brief:
  spillover  the creator's GAIL percentile (0-1) under the current checkpoint
  sentiment  the Temporal-branch score (0.5 when the creator has no scored comments)
  feature    engagement + reach percentile only; the brief-dependent CLIP/BERT
             relevance is added live by /recommendations, so it cannot be stored
Confidence bounds use the same three-branch interval as the live endpoint.

Usage (repo root, venv active):
    python scripts/backfill_fusion_scores.py
    python scripts/backfill_fusion_scores.py --write
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from ml._scipy_compat import avoid_blocked_scipy_solver  # noqa: E402

avoid_blocked_scipy_solver()

from sqlmodel import Session, create_engine, select  # noqa: E402

from app import creator_features  # noqa: E402
from app.fusion import compute_fusion_score, feature_uncertainty, sentiment_uncertainty  # noqa: E402
from app.models import Creator, FusionScore  # noqa: E402
from app.spillover import get_spillover_batch  # noqa: E402
from app.temporal import get_temporal_batch  # noqa: E402
from ml.feature_score import metadata  # noqa: E402


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
        url = re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    return url


def baseline_feature_scores(artifact) -> dict[str, tuple[float, str]]:
    """creator_id -> (engagement/reach percentile, "scored"|"neutral")."""
    eng, reach = artifact["engagement"], artifact["log_reach"]
    score = metadata(eng, reach)
    known = np.isfinite(eng) | np.isfinite(reach)
    return {str(cid): (float(s), "scored" if k else "neutral") for cid, s, k in zip(artifact["ids"], score, known)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="insert the rows (default: preview only)")
    ap.add_argument("--refresh", action="store_true", help="add a newer row even for creators that have one")
    args = ap.parse_args()

    artifact = creator_features.load_artifact()
    feature = baseline_feature_scores(artifact) if artifact is not None else {}
    if artifact is None:
        print("models/creator_embeddings.npz not found: feature score stays 0.5 for everyone")

    with Session(create_engine(database_url())) as session:
        creators = session.exec(select(Creator)).all()
        have = {r for r in session.exec(select(FusionScore.creator_id)).all()}
        ids = [str(c.creator_id) for c in creators]
        spill = get_spillover_batch(ids)
        temporal = get_temporal_batch(session)

        rows = []
        for c in creators:
            cid = str(c.creator_id)
            if c.creator_id in have and not args.refresh:
                continue
            sp, tm = spill[cid], temporal.get(cid)
            scored = tm is not None and tm["basis"] == "scored"
            sentiment = tm["sentiment_risk_score"] if scored else 0.5
            feat, feat_basis = feature.get(cid, (0.5, "neutral"))
            final, lo, hi, adj, _ = compute_fusion_score(
                sp["spillover_unit"], sentiment, feat,
                spillover_half_width=(sp["unit_high"] - sp["unit_low"]) / 2, spillover_basis=sp["basis"],
                sentiment_half_width=sentiment_uncertainty(tm["n_comments"] if scored else None),
                feature_half_width=feature_uncertainty(feat_basis),
            )
            rows.append(FusionScore(
                creator_id=c.creator_id, spillover_score=sp["spillover_unit"], spillover_basis=sp["basis"],
                sentiment_risk_score=sentiment, creator_feature_score=feat, final_score=final,
                confidence_low=lo, confidence_high=hi, risk_adjustment=adj,
            ))

        print(f"{len(creators)} creators; {len(have)} already have a stored row; {len(rows)} rows to insert")
        for r in sorted(rows, key=lambda r: -r.final_score)[:5]:
            name = next(c.name for c in creators if c.creator_id == r.creator_id)
            print(f"  {r.final_score:5.1f} [{r.confidence_low:5.1f}, {r.confidence_high:5.1f}] {r.spillover_basis:9s} {name}")
        if rows:
            fin = np.array([r.final_score for r in rows])
            print(f"  final score range {fin.min():.1f} to {fin.max():.1f}, median {np.median(fin):.1f}")
        if not args.write:
            print("dry run: nothing written. Re-run with --write to insert.")
            return
        session.add_all(rows)
        session.commit()
        print(f"inserted {len(rows)} rows into fusionscore")


if __name__ == "__main__":
    main()
