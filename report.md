# Track B — Round Report (2026-08-26) — Prod Artifact

Last verified: **2026-08-26** (live DB via `pair_count.py`, checkpoint `c6488a6`).

## What ran

**Prod training (new, this round): `scripts/train_prod_model.py:1`**
- Train ONCE on ALL computable pairs from Track A's fresh canonical `pair_count.py` (not LOO). Imports `pair_count.compute` directly — same 4-reading as orchestrator-verified, no re-derivation drift.
- Reuses `ml/gail_model.py:1` (`GAILModel`), `ml/training.py:1` (`TrainConfig`/`train` pattern), `ml/schema.py:1` (`empty_hetero_data`, 1289-dim creator features).
- Handles the two data-quality bugs already fixed in `scripts/compute_training_pair_deltas.py:1` / `CAPSTONE_NEXT_STEPS.md:799-802`:
  1. NULL→0 coalesce on sparse `like_count`/`comment_count`/`score` fabricated million-percent lifts (28 % of `instagram_posts` have `like_count`, 39.5 % have `comment_count`; missingness temporally skewed). Fix: `WHERE e1 IS NOT NULL AND e2 IS NOT NULL` — require BOTH engagement cols present, fully-measured only.
  2. Partial measurement bias (208 Instagram posts have `comment_count` but NULL `like_count`, zero reverse; same on Reddit `score` vs `num_comments`) — same fix, not coalesced.
  3. Same-platform lift only: `lift = (after_avg - before_avg)/(before_avg+1)` per platform, mean across platforms; cross-platform-only straddle (20/54) counted separately, not averaged across incompatible units.
- Normalizes creator features before propensity head (Round 3 rec `CAPSTONE_NEXT_STEPS.md:795` / `GRAPH_SCHEMA.md:429`): per-dim z-score `(x - mean)/std` (std clamped 1e-6), saved as `feature_scaler` and applied as `data["creator"].x = x_norm` so `PropensityScoreModel` sees normalized input. Fixes held-out saturation to 1.000 found in all 10 LOO folds.
- Deterministic: `seed 0`, `hidden_channels 16` `heads 2` `epochs 100` `lr 1e-2`, scaler computed from training data only, `torch.manual_seed(SEED)`.
- Builds live `HeteroData` from DB (mirrors `scripts/build_real_hetero_data.py:1` but DB-direct, no feature-store dump): `FeatureExtractor` (CLIP `openai/clip-vit-base-patch32` + BERT `bert-base-uncased`) over `youtube_channels.description` + `instagram_profiles.bio` + 20 titles/captions per creator, `log_subscriber_count`/`engagement_rate`/`category_one_hot`, `reputation_score=None` (no source, documented). Saves full tensors for offline inference.

**Prior eval (unchanged, not shipped): `scripts/train_holdout_round3.py:1`**
- LEAVE-ONE-OUT (10 folds, 50 epochs/fold, fresh model per fold) for honest calibration on small-N. Headline LOO MSE 67.19 vs baseline 67.36 — meaningless (>99 % from Virat Kohli outlier); ex-Kohli ~14 % win on other 9, N=9 unprovable. Kept intact — prod entrypoint is separate, does not modify LOO.

