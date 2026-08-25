# Handoff — Track B (ML-Core)

Start here. Last updated 2026-08-26 (prod artifact). Read `CAPSTONE_NEXT_STEPS.md` at repo
root FIRST, every session (`git pull origin main` — it lives on `main`,
rewritten frequently, supersedes this file and memory when they disagree),
then this file, then `GRAPH_SCHEMA.md` (the full technical spec, kept
current every round) for depth on any item below.

## What changed this round (2026-08-26 — prod artifact, P1.6 unblock)

**Shipped loadable prod artifact `models/gail_checkpoint.pt` (c6488a6, 3.7 MB)** — the unblock Track C was waiting on at `deaf630` (zero `torch.save`/`*.pt`, `backend/app/routers/scores.py:1` stuck at 0.5). Track C now loads via `ml/inference.py:1` (`load_predict`/`load_predict_batch`), not by retraining.

- **Prod training `scripts/train_prod_model.py:1` (new, LOO untouched):** trains ONCE on ALL computable pairs from fresh `pair_count.py` (54 rows, 138 checks, 23 directed / 19 undirected / 40 events yielding, `collab_edge_pairs` 170). Same-platform-computable 34/54 → collapsed to **10 distinct labelled creator-nodes** (per-node mean lift). Handles both NULL bugs (`WHERE e1 IS NOT NULL AND e2 IS NOT NULL`, not coalesce) and normalizes creator features before propensity head (`CAPSTONE_NEXT_STEPS.md:795` fix — propensity was 1.000 on held-out in all 10 LOO folds; now mean 0.61 min 0.0 max 1.0 on full-train, centred). Deterministic (seed 0, 100 epochs, hidden 16 heads 2). Saves `state_dict` + `config` + `feature_scaler` (mean/std 1289) + `training_pair_ids` + `git SHA` `ef826cd` + 4-reading + full tensors for offline inference. Reuses `ml/gail_model.py:1`/`ml/training.py:1`/`ml/schema.py:1`.
- **`ml/inference.py:1` (new):** `load_predict(creator_id: str) -> {spillover_score, basis: "trained"|"inferred", confidence_low/high}` + `load_predict_batch`; `IsolatedCreatorError` for degree 0 (72/259 isolates, 27.8 %), `FileNotFoundError` if checkpoint missing. Confidence WIDE for small-N (N=10, t 2.306 × residual_std 1.355 × sqrt(1+1/N) ≈ 3.28 half-width trained, 5.25 inferred; floors 0.15/0.25) — no fake precision. GAT inductive forward pass for `inferred` (embedding-based, no retrain). Single forward pass cached; backed by `models/gail_checkpoint.pt` `tensors` (creator_x_norm, brand_x, 340 collab + 1414 co_occurs edges, treatment/target).
- **Live graph reused (HeteroData 259 creators, 19 brands, 340 collab directed / 1414 co_occurs directed, giant 185):** same as 2026-08-22 LOO — co_occurs ~1,400 verified live, isolated 27.8 %, 2 components. See `GRAPH_SCHEMA.md` newest real-data status for full table.
- **Verification:** `pytest tests/ -q` **69 passed**, `scripts/verify_environment.py` OK (torch 2.6.0+cu124, PyG 2.8.0, CUDA RTX 3050), `scripts/train_prod_model.py` writes `models/gail_checkpoint.pt` (3774 KB), `ml/inference.py` returns all 3 bases on live HeteroData: `trained` CarryMinati `0.339 [-2.94,3.62]`, `inferred` abdevilliers17 `1.191 [-4.06,6.44]`, `isolated` _bungy_lover_.01 raises `IsolatedCreatorError`; batch + missing file also verified. MSE trained 1.84 vs baseline 67.36 (Kohli target +25.87 pred +21.62 sq_err 18.13 dominates — expected).
- **Track C next:** `git pull origin track-b-ml-core` → `from ml.inference import load_predict` in `backend/app/routers/scores.py`, replace 0.5 placeholder; `report.md` at worktree root documents artifact path, loader, and verification for handoff.

## What changed last round (2026-08-22)

