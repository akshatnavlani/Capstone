# Handoff — Track B (ML-Core)

Start here. Last updated 2026-08-17. Read `CAPSTONE_NEXT_STEPS.md` at repo
root FIRST, every session (`git pull origin main` — it lives on `main`,
rewritten frequently, supersedes this file and memory when they disagree),
then this file, then `GRAPH_SCHEMA.md` (the full technical spec, kept
current every round) for depth on any item below.

## What changed this round (2026-08-17)

**Base graph grew substantially since 2026-08-15** (259 creators, 161
resolved collaboration pairs, 32 sponsorship events — up from 63/10/18 —
re-verified live via direct SQL before building on it, matched
`CAPSTONE_NEXT_STEPS.md` P0.2/P0.4 exactly). Built
`scripts/find_computable_training_pairs.py` to check **all 32 events**
against the graph (only 1, mrbeast→CarryMinati, had been individually
confirmed before) and re-ran `scripts/build_real_hetero_data.py` against
the new 259-creator graph with real (not placeholder) targets. Full detail
in `GRAPH_SCHEMA.md`'s newest "Real-data status" section — summary:

- **Real computable training pairs: 2 distinct events (mrbeast, Cristiano
  Ronaldo), 5 (event, neighbor, platform) triples, 2 distinct neighbor
  creators (CarryMinati, LeBron James) with a real, non-placeholder target
  value.** Up from 1 known / 0 systematically-checked. Real numbers (avg
  engagement before/after, by platform) are in `GRAPH_SCHEMA.md`.
- **Graph structure changed shape, not just size:** 36.3% isolated (was
  74.6%), 12 non-trivial components (was 6), largest component now 53
  nodes (was 6) — degree distribution now has real hubs up to degree 18.
- **GAT + inductive check re-passed on the new, denser topology** — no
  assumption that the first pass generalized; re-run and re-confirmed.
- **First real (non-placeholder) training run** — 2 real target values is
  still a pipeline-correctness check, not a trained model (see Task 6 /
  sufficiency call below), but it's a genuine step up from the all-zero
  plumbing-only run last round.
- **Direct sufficiency call: still too early for any generalization claim.**
  2 real training examples is far below even the ~20-30 floor for a
  legitimate held-out split, let alone ~50-100 for a defensible thesis
  claim. See `GRAPH_SCHEMA.md` for the full reasoning and what would close
  the gap.
- New script this round: `scripts/find_computable_training_pairs.py` —
  the reusable, systematic version of the manual check; re-run every round
  to track the real pair count as data grows.

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
round). **68 tests pass** (`pytest tests/`, ~20-30s). The full GAIL
pipeline has now been run twice against **real** creators/brands/edges/
events end-to-end (`scripts/build_real_hetero_data.py`) — GAT forward pass
and inductive check are real results both times; the training-loop run now
has 2 real (non-placeholder) target values (2026-08-17, up from an
all-zero plumbing-only run 2026-08-15) but is still a pipeline-correctness
check, not a trained model — see Open Items and the sufficiency call in
`GRAPH_SCHEMA.md`. Bot detection (`ml/bot_detection.py`) is separately
complete and unrelated to the training-loop work.

## Open items (tagged with why)

- **Real collaboration edges: 161 real pairs (322 directed edges) as of
  2026-08-17**, up from 10 two rounds ago. *P0.2's "structurally sparse"
  finding was retracted by the orchestrator* — the graph wasn't sparse, its
  endpoints just weren't promoted to `creators` yet; bulk-promoting the
  reviewed sheet backlog converted 142 dangling rows into real pairs with
  zero new scraping. 36.3% of 259 creators are still isolated (was 74.6%),
  12 non-trivial components (was 6), largest now 53 nodes (was 6).
- **Real co-occurrence edges: still 0.** Re-confirmed this round via the
  live `/feature-store/edges/co-occurrence` endpoint. `reddit_post_creators`
  still has no post linked to 2+ creators.
- **Real sponsorship events: 32 confirmed (`is_sponsored=true`), 10 with
  `brand_id` resolved**, up from 18/10. 13 distinct creators are
  "sponsored" by the broader (any is_sponsored) definition.
- **Real training PAIRS (treatment + measured neighbor outcome): 2 distinct
  events / 5 (event, neighbor, platform) triples / 2 distinct neighbor
  creators, confirmed this round via
  `scripts/find_computable_training_pairs.py` checking all 32 events**, up
  from 0 (1 known-but-unsystematically-checked). mrbeast→CarryMinati
  (Instagram + Reddit) and Cristiano Ronaldo→LeBron James (Reddit) both
  have real dated content straddling the sponsorship event. The other 30
  events fail either the graph-connection test or the straddling test (28
  of 32 events have no `posted_at` at all — a separate, larger gap than
  straddling). See `GRAPH_SCHEMA.md`'s 2026-08-17 entry for the full table
  with real before/after engagement numbers.
- **Temporal engagement-delta computation: now real, not placeholder, for
  the first time** (`scripts/build_real_hetero_data.py`'s
  `load_real_targets`) — relative engagement lift `(after-before)/(before+1)`
  per computable triple, averaged per neighbor creator. Still only 2
  creators have a real value; everyone else is 0 ("no signal computed", not
  "confirmed zero"). Re-run every round as more events/edges land.
- **Propensity model real-fitting: not started.** *Blocked on real
  treated/untreated examples with enough N* — architecturally ready
  (`PropensityScoreModel` in `ml/causal_regularization.py`), 13 treated
  creators exist now but with only 2 real outcomes, fitting would be
  meaningless.
- **GraphSAGE-vs-GAT: settled.** Real-graph-structure validation re-passed
  this round on the new, much denser topology (not assumed to generalize
  from the sparser first pass) — no open validation question left blocking
  the GAT choice. Fallback custom weighted layer still exists
  (`ml/weighted_sage_conv.py`) if GraphSAGE is ever wanted for unrelated
  reasons (large-scale neighbor sampling).
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
3. **Re-run `scripts/find_computable_training_pairs.py` fresh against a
   live pull** — the real pair count (2 events / 5 triples as of
   2026-08-17) is the single most important number to re-check every
   round; it's grown every round so far and there's no reason to assume
   it's stable. Feed the output into `scripts/build_real_hetero_data.py`.
4. **28 of 32 events have no `posted_at` at all** — a bigger, more
   tractable lever than straddling depth: fixing/backfilling event dates
   (Track A/C's side) could unlock checking many more events at once,
   versus waiting for scraping depth to grow slowly. Worth flagging to the
   orchestrator.
5. **Sufficiency bar for real progress:** per this round's reference
   points (~20-30 pairs for a legitimate held-out split, ~50-100 for a
   defensible thesis claim), 2 is still far below either. Don't attempt a
   real held-out evaluation or trained-model claim until re-running step 3
   shows meaningfully more. Reasonable filler while waiting: early prep for
   Sentiment Propagation (same "de-risk against dummy data early" pattern).
6. Update `GRAPH_SCHEMA.md` and this file together with whatever you find —
   both are living docs, not append-only logs; correct stale sections
   rather than only adding new ones.