**Graph builder reference: `scripts/build_real_hetero_data.py:1`**
- Prod training re-implements its edge builders: `collaborates_with` via `creator_related_accounts` handle resolution (case-insensitive, prefix-stripped, ambiguous handles dropped) — 340 directed (170 undirected pairs); `co_occurs_with` via `reddit_post_creators` junction — **1414 directed** (matches this round's live expectation ~1,400, up from 0 at round 2).

**Tests & env:**
- `pytest tests/ -q` → **69 passed** (~12 s).
- `python scripts/verify_environment.py` → OK (torch 2.6.0+cu124, PyG 2.8.0.post1, CUDA RTX 3050).

## Artifact shipped

**Path:** `models/gail_checkpoint.pt` (3,864,983 bytes, 3.7 MB, <100 MB — committed, not `.gitkeep`) — single `torch.save` dict:

```python
{
  "state_dict": <GAILModel 16 hidden, 2 heads>,
  "config": {"creator_feature_dim":1289, "hidden_channels":16, "heads":2, "epochs":100, "lr":0.01, "seed":0},
  "feature_scaler": {"mean": [...1289], "std": [...1289]},   # also inside pt, not separate file
  "training_pair_ids": [10 distinct creator_ids with same-platform lift],
  "training_pair_details": [...54 detailed rows with per-platform lifts],
  "git_sha": "ef826cdd166105a0069224e6a0dcb7c58062c4e5",        # baked, from git rev-parse HEAD
  "pair_count": {
    "computable_pairs":54, "checks_evaluated":138, "distinct_directed_creator_pairs":23,
    "distinct_undirected_creator_pairs":19, "distinct_events_yielding_pairs":40, "events_total":53,
    "collab_edge_pairs":170, "same_platform_computable":34, "cross_platform_only":20,
    "effective_N_labeled_nodes":10
  },
  "graph": {"num_creators":259, "num_brands":19, "collab_edges_directed":340, "coocc_edges_directed":1414,
            "creator_ids_order": [...259], "creator_id_to_name": {...}},
  "tensors": {"creator_x_raw": (259,1289), "creator_x_norm": (259,1289), "brand_x": (19,9),
              "collab_edge_index": (2,340), "coocc_edge_index": (2,1414), "treatment": (259,), "target": (259,)},
  "training_stats": {"mse_trained":1.8377, "baseline_mse":67.3631, "per_node": [...], "final_propensity_mean":0.61, ...}
}
```

**Loader:** `ml/inference.py:1`

```python
from ml.inference import load_predict, load_predict_batch, IsolatedCreatorError, get_model_info

load_predict(creator_id: str, checkpoint_path: str|Path|None = None)
  -> {"spillover_score": float, "basis": "trained"|"inferred", "confidence_low": float, "confidence_high": float}
load_predict_batch(creator_ids: list[str]) -> list[dict]  # isolated returns {"error":"isolated","basis":"isolated"}
# IsolatedCreatorError if degree==0 on collaborates_with + co_occurs_with
# FileNotFoundError if checkpoint missing (no fabrication)
predict = load_predict  # alias for Track C
get_model_info() -> {"git_sha","pair_count","graph","training_stats","config","n_effective","mse","base_hw","inferred_hw"}
DEFAULT_CKPT = "models/gail_checkpoint.pt"
```

Track C wiring (P1.6 unblock): `backend/app/routers/scores.py:1` currently `0.5` placeholder at `deaf630` — replace with `load_predict` after pulling `track-b-ml-core:c6488a6`. No `torch.save`/`*.pt` existed before this commit.

## Live graph used

HeteroData built live from DB via `pair_count.py` + CLIP/BERT (no dump):

| | This round (2026-08-26 prod) | Prior round (2026-08-22 LOO) | Round 2 (08-17) |
|---|---|---|---|
| creators | **259** | 259 | 259 |
| brands | **19** (2 with real follower/post/verified: `duroflexworld`, `reliancejewels`) | 19 | 10 |
| `collaborates_with` edges (directed / undirected) | **340 / 170** | 340 / 170 | 322 / 161 |
| `co_occurs_with` edges (directed) | **1414** (~1,400 expected) | 1414 | 0 |
| isolated nodes (degree 0 on both) | **72 / 259 (27.8 %)** | 72 (27.8 %) | 94 (36.3 %) |
| non-trivial components | 2 (giant 185 + 2-node pair + isolates) | 2 | 12 |
| largest component | **185 nodes** (giant) | 185 | 53 |
| max degree | 39-40 | 39 | 18 |
| `sponsors`/`sponsored_by` edges | 16 (brand_id-resolved events) | 16 | 10 |
| treatment sponsored creators | 17/259 | 16-17 | — |

**Pair N trained on — ALL pairs, not LOO:**
- Canonical `pair_count.py` live: **54 computable (event,neighbour) rows** (138 checks evaluated, 53 dated sponsorship events total, **40 events yielding ≥1 pair**).
- Four readings (Track A's canonical, no re-drift): **directed 23** (collapses multi-event same pair), **undirected 19**, **events_yielding 40**, **collab edge pairs 170**.
- Same-platform-computable lifts: **34/54** (the training signal); **cross-platform-only straddle 20/54** counted separately, not mixed.
- Effective N for node-level head: **10 distinct labelled creator-nodes** (per-node mean lift: Kohli 16 events collapsed to 1). Prod trains ONCE on all 10 (mask over all labelled nodes) vs LOO's 10 folds holding out 1 each.
- Lift distribution (mean lift per neighbour, N=10): min -0.998, median -0.495, mean +2.212, max +25.874 (Kohli).

Giant component consolidation (0 → 1414 co_occurs) is the structural story, not collab growth — verified live, not from report.

## Verification

**`pytest tests/ -q`** — 69 passed, 12.59 s (no change, prod code backward-compatible; one new inference path not yet unit-tested, exercised via live check).

**`python scripts/verify_environment.py`** — `torch 2.6.0+cu124, torch_geometric 2.8.0.post1, CUDA True (RTX 3050) — OK`.

**`python scripts/train_prod_model.py`** — writes `models/gail_checkpoint.pt` (3774 KB) deterministically; report JSON: `computable_pairs 54 directed 23 undirected 19 events_yielding 40 effective_N 10 mse_trained 1.84 baseline 67.36 git_sha ef826cd`.

**`ml/inference.py` live HeteroData (co_occurs 1414) — one example per basis:**

```python
load_predict("c086bf2e-80f8-4902-b155-bbec78610798")  # CarryMinati
# → {"spillover_score": 0.339, "basis": "trained", "confidence_low": -2.940, "confidence_high": 3.618}
#    width 6.56 = t(2.306, df=8) * residual_std(1.355) * sqrt(1+1/10) ≈ 3.28 half-width, minimum 0.15

load_predict("89972049-1966-4f17-9c9d-e3343c62d090")  # abdevilliers17 (degree 1, not labelled)
# → {"spillover_score": 1.191, "basis": "inferred", "confidence_low": -4.055, "confidence_high": 6.436}
#    width 10.49 = 1.6× trained (inferred penalty) — GAT inductive forward pass, no retrain

load_predict("78e4817c-077f-4b4c-95de-2a8c043e5cf5")  # _bungy_lover_.01 (degree 0)
# → IsolatedCreatorError: Creator 78e4817c-... (_bungy_lover_.01) is graph-isolated (degree 0 on collaborates_with + co_occurs_with) — no spillover can be inferred

load_predict("...", checkpoint_path="models/missing.pt") -> FileNotFoundError (no fabrication)
load_predict_batch([trained, inferred]) -> [trained dict, inferred dict]
load_predict_batch([trained, inferred, isolated]) -> [..., {"error":"isolated","basis":"isolated"}]
```

**N=10 caveat:** Effective N is 10 distinct creator-nodes, not 54 rows — 16 of 34 computable rows are the same underlying Kohli Reddit jump (genuine 2026-08-05) measured from different Anushka Sharma anchors, collapsed to one per-node target. `compute_training_pair_deltas.py` pseudo-replication documented, `train_prod_model.py` preserves it (per-node mean) and reports separately.

**Propensity saturation `CAPSTONE_NEXT_STEPS.md:795` / `GRAPH_SCHEMA.md:395`:** Round 3 LOO saturated to 1.000 on held-out nodes in all 10 folds (overlap assumption violated). Prod fix: z-score normalize creator features (mean abs 0.224 std 0.236) before `PropensityScoreModel` (sigmoid on normalized 1289-dim). Result: final propensity mean 0.611 min 0.000 max 1.000 over all nodes (trained on all 10, no held-out) — centred, not stuck at 1.000; doubly-robust weights now finite, but still extremes exist (0 and 1) — overlap not fully satisfied at N=10, honestly reported.

**Recency cap:** `DEFAULT_RECENCY_DAYS=1095` respected (`pair_count.py`/`CAPSTONE_NEXT_STEPS.md:614` hard ceiling), not widened.

**Thesis MSE note (Kohli outlier):** Prod MSE 1.84 vs baseline 67.36 — headline 97 % improvement is driven by Kohli (target +25.87 pred +21.62 sq_err 18.13 = 98 % of residual sum). Per-node sorted by sq_err: Kohli 18.13, Gurfateh 0.092, Wamiqa 0.063, Mohitt 0.055, karanjohar 0.015, Pratibha 0.013, Carry 0.007, others <0.001. Ex-Kohli MSe ≈0.03 vs baseline ex-Kohli ≈0.47 — but N=9 is not a claim of generalization. LOO honest read (67.19 vs 67.36, ~14 % ex-Kohli) remains the valid held-out number; prod is for deployment, not for reporting generalization.

## What remains / thesis caveats

- **Small-N & pseudo-replication remain binding.** 54 rows → 10 nodes is the honest N; Kohli's 16-row jump is one signal. Per-(event,neighbour) loss instead of per-node averaging — Track B's own top-ranked lever — would make 16 real signals vs 1, bigger leverage than more collection.
- **Overlap not yet clean.** Normalized features centre propensity but extremes (0, 1) persist at N=10; report as limitation, not solved. Needs larger N or stronger regularization/overlap penalty tuning.
- **`co_occurs_with` adjacency undercount in `pair_count.py`.** `pair_count.py` draws edges from `creator_related_accounts` only (`REVIEW 2 BACKLOG`); co_occurs (1414) is in HeteroData/GAT but not in pair definition — pair count may be undercount until fixed (highest-value Review 2 follow-up).
- **`reputation_score`/`sentiment` still 0 % built** (`CAPSTONE_NEXT_STEPS.md:809`), temporal branch (lag/Granger) largely unbuilt, brand features sparse (17/19 brands all-zero).
- **P1.6 next:** Track C wires `ml.inference.load_predict` into `backend/app/routers/scores.py:1`, replaces 0.5 placeholder; calibrate `w1/w2/w3` and confidence from `inference` intervals.
- **Limitations to state plainly in thesis:** observational data, disclosure-based labels, India-skewed sample, engagement-per-rupee not true ROI, structural sparsity (27.8 % isolated), N=10, Kohli outlier, `pair_count` co_occurs blind spot.
- **Repro:** `PYTHONPATH=. .venv\Scripts\python.exe scripts/train_prod_model.py` (needs `DATABASE_URL` pooler); inference is offline after — `from ml.inference import load_predict; load_predict(creator_id)`.
