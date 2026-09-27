"""Phase 1 round 3: first genuine held-out training attempt on real data.

Prior rounds (2026-08-15, 2026-08-17) correctly treated every training run as a
pipeline-correctness check -- too few real (event, neighbour) pairs to mean anything
beyond "does it run." That changed this round: the orchestrator-verified canonical
pair count (`pair_count.py`, Track A) is 54, clearing the ~50-100 thesis-defensible
tier referenced in CAPSTONE_NEXT_STEPS.md, not just the >=20 floor for any split.

This script:
  1. Rebuilds the real HeteroData graph (259 creators, live pull) and reports
     structure against the 2026-08-17 numbers.
  2. Re-runs the GAT forward pass + inductive check on the current topology.
  3. Loads real per-creator targets from `training_pair_deltas.json`
     (produced by `scripts/compute_training_pair_deltas.py`, which itself imports
     Track A's canonical `pair_count.py` rather than re-deriving its own pair
     definition -- see that script's docstring for two real NULL-handling data
     bugs found and fixed this round while computing the deltas).
  4. Runs leave-one-out cross-validation over the real labeled creator-nodes --
     see the docstring on `leave_one_out_eval` for why LOO, not an 80/20 split,
     is the honest choice at this N.
  5. Reports calibration with explicit uncertainty, not a single point estimate.

READ-ONLY except for `.venv`'s own package cache and this repo's own files --
touches no data belonging to Track A/C/D.

Run (from repo root):
    DATABASE_URL=... PYTHONPATH=. .venv/Scripts/python.exe scripts/train_holdout_round3.py \\
        <creators.json> <collab_edges.json> <co_occurrence_edges.json> <sponsorship_edges.json> \\
        <training_pair_deltas.json>
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys

import torch

from ml.gail_loss import compute_gail_loss
from ml.gail_model import GAILModel
from ml.model import SchemaSmokeTestGAT
from ml.schema import CREATOR_FEATURE_DIM, empty_hetero_data
from ml.training import TrainConfig
from scripts.build_real_hetero_data import (
    load_brands,
    load_creator_features,
    load_sponsorship_edges,
    load_symmetric_edges,
    load_treatment,
    report_structure,
)

# 2026-08-17 (round 2) numbers, for direct comparison -- 259 creators / 161 pairs.
PRIOR_ROUND = {
    "creators": 259,
    "collab_edges_directed": 322,
    "isolated_pct": 36.3,
    "non_trivial_components": 12,
    "largest_component": 53,
    "max_degree": 18,
}


def load_real_targets_from_deltas(
    deltas_path: str, creator_id_to_index: dict[str, int], num_creators: int
) -> tuple[torch.Tensor, dict[str, list[float]]]:
    """Per-creator target = mean relative-engagement-lift across that creator's
    computed (event, neighbour) rows in `training_pair_deltas.json`. Only rows
    with a same-platform-computable `mean_lift` count -- cross-platform-only
    straddle rows (no single platform with both before/after MEASURED data)
    contribute nothing, by design (see compute_training_pair_deltas.py).
    """
    with open(deltas_path, encoding="utf-8") as f:
        rows = json.load(f)
    lifts_by_creator: dict[str, list[float]] = {}
    for r in rows:
        if r["mean_lift"] is not None:
            lifts_by_creator.setdefault(r["neighbour_id"], []).append(r["mean_lift"])

    target = torch.zeros(num_creators, dtype=torch.float32)
    for cid, lifts in lifts_by_creator.items():
        if cid in creator_id_to_index:
            target[creator_id_to_index[cid]] = statistics.mean(lifts)
    return target, lifts_by_creator


def leave_one_out_eval(
    data, treatment: torch.Tensor, target: torch.Tensor, labeled_idx: list[int], base_seed: int = 0
) -> list[dict]:
    """Leave-one-out CV over the labeled creator-nodes.

    WHY LOO, NOT AN 80/20 SPLIT: the target tensor is one scalar PER CREATOR
    NODE (transductive), not per (event, neighbour) pair -- multiple events on
    the same neighbour collapse to one averaged target. That leaves only 10
    distinct labeled creator-nodes from the 54 canonical pairs (44 either fail
    the same-platform-lift computability check or land on a neighbour already
    counted). An 80/20 split of N=10 holds out ~2 nodes on one random draw --
    a single point estimate with no way to know if it was a lucky or unlucky
    split. Leave-one-out uses every one of the 10 as a held-out example exactly
    once, giving 10 independent generalization-error draws instead of 1, at the
    cost of 10x the compute -- affordable at this N (small graph, 50 epochs).
    This is the standard, textbook choice for N this small, not a bespoke one.

    Each fold trains a FRESH model (no leakage across folds) with the held-out
    node's target masked out of the supervised loss; structural terms
    (smoothness/consistency/overlap) still see the full real graph every epoch,
    per ml/training.py's existing transductive design -- the held-out node's
    features and graph position are visible, only its label is hidden, which is
    correct transductive-GNN practice.
    """
    results = []
    for fold, held_out in enumerate(labeled_idx):
        torch.manual_seed(base_seed + fold)
        model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, hidden_channels=16, heads=2)
        config = TrainConfig(epochs=50, lr=1e-2, val_fraction=0.0, seed=base_seed + fold)

        # Bypass train()'s random val split -- we need a DETERMINISTIC held-out
        # set (exactly this one labeled node), not train()'s random 20%. Reuse
        # its internals directly (has_sponsored_neighbor / compute_gail_loss)
        # rather than duplicating them.
        from ml.causal_regularization import has_sponsored_neighbor

        num_creators = data["creator"].x.size(0)
        train_mask = torch.ones(num_creators, dtype=torch.bool)
        train_mask[held_out] = False
        collab_edge_index = data["creator", "collaborates_with", "creator"].edge_index
        collab_edge_weight = data["creator", "collaborates_with", "creator"].edge_attr
        has_sponsored = has_sponsored_neighbor(collab_edge_index, treatment)
        optimizer = torch.optim.Adam(model.parameters(), lr=config.lr)

        any_nan = False
        for _epoch in range(config.epochs):
            model.train()
            optimizer.zero_grad()
            prediction, exposure, propensity = model(data, treatment)
            loss, components = compute_gail_loss(
                prediction,
                target,
                propensity,
                collab_edge_index,
                collab_edge_weight,
                has_sponsored,
                config.loss_weights,
                prediction_mask=train_mask,
                treatment=treatment,
            )
            if any(math.isnan(v) for v in components.values()):
                any_nan = True
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            final_prediction, _, final_propensity = model(data, treatment)
            held_out_pred = final_prediction[held_out].item()
            held_out_target = target[held_out].item()
            held_out_sq_err = (held_out_pred - held_out_target) ** 2
            held_out_propensity = final_propensity[held_out].item()

        results.append(
            {
                "fold": fold,
                "held_out_node": held_out,
                "held_out_target": held_out_target,
                "held_out_prediction": held_out_pred,
                "held_out_sq_err": held_out_sq_err,
                "held_out_propensity": held_out_propensity,
                "nan_encountered": any_nan,
            }
        )
        print(
            f"  fold {fold + 1}/{len(labeled_idx)}: held out node={held_out} "
            f"target={held_out_target:+.4f} pred={held_out_pred:+.4f} "
            f"sq_err={held_out_sq_err:.4f} propensity={held_out_propensity:.3f} "
            f"nan={any_nan}"
        )
    return results


def main() -> int:
    # Redirecting stdout to a log file on Windows defaults to cp1252, which
    # crashes on non-Latin creator names (found live, 259-creator set includes
    # names outside cp1252's range). UTF-8 with replace matches how the data
    # actually is; this only affects this script's own stdout.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 6:
        print(__doc__)
        return 1
    creators_path, collab_path, cooccur_path, sponsorship_path, deltas_path = sys.argv[1:6]

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL env var required (session-only, never committed).")
        return 1

    print("Loading CLIP + BERT (real pretrained models)...")
    from ml.feature_extraction import FeatureExtractor

    extractor = FeatureExtractor(max_thumbnails=5)

    print("\n--- TASK 1: rebuilding the real HeteroData graph, current state ---")
    real_x, creator_id_to_index, creator_order = load_creator_features(creators_path, extractor)
    id_to_name = {}
    with open(creators_path, encoding="utf-8") as f:
        for r in json.load(f):
            id_to_name[creator_id_to_index[r["creator_id"]]] = r["name"]
    num_creators = real_x.size(0)
    assert real_x.shape[1] == CREATOR_FEATURE_DIM

    brand_x, brand_id_to_index = load_brands(database_url)
    collab_index, collab_attr = load_symmetric_edges(collab_path, creator_id_to_index)
    cooccur_index, cooccur_attr = load_symmetric_edges(cooccur_path, creator_id_to_index)
    sponsors_index, sponsored_by_index = load_sponsorship_edges(
        sponsorship_path, creator_id_to_index, brand_id_to_index
    )

    data = empty_hetero_data()
    data["creator"].x = real_x
    data["brand"].x = brand_x
    data["creator", "collaborates_with", "creator"].edge_index = collab_index
    data["creator", "collaborates_with", "creator"].edge_attr = collab_attr
    data["creator", "co_occurs_with", "creator"].edge_index = cooccur_index
    data["creator", "co_occurs_with", "creator"].edge_attr = cooccur_attr
    data["brand", "sponsors", "creator"].edge_index = sponsors_index
    data["creator", "sponsored_by", "brand"].edge_index = sponsored_by_index

    report_structure(data, id_to_name)
    print(f"\nComparison vs. 2026-08-17 (round 2, {PRIOR_ROUND['creators']} creators, "
          f"{PRIOR_ROUND['collab_edges_directed']} directed collab edges): "
          f"prior isolated={PRIOR_ROUND['isolated_pct']}%, "
          f"non-trivial components={PRIOR_ROUND['non_trivial_components']}, "
          f"largest={PRIOR_ROUND['largest_component']}, max degree={PRIOR_ROUND['max_degree']}.")

    print("\n--- TASK 2: GAT forward pass + inductive check on the CURRENT topology ---")
    torch.manual_seed(0)
    model = SchemaSmokeTestGAT(hidden_channels=16, heads=2)
    out = model(data)
    assert not out["creator"].isnan().any() and not out["brand"].isnan().any()
    print(f"Forward pass PASSED: creator={out['creator'].shape}, brand={out['brand'].shape}, no NaN.")

    from ml.dummy_data import make_dummy_hetero_data

    bigger = make_dummy_hetero_data(num_creators=num_creators + 15, num_brands=brand_x.size(0) + 2, seed=1)
    bigger["creator"].x[:num_creators] = real_x
    bigger["brand"].x[: brand_x.size(0)] = brand_x
    out_bigger = model(bigger)
    assert out_bigger["creator"].shape == (num_creators + 15, 16)
    assert not out_bigger["creator"].isnan().any()
    print(f"Inductive check PASSED: same trained instance runs on {num_creators + 15} nodes "
          "(15 appended to the current real graph), no retraining, no NaN.")

    print("\n--- TASK 4: real target + leave-one-out held-out evaluation ---")
    treatment = load_treatment(database_url, creator_id_to_index, num_creators)
    n_sponsored = int(treatment.sum().item())
    print(f"Treatment: {n_sponsored} of {num_creators} creators marked sponsored.")

    target, lifts_by_creator = load_real_targets_from_deltas(deltas_path, creator_id_to_index, num_creators)
    labeled_idx = [creator_id_to_index[cid] for cid in lifts_by_creator if cid in creator_id_to_index]
    print(f"Real labeled creator-nodes: {len(labeled_idx)} (from {sum(len(v) for v in lifts_by_creator.values())} "
          "same-platform-computable (event, neighbour) rows -- see compute_training_pair_deltas.py for why "
          "the per-node count is smaller than the 54 canonical pairs: multiple events on the same neighbour "
          "collapse to one node-level target, and cross-platform-only-straddle pairs have no computable lift).")
    for cid in lifts_by_creator:
        if cid in creator_id_to_index:
            idx = creator_id_to_index[cid]
            print(f"  {id_to_name.get(idx, cid)}: {len(lifts_by_creator[cid])} event(s), "
                  f"node target (mean lift) = {target[idx]:+.4f}")

    print(f"\nRunning leave-one-out CV over {len(labeled_idx)} labeled nodes "
          f"({len(labeled_idx)} folds, 50 epochs/fold, fresh model each fold)...")
    loo_results = leave_one_out_eval(data, treatment, target, labeled_idx)

    sq_errs = [r["held_out_sq_err"] for r in loo_results]
    any_nan_any_fold = any(r["nan_encountered"] for r in loo_results)

    print("\n--- TASK 5: calibration, reported with uncertainty ---")
    n = len(sq_errs)
    mean_sq_err = statistics.mean(sq_errs)
    print(f"Leave-one-out held-out MSE: mean={mean_sq_err:.4f} over {n} folds")
    if n > 1:
        stdev = statistics.stdev(sq_errs)
        sem = stdev / math.sqrt(n)
        print(f"  stdev across folds = {stdev:.4f}, standard error of the mean = {sem:.4f}")
        print(f"  rough 95% CI (mean +/- 1.96*SEM, NOT a rigorous small-sample interval "
              f"-- n={n} is far too small for the normal approximation to be trustworthy): "
              f"[{mean_sq_err - 1.96 * sem:.4f}, {mean_sq_err + 1.96 * sem:.4f}]")
    baseline_mse = statistics.mean(target[labeled_idx].pow(2).tolist())
    print(f"  naive always-predict-zero baseline MSE on the same {n} nodes: {baseline_mse:.4f}")
    print(f"  model beats the always-zero baseline: {mean_sq_err < baseline_mse}")
    print(f"NaN encountered in any fold: {any_nan_any_fold}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
