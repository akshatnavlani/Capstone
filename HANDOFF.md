# Handoff — Track B (ML-Core)

Start here. Last updated 2026-08-15, end of Phase 1's Track B step (per
`CAPSTONE_NEXT_STEPS.md` §6 "Sequential relay" — the orchestrator's living
plan doc at repo root, now the project's actual source of truth; read that
file first, every session, before this one). If you're a fresh session with
no memory of prior conversations, read `CAPSTONE_NEXT_STEPS.md`, then this
file, then `GRAPH_SCHEMA.md` (the full technical spec, kept current every
round) for depth on any item below.

## What changed this round (2026-08-15)

**The 0-real-edges/0-real-sponsorships blocker that paused every round since
Weeks 9-10 is cleared** — Track A/C's work landed 10 real collaboration
pairs and 18 real sponsorship events (10 with `brand_id`). Re-verified live
via direct SQL before trusting `CAPSTONE_NEXT_STEPS.md`'s numbers; they
matched exactly. Built the **first real HeteroData end-to-end** (real CLIP+
BERT creator features, real brand features, real collaborates_with/sponsors
edges), ran the GAT forward pass + inductive check against it (passed, no
NaN), and attempted real training. Full detail, numbers, and the direct
sufficiency call are in `GRAPH_SCHEMA.md`'s newest "Real-data status"
section (2026-08-15) — summary:

- **Real graph is small and 74.6% isolated** (47 of 63 creators, degree 0)
  — a confirmed structural property of the curated set (Track A tested and
  disproved "more coverage helps"), not a bug.
- **GAT + inductive property hold on real topology**, not just real
  features — new, since prior rounds only had real features with 0 real
  edges to test structure against.
- **A NEW, more specific blocker was found, not the same old one:** even
  though 10 real sponsorship events + 10 real collaboration pairs now
  exist, **zero real (treatment, neighbor-outcome) training pairs are
  actually computable today.** The 2 sponsored creators who have a
  graph-connected neighbor (Kohli, Ronaldo) each have collaborators whose
  dated posts fall entirely AFTER the sponsorship event — none straddle it,
  because per-creator scraping depth only reaches back 1-3 months. The
  temporal engagement-delta computation itself is simple (before/after
  aggregation) and was exercised with a placeholder target to confirm the
  training loop runs clean on real sparse structure (50 epochs, no NaN) —
  but that run is explicitly NOT a real result, per this round's own
  instruction not to stub-and-call-real. Real training is still blocked,
  just on a narrower, better-understood thing now.
- **Direct sufficiency answer (Phase 1's ask):** not sufficient yet — and
  the reason is that specific 0-real-pairs finding, not merely "N=10 is
  small." Worth flagging to the orchestrator for `CAPSTONE_NEXT_STEPS.md`'s
  P0.4/P2 items, since "does the neighbor's data actually straddle the
  event" wasn't previously checked as its own requirement.
- New script this round: `scripts/build_real_hetero_data.py` — reusable for
  the next check (re-run once Track A's scraping depth grows or new events
  land with time for a "before" window to accumulate after them).

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
is validated against real scraped data (63 real creators as of this round).
**68 tests pass** (`pytest tests/`, ~20-30s). As of 2026-08-15, the full
GAIL pipeline has also been run once against **real** creators/brands/
edges/events end-to-end (`scripts/build_real_hetero_data.py`) — the GAT
forward pass and inductive check are real results; the training-loop run is
a plumbing check only (placeholder target, see below), not a real result
yet. Bot detection (`ml/bot_detection.py`) is separately complete and
unrelated to the training-loop work.

## Open items (tagged with why)

- **Real collaboration edges: 10 real pairs (20 directed edges) as of
  2026-08-15.** *Was blocked on Track A, now cleared* — confirmed via
  direct SQL this round, matches `CAPSTONE_NEXT_STEPS.md` and two other
  tracks' independent counts exactly. Structurally sparse (74.6% of 63
  creators isolated) — a confirmed property of the curated set, not a
  coverage gap (Track A tested and disproved "more scanning helps").
