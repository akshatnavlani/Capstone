"""Loadable inference for the prod GAIL checkpoint.

Artifact: `models/gail_checkpoint.pt` (produced by `scripts/train_prod_model.py`).
Provides `load_predict` / `load_predict_batch` for Track C's
`backend/app/routers/scores.py` (currently 0.5 placeholder, P1.6).

Basis:
  - "trained"  — creator has a real training label (is a neighbour in a
                 same-platform-computable (event, neighbour) pair).
  - "inferred" — graph-connected (degree > 0) but no label; prediction via
                 GAT inductive forward pass (embedding-based, no retrain).
  - isolated   — degree == 0 on BOTH collab + co_occurrence graphs; raise
                 `IsolatedCreatorError` (do not fabricate).

Confidence:
  Wide intervals for small-N (effective N≈10) and for inferred — no fake
  precision. Uses prediction-interval half-width:
      hw = t_{0.975, df} * residual_std * sqrt(1 + 1/N)
  where residual_std = sqrt(mse_trained), df = N-2, t from a small-N table
  (2.306 at N=10). Inferred multiplies by 1.6x. Minimum half-width 0.15 to
  avoid degenerate narrow intervals when mse is tiny.

Missing checkpoint → FileNotFoundError (do not fabricate).

Example:
  from ml.inference import load_predict, load_predict_batch, IsolatedCreatorError
  load_predict("some-creator-uuid")
  # {"spillover_score": 0.12, "basis": "trained", "confidence_low": -0.9, "confidence_high": 1.2}
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Dict, List

import torch

from app.gail.gail_model import GAILModel
from app.gail.schema import empty_hetero_data

DEFAULT_CKPT = Path(__file__).resolve().parents[2] / "models" / "gail_checkpoint.pt"

# t_{0.975, df} for df = N-2, N small. Values from t-distribution table.
# For df >= 30 use 1.96 (normal). This avoids scipy dependency.
_T_TABLE = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
    23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
    30: 2.042,
}


class IsolatedCreatorError(ValueError):
    """Creator is graph-isolated (degree 0) — no spillover can be estimated."""
    pass


# Module-level cache — lazy, singleton
_CACHE: dict | None = None


def _t_critical(df: int) -> float:
    if df <= 0:
        return 12.706  # very wide for N<=2
    if df in _T_TABLE:
        return _T_TABLE[df]
    if df > 30:
        return 1.96
    # interpolate roughly — closest
    return 2.0


def _load_checkpoint(ckpt_path: str | Path) -> dict:
    p = Path(ckpt_path)
    if not p.exists():
        raise FileNotFoundError(f"Checkpoint not found: {p} — run scripts/train_prod_model.py first")
    # weights_only=False because checkpoint contains tensors + python objects
    ckpt = torch.load(str(p), map_location="cpu", weights_only=False)
    return ckpt


def _build_data(ckpt: dict):
    """Reconstruct HeteroData from checkpoint tensors (offline, no DB)."""
    t = ckpt["tensors"]
    g = ckpt["graph"]
    data = empty_hetero_data()
    # Use normalized creator features — model was trained on these
    data["creator"].x = t["creator_x_norm"]
    data["brand"].x = t["brand_x"]
    data["creator", "collaborates_with", "creator"].edge_index = t["collab_edge_index"]
    data["creator", "collaborates_with", "creator"].edge_attr = t["collab_edge_attr"]
    data["creator", "co_occurs_with", "creator"].edge_index = t["coocc_edge_index"]
    data["creator", "co_occurs_with", "creator"].edge_attr = t["coocc_edge_attr"]
    data["brand", "sponsors", "creator"].edge_index = t.get("treatment", torch.empty((2,0))).new_empty((2,0)) if "sponsors" not in t else t.get("sponsors", torch.empty((2,0)))
    # sponsors edges are stored separately in graph; for inference we don't need them beyond treatment
    # Use empty for sponsors/sponsored_by — they are not used in prediction (only treatment tensor matters)
    data["brand", "sponsors", "creator"].edge_index = torch.empty((2, 0), dtype=torch.long)
    data["creator", "sponsored_by", "brand"].edge_index = torch.empty((2, 0), dtype=torch.long)
    # If checkpoint stored sponsors edges explicitly, restore
    if "sponsors_edge_index" in t:
        data["brand", "sponsors", "creator"].edge_index = t["sponsors_edge_index"]
        data["creator", "sponsored_by", "brand"].edge_index = t["sponsored_by_edge_index"]
    return data


def _ensure_loaded(ckpt_path: str | Path | None = None) -> dict:
    global _CACHE
    if _CACHE is not None and ckpt_path is None:
        return _CACHE
    # If explicit path differs from cached, reload
    path = Path(ckpt_path) if ckpt_path is not None else DEFAULT_CKPT
    # Check cache path mismatch
    if _CACHE is not None and _CACHE.get("_ckpt_path") == str(path):
        return _CACHE
    ckpt = _load_checkpoint(path)
    # Build model
    cfg = ckpt["config"]
    model = GAILModel(
        creator_feature_dim=cfg["creator_feature_dim"],
        hidden_channels=cfg.get("hidden_channels", 16),
        heads=cfg.get("heads", 2),
    )
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    data = _build_data(ckpt)
    treatment = ckpt["tensors"]["treatment"]
    # Also need target for mse reference if not in ckpt? Use training_stats
    # Compute degrees for isolated check
    import collections
    num_creators = data["creator"].x.size(0)
    degree = collections.Counter()
    for rel in [("creator", "collaborates_with", "creator"), ("creator", "co_occurs_with", "creator")]:
        ei = data[rel].edge_index
        if ei.numel():
            for s, d in ei.t().tolist():
                degree[s] += 1
                degree[d] += 1  # undirected counting; but directed already both ways, so this double-counts
                # Actually edges are already both directions, so counting one direction suffices.
                # Use set-based degree: count distinct neighbors
    # Better degree: distinct neighbor count via edge_index
    deg = [0]*num_creators
    for rel in [("creator", "collaborates_with", "creator"), ("creator", "co_occurs_with", "creator")]:
        ei = data[rel].edge_index
        if ei.size(1):
            for s, d in ei.t().tolist():
                deg[d] += 1
    # Precompute predictions for all nodes (single forward pass, cached)
    with torch.no_grad():
        preds, _, _ = model(data, treatment)
    preds = preds.detach()

    # Confidence params
    n_effective = ckpt["pair_count"].get("effective_N_labeled_nodes", len(ckpt.get("training_pair_ids", [])))
    if n_effective == 0:
        n_effective = len(ckpt.get("training_pair_ids", [])) or 10
    mse = ckpt.get("training_stats", {}).get("mse_trained", 0.5)
    # Fallback if mse nan or 0
    if not isinstance(mse, (int, float)) or math.isnan(mse) or mse <= 0:
        mse = 0.5
    residual_std = math.sqrt(mse)
    df = max(1, n_effective - 2)
    t = _t_critical(df)
    # Base half-width for prediction interval
    base_hw = t * residual_std * math.sqrt(1 + 1.0 / max(1, n_effective))
    # Minimum width to avoid fake precision (task requirement)
    base_hw = max(base_hw, 0.15)
    inferred_hw = max(base_hw * 1.6, 0.25)

    # Maps
    order: List[str] = ckpt["graph"]["creator_ids_order"]
    id_to_idx = {cid: i for i, cid in enumerate(order)}
    trained_set = set(ckpt.get("training_pair_ids", []))
    id_to_name = ckpt["graph"].get("creator_id_to_name", {})

    cache = {
        "_ckpt_path": str(path),
        "ckpt": ckpt,
        "model": model,
        "data": data,
        "treatment": treatment,
        "preds": preds,
        "degree": deg,
        "id_to_idx": id_to_idx,
        "trained_set": trained_set,
        "id_to_name": id_to_name,
        "n_effective": n_effective,
        "mse": mse,
        "residual_std": residual_std,
        "t": t,
        "base_hw": base_hw,
        "inferred_hw": inferred_hw,
    }
    _CACHE = cache
    return cache


def load_predict(creator_id: str, checkpoint_path: str | Path | None = None) -> Dict[str, float | str]:
    """Return spillover for one creator.

    Raises:
        FileNotFoundError — if checkpoint missing.
        IsolatedCreatorError — if creator is graph-isolated (degree 0).
        KeyError — if creator_id unknown.
    """
    cache = _ensure_loaded(checkpoint_path)
    id_to_idx = cache["id_to_idx"]
    if creator_id not in id_to_idx:
        raise KeyError(f"Unknown creator_id: {creator_id}")
    idx = id_to_idx[creator_id]
    deg = cache["degree"][idx]
    if deg == 0:
        raise IsolatedCreatorError(
            f"Creator {creator_id} ({cache['id_to_name'].get(creator_id, 'unknown')}) is graph-isolated "
            f"(degree 0 on collaborates_with + co_occurs_with) — no spillover can be inferred"
        )
    basis = "trained" if creator_id in cache["trained_set"] else "inferred"
    score = float(cache["preds"][idx].item())
    hw = cache["base_hw"] if basis == "trained" else cache["inferred_hw"]
    return {
        "spillover_score": score,
        "basis": basis,
        "confidence_low": score - hw,
        "confidence_high": score + hw,
    }


def load_predict_batch(creator_ids: List[str], checkpoint_path: str | Path | None = None) -> List[Dict]:
    """Batch version — returns list in same order; isolated creators raise IsolatedCreatorError inline
    as dicts with 'error' key instead of propagating, so caller can handle per-id.

    If you prefer strict raise-on-first-isolated, use `load_predict` in a loop.
    """
    cache = _ensure_loaded(checkpoint_path)
    results: List[Dict] = []
    for cid in creator_ids:
        try:
            results.append(load_predict(cid, checkpoint_path=checkpoint_path))
        except IsolatedCreatorError as e:
            results.append({"creator_id": cid, "error": "isolated", "message": str(e), "basis": "isolated"})
        except KeyError as e:
            results.append({"creator_id": cid, "error": "unknown", "message": str(e), "basis": "unknown"})
        except FileNotFoundError:
            raise
    return results


# Convenience alias for Track C — they may import `predict`
predict = load_predict


def get_model_info(checkpoint_path: str | Path | None = None) -> dict:
    """Return checkpoint metadata without running inference."""
    cache = _ensure_loaded(checkpoint_path)
    ckpt = cache["ckpt"]
    return {
        "git_sha": ckpt.get("git_sha"),
        "pair_count": ckpt.get("pair_count"),
        "graph": ckpt.get("graph"),
        "training_stats": ckpt.get("training_stats"),
        "config": ckpt.get("config"),
        "n_effective": cache["n_effective"],
        "mse": cache["mse"],
        "base_hw": cache["base_hw"],
        "inferred_hw": cache["inferred_hw"],
    }
