# Handoff — Track B (ML-Core)

Start here. Last updated 2026-08-22. Read `CAPSTONE_NEXT_STEPS.md` at repo
root FIRST, every session (`git pull origin main` — it lives on `main`,
rewritten frequently, supersedes this file and memory when they disagree),
then this file, then `GRAPH_SCHEMA.md` (the full technical spec, kept
current every round) for depth on any item below.

## What changed this round (2026-08-22)

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
data only**: heterogeneous graph schema (`ml/schema.py`, creator/brand
nodes) → GAT backbone (`ml/model.py`, chosen over GraphSAGE — see "Lessons"
below) → exposure module (`ml/exposure.py`) → causal regularization
(`ml/causal_regularization.py`: propensity/overlap, Laplacian smoothness,
consistency) → spillover prediction head (`ml/spillover_head.py`) →
combined loss (`ml/gail_loss.py`) → training loop (`ml/training.py`,
`ml/gail_model.py` wires it together) → evaluation harness
(`ml/evaluation.py`). CLIP+BERT feature extraction (`ml/feature_extraction.py`)
is validated against real scraped data (259 real creators as of this
round). **69 tests pass** (`pytest tests/`, ~90s). The full GAIL
pipeline has now been run three times against **real** creators/brands/
edges/events end-to-end — GAT forward pass and inductive check are real
results all three times; this round (2026-08-22) ran the first genuine
leave-one-out held-out evaluation, with `doubly_robust_weights` (defined
since Weeks 3-4) wired into the loss for real for the first time. Real,
but fragile: a small held-out improvement over baseline survives once one
pseudo-replicated outlier is excluded, but N=10 labeled nodes and a
saturated propensity model mean this is still evidence the pipeline works
on real data, not a validated model — see Open Items and the sufficiency
call in `GRAPH_SCHEMA.md`. Bot detection (`ml/bot_detection.py`) is
separately complete and unrelated to the training-loop work.

## Open items (tagged with why)

- **Real collaboration edges: 170 real pairs (340 directed edges) as of
  2026-08-22**, up from 161 two rounds ago — steady, no longer the fast-
  moving number.
- **Real co-occurrence edges: 1,414 as of 2026-08-22 — up from 0.** The
  real structural story this round: consolidated the graph from 12 small
  clusters (largest 53 nodes) into one 185-node giant component + one
  2-node pair. Not flagged in this round's brief; caught only by re-pulling
  `/feature-store/edges/co-occurrence` live rather than trusting the prior
  "still 0" note. Flag to Track A/C: worth confirming this is real
  `reddit_post_creators` growth and not a resolver-side change.
- **Real sponsorship events: 16 sponsorship-edges (brand_id-resolved) as of
  2026-08-22**, up from 10; 19 brands now (up from 10), still no real
  category/follower/post/verified data on all but 2 (`duroflexworld`,
  `reliancejewels`, which have 1 platform handle each).
- **Real training PAIRS: 54 canonical (event, neighbour) pairs
  (`pair_count.py`, Track A's single shared definition — see that file's
  docstring for why a canonical script now exists), up from 2 two rounds
  ago.** Of those, 34 have a same-platform-computable engagement delta
  (`scripts/compute_training_pair_deltas.py`, which found and fixed two
  real NULL-handling bugs — see `GRAPH_SCHEMA.md`'s 2026-08-22 entry). The
  target tensor is per-creator-node, not per-pair, so those 34 rows
  collapse to **10 distinct labeled creator-nodes** — the honest N for a
  held-out split.
- **Temporal engagement-delta computation: now computed for all 54
  canonical pairs**, not a handful by hand — real relative-lift values,
  full distribution in `GRAPH_SCHEMA.md`. One pair (Virat Kohli, 16 of 34
  rows) is a real but pseudo-replicated outlier dominating any raw average;
  reported separately from the other 9, not silently blended in.
- **Propensity model: now actually exercised, with a real finding.**
  `doubly_robust_weights` (defined since Weeks 3-4) is wired into
  `compute_gail_loss` as of this round. Real result: the propensity head
  saturates to 1.000 on held-out nodes within 50 epochs on the real
  1,289-dim feature space — the overlap assumption is not empirically
  satisfied by this run. *Next lever: normalize/scale creator features
  before the propensity head.*
- **GraphSAGE-vs-GAT: settled**, unchanged this round — GAT forward pass +
  inductive check re-passed on the new, much denser (giant-component)
  topology, no assumption it would generalize from the prior shape.
  Fallback custom weighted layer still exists (`ml/weighted_sage_conv.py`)
  if GraphSAGE is ever wanted for unrelated reasons (large-scale neighbor
  sampling).
- **`NUM_BRAND_CATEGORIES = 5` (in `ml/schema.py`): a placeholder.** *Needs
  a decision from Track A* — `brands.category` is free-text/nullable with
  no fixed taxonomy defined yet.
- **`reputation_score`: no data source anywhere.** *Unowned gap* — flagged
  by Track C's own feature-store code, not fabricated here. No track has
  claimed it.

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
2. `git status` (expect clean) and `pytest tests/` fresh (expect 68
   passing, ~20-30s) — standard self-check.
3. **Re-run `pair_count.py` (Track A) fresh against a live pull, then
   `scripts/compute_training_pair_deltas.py`** — 54 canonical pairs as of
   2026-08-22, growing fast; re-check every round. Feed the deltas output
   into `scripts/train_holdout_round3.py` (or its successor).
4. **The per-node target design is now the binding constraint, not the
   pair count.** 54 canonical pairs collapsed to 10 distinct labeled nodes
   this round because the target is one scalar per creator, not per pair —
   redesigning toward a per-(event, neighbour) target (e.g. a
   pair-indexed loss instead of a node-indexed one) would use Kohli's 16
   rows as 16 real signals instead of 1, likely the single highest-leverage
   change available right now, bigger than growing the pair count further.
5. **Propensity saturation found this round** — normalize/scale creator
   features before the propensity head; re-check whether propensity scores
   spread out across [0.05, 0.95] instead of collapsing to an extreme.
6. **Sufficiency bar:** 54 canonical pairs clears the ~50-100
   thesis-defensible tier on the pair-COUNT question, but the effective
   held-out-evaluable N is still ~10, one of which is a dominant outlier.
   Real evidence the pipeline works on real data now exists; a
   generalizable-model claim still doesn't. Don't inflate this round's LOO
   result (67.19 MSE, ~99% driven by one fold) into a validated result —
   report the outlier-excluded comparison (~14% better than baseline on 9
   folds) as the honest read.
7. Update `GRAPH_SCHEMA.md` and this file together with whatever you find —
   both are living docs, not append-only logs; correct stale sections
   rather than only adding new ones.