**The graph and pair count crossed the orchestrator's thesis-defensible
tier this round: canonical computable pairs (`pair_count.py`, Track A's
single shared definition) is 54**, re-verified live before building on it.
This round attempted the first genuine held-out evaluation rather than
another pipeline-correctness check. Full detail in `GRAPH_SCHEMA.md`'s
newest "Real-data status" section — summary:

- **Co-occurrence edges went from 0 to 1,414** — the real structural story
  this round, bigger than collaboration-edge growth (322→340 directed).
  Graph consolidated from 12 small clusters (largest 53 nodes) into
  essentially one giant component (185 of 259 nodes) plus one 2-node pair.
  Isolated nodes dropped 36.3%→27.8%. This wasn't flagged in this round's
  brief — caught only by re-pulling the feature-store endpoint live.
- **Computed real before/after engagement deltas for all 54 canonical
  pairs** (`scripts/compute_training_pair_deltas.py`) and found + fixed two
  real NULL-handling bugs while doing it: (1) fully-unmeasured Instagram
  posts were being coalesced to zero engagement, fabricating fake
  million-percent "lifts" on Kohli/Anushka Sharma pairs; (2) even after
  excluding those, posts with only their smaller engagement metric measured
  (comment_count present, like_count NULL — a real, non-random pattern, not
  missing-at-random) still biased the average. Fixed by requiring both
  engagement columns non-null. After both fixes: 34 of 54 pairs have a
  same-platform-computable lift.
- **First genuine leave-one-out held-out evaluation.** The target is
  per-creator-node (not per-pair), so the honest N for a held-out split is
  10 distinct labeled creators, not 54 or 34 — see `GRAPH_SCHEMA.md` for why
  LOO (not an 80/20 split) is the right choice at this N.
- **Wired `doubly_robust_weights` into the loss for the first time**
  (defined since Weeks 3-4, never called) — real doubly-robust correction,
  not just a standalone-tested primitive. Backward-compatible, one new test.
- **Honest calibration result: real but fragile.** Headline LOO MSE (67.19)
  is ~99% driven by one pseudo-replicated outlier (Kohli, 16 of 34 rows
  measuring the same underlying Reddit-engagement jump). Excluding it, the
  model beats the always-zero baseline by ~14% on the other 9 — a real,
  modest signal, not a validated result. Also found: the propensity model
  saturates to 1.000 on held-out nodes in all 10 folds — the overlap
  assumption is not empirically satisfied by this run, a real limitation,
  not glossed over.
- **Direct sufficiency call: pipeline validated on real, non-trivial data
  for the first time — not yet a generalizable model.** See
  `GRAPH_SCHEMA.md` for the full reasoning and the two concrete next levers
  (per-pair rather than per-node targets; feature normalization before the
  propensity head).
- New scripts this round: `scripts/compute_training_pair_deltas.py` (real
  delta computation, imports Track A's canonical `pair_count.py` directly
  rather than re-deriving the pair definition) and
  `scripts/train_holdout_round3.py` (graph rebuild + GAT/inductive + LOO
  held-out training).

## Current state (one paragraph)

The full GAIL architecture is built and tested end-to-end **against dummy
data and real data**: heterogeneous graph schema (`ml/schema.py`, creator/brand
nodes) → GAT backbone (`ml/model.py`, chosen over GraphSAGE — see "Lessons"
below) → exposure module (`ml/exposure.py`) → causal regularization
(`ml/causal_regularization.py`: propensity/overlap, Laplacian smoothness,
consistency) → spillover prediction head (`ml/spillover_head.py`) →
combined loss (`ml/gail_loss.py`) → training loop (`ml/training.py`,
`ml/gail_model.py` wires it together) → evaluation harness
(`ml/evaluation.py`). CLIP+BERT feature extraction (`ml/feature_extraction.py`)
is validated against real scraped data (259 real creators). **69 tests pass** (`pytest tests/`, ~12 s).
The GAIL pipeline has been run four times against **real** creators/brands/edges/events: GAT forward pass + inductive check are real all four times; 2026-08-22 ran the first genuine LOO held-out evaluation (N=10, doubly-robust wired in); **2026-08-26 (this round) shipped the prod artifact** — `scripts/train_prod_model.py` trains ONCE on ALL 54 canonical pairs (34 same-platform-computable → 10 nodes) with normalized propensity, `ml/inference.py` serves `trained`/`inferred`/`isolated` via `models/gail_checkpoint.pt` (c6488a6, 3.7 MB, git SHA ef826cd, 259 creators, 340 collab / 1414 co_occurs edges). P1.6 is now unblocked for Track C — `backend/app/routers/scores.py` can replace 0.5 placeholder via `load_predict`. Bot detection (`ml/bot_detection.py`) remains separately complete.

