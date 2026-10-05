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

import bisect
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
    from ml.inference import IsolatedCreatorError as _Iso  # noqa: F401
    from ml.inference import get_model_info as _gmi  # noqa: F401
    from ml.inference import load_predict as _lp  # noqa: F401

    _load_predict = _lp
    _IsolatedCreatorError = _Iso
    _get_model_info = _gmi
    _HAS_GAIL = True
except Exception as e:  # ImportError, ModuleNotFoundError (torch missing), etc.
    _IMPORT_ERROR = e
    logger.warning("GAIL inference unavailable (%s) — spillover will fallback to placeholder", e)


# GAIL predicts the relative engagement lift after a sponsorship: unbounded
# (observed -1 to +23), not a 0-1 score. Fusion needs 0-1, so the lift is turned
# into its percentile among all graph-connected creators ("spillover_unit"). The
# raw lift and its interval stay in spillover_score / confidence_*.
# A creator with no graph signal knows nothing: the middle, with the widest 95%
# interval a uniform rank allows (0.025 to 0.975).
NEUTRAL_UNIT = 0.5
NEUTRAL_UNIT_HALF_WIDTH = 0.475

_reference: list[float] | None = None


def unit_rank(value: float, sorted_reference: list[float]) -> float:
    """Percentile of `value` among an ascending `sorted_reference` (ties share the
    middle rank), in (0, 1)."""
    if not sorted_reference:
        return NEUTRAL_UNIT
    below = bisect.bisect_left(sorted_reference, value)
    through = bisect.bisect_right(sorted_reference, value)
    return (below + through) / 2 / len(sorted_reference)


def _reference_lifts() -> list[float]:
    """Sorted GAIL predictions of every graph-connected creator (cached)."""
    global _reference
    if _reference is None:
        from ml.inference import _ensure_loaded  # lazy, only reached when GAIL is available

        c = _ensure_loaded()
        _reference = sorted(float(p) for p, d in zip(c["preds"].view(-1).tolist(), c["degree"]) if d > 0)
    return _reference


def _with_unit(res: dict) -> dict:
    """Add spillover_unit / unit_low / unit_high (0-1) to a real GAIL result."""
    ref = _reference_lifts()
    res["spillover_unit"] = unit_rank(res["spillover_score"], ref)
    res["unit_low"] = unit_rank(res["confidence_low"], ref)
    res["unit_high"] = unit_rank(res["confidence_high"], ref)
    return res


def _fallback(creator_id: str | uuid.UUID, basis: SpilloverBasis = "placeholder") -> dict:
    """Return placeholder spillover dict. Basis is 'placeholder' or 'isolated'."""
    # Isolated and placeholder both use 0.5 but keep basis distinct for Track D.
    return {
        "creator_id": str(creator_id),
        "spillover_score": PLACEHOLDER_SPILLOVER,
        "basis": basis,
        "confidence_low": PLACEHOLDER_SPILLOVER - PLACEHOLDER_HALF_WIDTH,
        "confidence_high": PLACEHOLDER_SPILLOVER + PLACEHOLDER_HALF_WIDTH,
        "spillover_unit": NEUTRAL_UNIT,
        "unit_low": NEUTRAL_UNIT - NEUTRAL_UNIT_HALF_WIDTH,
        "unit_high": NEUTRAL_UNIT + NEUTRAL_UNIT_HALF_WIDTH,
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
        # spillover_score stays the raw lift (unbounded); fusion uses spillover_unit (0-1).
        return _with_unit(res)
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
        from ml.inference import load_predict_batch  # lazy

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
                out[cid] = _with_unit(item)
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
