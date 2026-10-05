"""Creator feature score service (PendingWork S2): the real third input of the
fusion layer, replacing the constant 0.5.

Reads the precomputed artifact models/creator_embeddings.npz (written by
scripts/compute_creator_embeddings.py) and scores every creator against the
brand's product category with ml.feature_score. Embedding the category needs
CLIP and BERT, which take about a minute to load, so they load once in a
background thread: until they are ready, and whenever the artifact or the
models are unavailable, `get_feature_scores` returns None and the caller keeps
the neutral 0.5. It never raises into /recommendations.

Set CREATOR_FEATURES_DISABLED=1 to turn it off (the backend tests do).
"""
from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "models" / "creator_embeddings.npz"
_CACHE_SIZE = 32

_lock = threading.Lock()
_artifact: dict | None = None
_embedder = None
_loading = False
_scores_cache: "OrderedDict[str, dict[str, dict]]" = OrderedDict()


def load_artifact(path: Path = ARTIFACT_PATH) -> dict | None:
    """Artifact arrays as a dict, or None when the file is missing or unreadable."""
    try:
        with np.load(path, allow_pickle=False) as z:
            return {k: z[k] for k in z.files}
    except (FileNotFoundError, OSError, ValueError) as e:
        logger.warning("creator embeddings unavailable (%s) -- creator feature score stays 0.5", e)
        return None


def score_query(query: str, artifact: dict, embedder) -> dict[str, dict]:
    """creator_id -> {"score": float in [0, 1], "basis": "scored" | "neutral"}.
    Pure given the artifact and an embedder, so it is testable with fakes."""
    from ml.feature_score import cosine, creator_feature_scores

    q = query.strip()
    q_clip = embedder.clip_text(q)
    image_sim = cosine(artifact["clip"], q_clip)
    text_sims = [cosine(artifact["clip_text"], q_clip), cosine(artifact["bert"], embedder.bert_text(q))]
    scores = creator_feature_scores(
        image_sim, artifact["has_img"], text_sims, artifact["has_text"], artifact["engagement"], artifact["log_reach"],
    )
    known = (
        artifact["has_img"].astype(bool) | artifact["has_text"].astype(bool)
        | np.isfinite(artifact["engagement"]) | np.isfinite(artifact["log_reach"])
    )
    return {
        str(cid): {"score": float(s), "basis": "scored" if k else "neutral"}
        for cid, s, k in zip(artifact["ids"], scores, known)
    }


def _load_in_background() -> None:
    global _artifact, _embedder, _loading
    try:
        artifact = load_artifact()
        if artifact is None:
            return
        from ml._scipy_compat import avoid_blocked_scipy_solver

        avoid_blocked_scipy_solver()
        from ml.creator_embeddings import QueryEmbedder
        from ml.feature_extraction import FeatureExtractor

        embedder = QueryEmbedder.from_extractor(FeatureExtractor(max_thumbnails=5))
        with _lock:
            _artifact, _embedder = artifact, embedder
        logger.info("creator feature score ready (%d creators)", len(artifact["ids"]))
    except Exception as e:  # torch/transformers missing, weights not cached, ...
        logger.warning("creator feature models unavailable (%s) -- creator feature score stays 0.5", e)
    finally:
        _loading = False


def get_feature_scores(query: str | None) -> dict[str, dict] | None:
    """Scores for the brand's product category, or None if not available yet."""
    global _loading
    if os.environ.get("CREATOR_FEATURES_DISABLED") or not query or not query.strip():
        return None
    key = query.strip().lower()
    with _lock:
        if key in _scores_cache:
            _scores_cache.move_to_end(key)
            return _scores_cache[key]
        artifact, embedder = _artifact, _embedder
        if embedder is None and not _loading and ARTIFACT_PATH.exists():
            _loading = True
            threading.Thread(target=_load_in_background, daemon=True).start()
    if artifact is None or embedder is None:
        return None
    try:
        result = score_query(key, artifact, embedder)
    except Exception as e:
        logger.warning("creator feature scoring failed (%s) -- stays 0.5", e)
        return None
    with _lock:
        _scores_cache[key] = result
        while len(_scores_cache) > _CACHE_SIZE:
            _scores_cache.popitem(last=False)
    return result


def reset() -> None:
    """Forget the loaded models and cached scores (tests, or after re-running the script)."""
    global _artifact, _embedder, _loading
    with _lock:
        _artifact = _embedder = None
        _loading = False
        _scores_cache.clear()