## Open items (tagged with why)

- **Prod artifact shipped: `models/gail_checkpoint.pt` (c6488a6, 3.7 MB, 2026-08-26, git SHA ef826cd).** Track C loads via `ml/inference.py:load_predict` / `load_predict_batch` — `backend/app/routers/scores.py:1` 0.5 placeholder can now be wired. Loader spec: `load_predict(creator_id: str) -> {spillover_score, basis: "trained"|"inferred", confidence_low/high}`; `IsolatedCreatorError` for degree 0 (72/259 isolates), `FileNotFoundError` if checkpoint missing; confidence WIDE for N=10 (base half-width 3.28 trained / 5.25 inferred, t 2.306 df 8). Checkpoint embeds `state_dict` + `config` + `feature_scaler` (z-score, fixes `CAPSTONE_NEXT_STEPS.md:795` saturation) + 10 `training_pair_ids` + 4-reading + tensors for offline inference. `report.md` at worktree root is the durable trail for this round.
- **Real collaboration edges: 170 real pairs (340 directed) as of 2026-08-26 — unchanged from 2026-08-22**, steady. `pair_count.py` canonical: 54 rows, 23 directed / 19 undirected pairs, 40 events yielding.
- **Real co-occurrence edges: 1,414 directed as of 2026-08-26 — unchanged, still the giant-component driver** (was 0 at 08-17, jump caught live). Graph: 259 creators, 19 brands, 185-node giant + 2-node pair + 72 isolates (27.8 %); max degree 39-40. `pair_count.py` edge definition still draws only from `creator_related_accounts` — co_occurs blind spot may undercount pairs (REVIEW 2 BACKLOG).
- **Real sponsorship events: 17 creators with `is_sponsored` (16 brand_id-resolved edges) as of prod run** — same as 2026-08-22 LOO (16). 19 brands, still sparse metadata (2 with followers/handles).
- **Real training PAIRS: 54 canonical rows → 34 same-platform-computable → 10 labelled nodes (prod trains ONCE on all 10, LOO evaluated on 10 held-out).** Prod MSE 1.84 vs baseline 67.36, Kohli outlier (target +25.87 pred +21.62 sq_err 18.13) dominates — same as LOO's 67.19 vs 67.36 (>99 % from Kohli). Per-node table in `report.md` / `GRAPH_SCHEMA.md` newest section.
- **Propensity: now normalized.** `scripts/train_prod_model.py` z-scores creator_x (mean abs 0.224 std 0.236) before `PropensityScoreModel`; LOO had saturated to 1.000 in all 10 folds (`CAPSTONE_NEXT_STEPS.md:795`); prod final mean 0.61 min 0.00 max 1.00 (centred, not stuck). Overlap still has extremes at N=10 — honestly reported, not solved.
- **GraphSAGE-vs-GAT: settled** — GAT is inductive (verified structurally + empirically), weighted edges via `edge_dim`; fallback `ml/weighted_sage_conv.py` remains if needed.
- **`NUM_BRAND_CATEGORIES = 5` placeholder, `reputation_score` no source** — unchanged, unowned, flagged by Track C.

## Non-obvious lessons (read before assuming something is simple)

1. **GAT is inductive by construction — this overturned the original
   architecture rationale.** PROJECT_PLAN.md originally picked GraphSAGE
   specifically for "new nodes without full retrain." Verified (both by
   inspecting `GATConv`'s parameters — all shape-fixed, none per-node — and
   empirically, running the same trained model on a 3x-larger graph with no
   retraining) that GAT already has this property. Don't assume a past
   architecture decision's *stated reason* is still the real reason without
   checking — the fact that motivated GraphSAGE turned out not to require it.