- **Real co-occurrence edges: still 0.** Re-confirmed this round via the
  live `/feature-store/edges/co-occurrence` endpoint. `reddit_post_creators`
  still has no post linked to 2+ creators.
- **Real sponsorship events: 18 confirmed (`is_sponsored=true`), 10 with
  `brand_id` resolved.** *Was blocked, now cleared* — re-verified this
  round via direct SQL and Track C's `/feature-store/edges/sponsorships`
  (returns exactly the 10 brand_id-resolved rows). 8 distinct creators are
  "sponsored" by the broader (any is_sponsored) definition.
- **Real training PAIRS (treatment + measured neighbor outcome): 0,
  confirmed this round — the actual current blocker, more specific than
  the old "0 sponsorships" one.** Of the 8 sponsored creators, only 2
  (Kohli, Ronaldo) have a graph-connected collaborator at all; for both,
  every one of that collaborator's dated posts falls entirely AFTER the
  sponsorship event date — none straddle it, so no real before/after delta
  exists to compute. Root cause is scraping depth (1-3 months back per
  creator), not a missing computation. Re-check as Track A's scraping
  continues to accumulate depth, or as more time passes after existing
  events. See `GRAPH_SCHEMA.md`'s 2026-08-15 entry for the full per-pair
  detail table.
- **Temporal engagement-delta computation: still not built as reusable
  code**, but no longer purely hypothetical — this round confirmed exactly
  what data shape it needs (dated posts straddling an event) and confirmed
  that shape doesn't exist yet for any real pair. Build it for real the
  moment one real straddling pair exists; a placeholder (all-zero target)
  was used this round only to plumbing-test the training loop, explicitly
  not presented as a real result.
- **Propensity model real-fitting: not started.** *Blocked on real
  treated/untreated examples* — architecturally ready
  (`PropensityScoreModel` in `ml/causal_regularization.py`), just has
  nothing real to fit against yet.
- **GraphSAGE-vs-GAT: now settled, not just provisional.** Staying on GAT
  for production is accepted and PROJECT_PLAN.md Section 3a already
  reflects it. Real-feature-value validation was done Weeks 7-8; real-
  graph-structure validation (the missing piece) landed this round —
  `scripts/build_real_hetero_data.py` ran the GAT forward pass and the
  inductive (new-node) check against the real 63-creator/10-pair graph,
  both passed with no NaN. A fallback custom weighted layer still exists
  (`ml/weighted_sage_conv.py`) if GraphSAGE is ever wanted for unrelated
  reasons (large-scale neighbor sampling), but there's no open validation
  question left blocking the GAT choice.
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
3. **Re-check the specific gap this round found: does any real sponsored
   creator's collaborator now have a dated post straddling the event?**
   Re-run `scripts/build_real_hetero_data.py`'s delta-probe logic (or the
   whole script) against a fresh live pull — this is the ONE thing standing
   between "plumbing checked" and "real training result." If yes even for
   one pair: build the real temporal engagement-delta computation for real
   (the shape is now known — before/after aggregation of `like_count`/
   `comment_count` around `posted_at`) and replace the placeholder target.
4. **If it's still 0 straddling pairs:** no real training progress is
   unblocked. Reasonable filler: early prep for Sentiment Propagation
   (same "de-risk against dummy data early" pattern), or report status
   plainly — don't manufacture busywork. Consider flagging to the
   orchestrator whether Track A should prioritize scraping-depth (older
   posts) for the handful of graph-connected creators specifically, since
   that's the actual unblock now, not general breadth.
5. Update `GRAPH_SCHEMA.md` and this file together with whatever you find —
   both are living docs, not append-only logs; correct stale sections
   rather than only adding new ones.
