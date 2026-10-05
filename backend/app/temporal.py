"""Temporal branch service (PendingWork S1): real sentiment_risk_score plus
sentiment propagation along the collaboration graph.

Reads the precomputed artifact models/temporal_sentiment.json (written by
scripts/score_creator_sentiment.py), the same artifact pattern as the GAIL
checkpoint. Never raises into /recommendations: a missing artifact, a missing
creator, or a failure all fall back to basis="placeholder" at 0.5.

basis:
  "scored"      the creator has comments scored by the sentiment classifier
  "placeholder" no scored comments; sentiment stays the neutral 0.5

Propagation hyperparameters below are uncalibrated starting values. S3 found no
held-out outcome that could fit them (see scripts/calibrate_fusion.py), so they
stay documented priors.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from pathlib import Path

import numpy as np
from sqlmodel import Session

from app.feature_store import build_collaboration_edges, build_supported_co_occurrence_edges

logger = logging.getLogger(__name__)

try:
    from ml.temporal.propagation import (
        apply_propagated_risk,
        normalized_adjacency,
        propagate,
        propagation_matrix,
        risk_shock,
        top_source,
    )
    _HAS_PROPAGATION = True
except Exception as e:  # ml/ not importable in this environment
    _HAS_PROPAGATION = False
    logger.warning("ml.temporal unavailable (%s) -- sentiment propagation disabled", e)

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "models" / "temporal_sentiment.json"

PLACEHOLDER_SAFETY = 0.5
# Creators in the lowest SHOCK_PERCENTILE of safety scores start a shock. Relative
# to the population because absolute scores are bunched (about 0.6 to 0.8).
SHOCK_PERCENTILE = 20.0
PROPAGATION_ALPHA = 0.5   # decay per hop
PROPAGATION_HOPS = 2
PROPAGATION_BETA = 0.5    # how strongly incoming risk lowers a creator's safety
RELATION_WEIGHTS = {"collaborates_with": 1.0, "co_occurs_with": 1.0}

_cache: dict[str, dict] | None = None


def load_scores(path: Path = ARTIFACT_PATH) -> dict[str, dict]:
    """creator_id -> artifact row. Empty if the artifact is missing or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        logger.warning("temporal artifact unavailable (%s) -- sentiment stays placeholder", e)
        return {}
    return {row["creator_id"]: row for row in data.get("creators", [])}


def _fallback(creator_id: str) -> dict:
    return {
        "creator_id": creator_id,
        "sentiment_risk_score": PLACEHOLDER_SAFETY,
        "own_safety": None,
        "propagated_risk": 0.0,
        "source_creator_id": None,
        "n_comments": 0,
        "basis": "placeholder",
    }


def compute_temporal(session: Session, scores: dict[str, dict] | None = None) -> dict[str, dict]:
    """creator_id -> {sentiment_risk_score, own_safety, propagated_risk,
    source_creator_id, n_comments, basis}. sentiment_risk_score is the creator's own safety
    lowered by the risk propagated to them from collaborators.
    """
    scores = load_scores() if scores is None else scores
    if not scores or not _HAS_PROPAGATION:
        return {}

    edges_by_relation = {
        "collaborates_with": build_collaboration_edges(session),
        # Only co-occurrences backed by a post that names both creators in full (S8 audit);
        # the plain builder carries about 24% wrong links and roster-thread pairs.
        "co_occurs_with": build_supported_co_occurrence_edges(session),
    }
    ids = set(scores)
    for edges in edges_by_relation.values():
        for e in edges:
            ids.update((str(e.source_creator_id), str(e.target_creator_id)))
    ids = sorted(ids)
    index = {cid: i for i, cid in enumerate(ids)}

    safety = np.array([scores[c]["safety_score"] if c in scores else PLACEHOLDER_SAFETY for c in ids])
    scored = np.array([c in scores for c in ids])

    threshold = float(np.percentile(safety[scored], SHOCK_PERCENTILE))
    shock = np.where(scored, risk_shock(safety, threshold), 0.0)

    # log1p damps the count-based edge weights so heavy co-occurrence pairs do
    # not drown out collaboration edges after row-normalization.
    typed_edges = {
        relation: [(index[str(e.source_creator_id)], index[str(e.target_creator_id)], math.log1p(e.weight)) for e in edges]
        for relation, edges in edges_by_relation.items()
    }
    A = normalized_adjacency(len(ids), typed_edges, RELATION_WEIGHTS)
    M = propagation_matrix(A, alpha=PROPAGATION_ALPHA, hops=PROPAGATION_HOPS)
    propagated = propagate(shock, M)
    adjusted = apply_propagated_risk(safety, propagated, beta=PROPAGATION_BETA)

    out = {}
    for cid, i in index.items():
        src = top_source(M, shock, i)
        out[cid] = {
            "creator_id": cid,
            "sentiment_risk_score": float(adjusted[i]),
            "own_safety": float(safety[i]) if scored[i] else None,
            "propagated_risk": float(propagated[i]),
            "source_creator_id": ids[src] if src is not None else None,
            "n_comments": int(scores[ids[i]].get("n_comments", 0)) if scored[i] else 0,
            "basis": "scored" if scored[i] else "placeholder",
        }
    return out


def get_temporal_batch(session: Session, creator_ids: list[str | uuid.UUID] | None = None) -> dict[str, dict]:
    """Cached per process, like the GAIL forward pass; call reset_cache() after
    the artifact or the graph changes. Creators not in the result get a
    placeholder entry when `creator_ids` is given.
    """
    global _cache
    if _cache is None:
        try:
            _cache = compute_temporal(session)
        except Exception as e:
            logger.warning("temporal computation failed (%s) -- sentiment stays placeholder", e)
            return {str(c): _fallback(str(c)) for c in (creator_ids or [])}
    if creator_ids is None:
        return dict(_cache)
    return {str(c): _cache.get(str(c)) or _fallback(str(c)) for c in creator_ids}


def reset_cache() -> None:
    global _cache
    _cache = None