2. **Structural regularization terms need the FULL graph, not a
   train/val-subsetted tensor.** `laplacian_smoothness_penalty` and
   `consistency_penalty` index into `collab_edge_index`, which uses the
   full node-index range. Subsetting `prediction[train_idx]` before passing
   it in desyncs indices and crashes. Fix pattern used throughout
   `ml/training.py`/`ml/gail_loss.py`: run the whole graph through the
   model every step, mask only the final supervised MSE loss to train
   nodes (`prediction_mask` param) — standard transductive-GNN practice.
3. **Zero-edge/zero-count cases are the ACTUAL current data state, not
   edge-case paranoia.** The real live graph has 0 collaboration edges
   right now. `laplacian_smoothness_penalty` returned `NaN` on empty edges
   (`.mean()` over an empty tensor) until this round — a latent bug from
   Weeks 3-4 that nothing caught until something new actually hit it with
   real-shaped (zero-edge) input. Test every new graph-structural function
   against `edge_index.shape == (2, 0)` explicitly; it's not hypothetical here.
4. **`transformers` 5.14.1's `CLIPModel.get_image_features()` returns a
   `BaseModelOutputWithPooling`, not a plain tensor** — the real embedding
   is `.pooler_output`. Most tutorials assume the old plain-tensor return.
   Caught by testing against a real fetched thumbnail before trusting it;
   would have silently produced garbage otherwise.
5. **Real DB credentials are never in git or memory — ask the user fresh
   each session.** Pattern used repeatedly and it works: ask directly for
   the Supabase `DATABASE_URL` (session-only use), clone Track C's backend
   branch into the scratchpad directory (`.../scratchpad/track-c-check/`,
   *not* this repo), run their unmodified code locally, hit
   `/feature-store/*` for derived data or connect via `psycopg2` directly
   for raw-table checks Track C's API doesn't expose, then kill the server.
   For anything another track's pipeline *writes* (e.g. Track C's
   `POST /labeling/run`), read-only checking is fine but never trigger
   their write endpoints unilaterally — that's their call, not yours, even
   just to "check" something.
6. **A cross-track doc claim can go stale within the same day** when the
   other track is actively iterating on data quality. Verify against live
   state before repeating a claim, even one from a careful, usually-correct
   track — this round's co-occurrence discrepancy (Track C's claimed real
   example had been purged as noise by Track A's own subsequent fix)
   is the concrete example.

## Exact next steps for the next round

1. Read `CAPSTONE_NEXT_STEPS.md` at repo root FIRST — it's now the
   project's actual source of truth (the orchestrator's cross-track living
   doc), supersedes this file and memory when they disagree, and gets
   rewritten frequently. `git pull origin main` before reading it, since it
   lives on `main` and this branch doesn't auto-sync.
2. `git status` (expect clean, artifact `models/gail_checkpoint.pt` present) and `pytest tests/` fresh (expect **69** passing, ~12 s) + `python scripts/verify_environment.py` — standard self-check.
3. **Track C wiring (P1.6):** pull `track-b-ml-core:c6488a6`, `from ml.inference import load_predict` in `backend/app/routers/scores.py`, replace 0.5 placeholder; smoke-test `load_predict` on one `trained`/`inferred`/`isolated` id each (see `report.md` examples).
4. **Re-run `pair_count.py` fresh against live DB, then `scripts/compute_training_pair_deltas.py`** if re-evaluating — prod training (`scripts/train_prod_model.py`) already did fresh `pair_count.compute` + same-platform lift with both-engagement-cols fix. For eval, LOO `scripts/train_holdout_round3.py` remains the honest held-out path (prod is for deployment, not for reporting generalization).
5. **Binding constraint remains per-node target design (N=10).** Redesign toward per-(event,neighbour) loss still top lever — would make Kohli's 16 rows 16 signals vs 1. Second lever now partly addressed (propensity normalized: mean 0.61 not 1.000), but overlap still has extremes at N=10.
6. **Sufficiency bar unchanged:** 54 rows clears ~50-100 pair-count tier, but N=10 (one outlier) is not a validated model. Report LOO 67.19 vs 67.36 (headline meaningless) / 14 % ex-Kohli, and prod 1.84 vs 67.36 with Kohli-dominated caveat — both honestly, not as generalization claims.
7. Update `GRAPH_SCHEMA.md` and this file together with whatever you find — both are living docs, not append-only logs; correct stale sections rather than only adding new ones. See `report.md` for this round's durable trail.
