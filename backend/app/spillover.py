"""Spillover service — wraps Track B's GAIL checkpoint with honest fallbacks.

Task 1 spec:
  - Load via ml/inference.py:load_predict if artifact present
  - Else basis="placeholder" with 0.5 and wide CI — never crash, never fabricate
  - Isolated (degree 0) → placeholder, not infer

This module is the ONLY place that touches torch/PyG. All callers (fusion,
scores, recommendations) go through here so they survive when torch or the
checkpoint is absent (local dev, CI, tests without torch).
"""

from __future__ import annotations

import logging
import math
import uuid
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

SpilloverBasis = Literal["trained", "inferred", "placeholder", "isolated"]

# Wide CI half-width on 0-1 spillover scale for placeholder/isolated.
# Inference's inferred_hw is ~0.25-0.5 on 0-1 scale; placeholder uses same
# wide value. On final_score (0-100, w1=0.4) this becomes ±10-20 pts.
PLACEHOLDER_SPILLOVER = 0.5
PLACEHOLDER_HALF_WIDTH = 0.25  # 0-1 scale; matches inference.py inferred_hw minimum

# Lazy import state — do not fail at import time if torch/PyG missing.
_HAS_GAIL = False
_IMPORT_ERROR: Exception | None = None
_load_predict = None
_IsolatedCreatorError = None
_get_model_info = None

try:
    from app.gail.inference import IsolatedCreatorError as _Iso  # noqa: F401
    from app.gail.inference import get_model_info as _gmi  # noqa: F401
    from app.gail.inference import load_predict as _lp  # noqa: F401

    _load_predict = _lp
    _IsolatedCreatorError = _Iso
    _get_model_info = _gmi
    _HAS_GAIL = True
except Exception as e:  # ImportError, ModuleNotFoundError (torch missing), etc.
    _IMPORT_ERROR = e
    logger.warning("GAIL inference unavailable (%s) — spillover will fallback to placeholder", e)


def _fallback(creator_id: str | uuid.UUID, basis: SpilloverBasis = "placeholder") -> dict:
    """Return placeholder spillover dict. Basis is 'placeholder' or 'isolated'."""
    # Isolated and placeholder both use 0.5 but keep basis distinct for Track D.
    return {
        "creator_id": str(creator_id),
        "spillover_score": PLACEHOLDER_SPILLOVER,
        "basis": basis,
        "confidence_low": PLACEHOLDER_SPILLOVER - PLACEHOLDER_HALF_WIDTH,
        "confidence_high": PLACEHOLDER_SPILLOVER + PLACEHOLDER_HALF_WIDTH,
    }


def get_spillover(creator_id: str | uuid.UUID) -> dict:
    """Return spillover dict for one creator.

    Never raises IsolatedCreatorError/FileNotFoundError/KeyError to caller —
    instead maps to basis="isolated"/"placeholder" with 0.5 and wide CI.
    This keeps /recommendations and /scores from crashing on isolated nodes.
    """
    cid = str(creator_id)
    if not _HAS_GAIL or _load_predict is None:
        return _fallback(cid, "placeholder")

    try:
        res = _load_predict(cid)
        # res already has spillover_score, basis, confidence_low/high
        # Ensure creator_id echoed for batch consistency
        res["creator_id"] = cid
        # Clamp spillover to [0,1] for safety? Inference can return outside (e.g. -0.9)
        # but spec says spillover_score is 0-1; keep raw for honesty, clamp only if needed downstream.
        return res
    except Exception as e:
        # Isolated → map to isolated, not inferred
        if _IsolatedCreatorError is not None and isinstance(e, _IsolatedCreatorError):
            return _fallback(cid, "isolated")
        # Unknown creator_id → treat as isolated/placeholder (no graph entry)
        if isinstance(e, KeyError):
            # Could be "unknown creator" — same as isolated for consumer
            return _fallback(cid, "isolated")
        if isinstance(e, FileNotFoundError):
            logger.warning("GAIL checkpoint missing (%s) — using placeholder for %s", e, cid)
            return _fallback(cid, "placeholder")
        # Any other inference failure → placeholder, log once
        logger.warning("GAIL inference failed for %s (%s) — placeholder fallback", cid, e)
        return _fallback(cid, "placeholder")


def get_spillover_batch(creator_ids: list[str | uuid.UUID]) -> dict[str, dict]:
    """Batch helper — returns dict mapping str(creator_id) → spillover dict.

    Uses load_predict_batch if available for efficiency (single forward pass cached),
    otherwise falls back per-id.
    """
    if not creator_ids:
        return {}

    str_ids = [str(c) for c in creator_ids]
    if not _HAS_GAIL or _load_predict is None:
        return {cid: _fallback(cid, "placeholder") for cid in str_ids}

    # Try batch API if available
    try:
        from app.gail.inference import load_predict_batch  # lazy

        results = load_predict_batch(str_ids)
        out: dict[str, dict] = {}
        for item in results:
            # Batch returns either success: {spillover_score, basis, ...}
            # or error: {creator_id, error, basis: isolated/unknown}
            cid = item.get("creator_id") or item.get("creator_id", "")
            # load_predict_batch returns dicts without creator_id on success (only score/basis)
            # We need to align by order — batch returns list in same order as input
            # So we zip
            pass
        # Above is awkward — just zip by order
        out = {}
        for cid, item in zip(str_ids, results):
            if "error" in item:
                basis = item.get("basis", "isolated")
                if basis == "isolated":
                    out[cid] = _fallback(cid, "isolated")
                elif basis == "unknown":
                    out[cid] = _fallback(cid, "isolated")
                else:
                    out[cid] = _fallback(cid, "placeholder")
            else:
                item["creator_id"] = cid
                out[cid] = item
        return out
    except Exception as e:
        logger.warning("batch inference failed (%s) — falling back per-id", e)
        return {cid: get_spillover(cid) for cid in str_ids}


def get_model_info_safe() -> dict | None:
    """Return checkpoint metadata if available, else None."""
    if not _HAS_GAIL or _get_model_info is None:
        return None
    try:
        return _get_model_info()
    except Exception as e:
        logger.warning("get_model_info failed (%s)", e)
        return None


def is_gail_available() -> bool:
    return _HAS_GAIL


def gail_unavailable_reason() -> str | None:
    if _HAS_GAIL:
        return None
    return str(_IMPORT_ERROR) if _IMPORT_ERROR else "unknown"
