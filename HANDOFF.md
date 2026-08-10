# Handoff — Track B (ML-Core)

Start here. Last updated 2026-08-10, end of a Weeks 14-16 check-in round
(no new build — see "What changed this round" below). If you're a fresh
session with no memory of prior conversations, read this file first, then
`GRAPH_SCHEMA.md` (the full technical spec, kept current every round) for
depth on any item below.

## What changed this round (2026-08-10 check-in)

Nothing built — this was a live-data re-verification round per the prior
handoff's step 2, plus doc updates. Findings:

- **Re-verified live against the Supabase DB directly** (not from any
  track's docs): collaboration edges still 0, co-occurrence edges still 0
  (346 `reddit_post_creators` rows, 0 shared across creators), sponsorships
  still 0 (695 total content rows, `is_sponsored=true` count 0). Kohli/
  Agilitas unchanged — still truncated at 100 chars, still `is_sponsored=
  false`, Instagram not yet re-scraped since Track A's caption-fix commit
  landed. Full detail in `GRAPH_SCHEMA.md`'s newest "Real-data status"
  section.
- **A concurrent Track C session verified the identical result the same
  day** (their `track_c_backend_weeks14_16` memory) — two independent
  live-DB checks agree, so this isn't a single-session artifact.
- **Found (not yet actionable): `main` has an unmerged PROJECT_PLAN.md
  revision** (2026-08-10) pivoting Section 1 to breadth-over-depth (~1,000
  curated creators at 200-400 datapoints each, down from ~15 creators at
  1,000+ each), explicitly targeting the zero-collaboration-edges blocker
  this doc has carried for 6+ rounds. Not merged into any track branch yet,
  and Track A's actual HANDOFF.md (2026-08-12, newest doc of any track)
  still describes working the old 15-creator list — so the pivot is a plan
  decision, not yet an operational reality. User's direction this round:
  flag it, don't chase it. Worth checking again next round.

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
is validated against real scraped data (16 real creators as of the last
check). **68 tests pass** (`pytest tests/`, ~20-30s). What doesn't work
yet: nothing can be trained on real data, because the live DB has 0 real
collaboration/co-occurrence edges and 0 confirmed real sponsorship events —
see Open Items. Bot detection (`ml/bot_detection.py`) is separately
complete and unrelated to the training-loop work.

## Open items (tagged with why)

- **Real collaboration edges: 0.** *Blocked on Track A* —
  `creator_related_accounts` "frequent_collaborator" data isn't populated.
- **Real co-occurrence edges: 0 as of my last direct check (2026-08-10).**
  *Needs re-verification, not a trusted claim* — Track C's own memory
  claims this "self-healed after Track A's data purge," but I have not
  independently re-checked that since it was written. **Don't trust either
  number without a fresh live check** (see Next Steps).
- **Real sponsorship training pair: 0 confirmed.** *Blocked on a backfill,
  not a bug* — one real brand-linked post exists (Virat Kohli/Agilitas,
  genuine partnership caption) but its stored caption is truncated at
  exactly 100 characters (a scraper limitation Track A already fixed *going
  forward*, but the existing row was never re-scraped). `is_sponsored` is
  `false` on it as a result. Will resolve itself once that post (or a
  similar one) gets re-scraped, or Track C backfills it.
- **Temporal engagement-delta computation: not started.** *Genuinely
  blocked, and the single biggest remaining piece* — GAIL needs
  `(creator, timestamp, engagement before, engagement after)` around a real
  sponsorship event to build real training pairs; nothing computes this
  yet, and it can't be meaningfully dummy-data-tested (the whole point is
  real temporal signal). Build this the moment a real sponsorship event
  exists.
- **Propensity model real-fitting: not started.** *Blocked on real
  treated/untreated examples* — architecturally ready
  (`PropensityScoreModel` in `ml/causal_regularization.py`), just has
  nothing real to fit against yet.
- **GraphSAGE-vs-GAT: provisionally decided, not 100% closed.** Staying on
  GAT for production is accepted and PROJECT_PLAN.md Section 3a is already
  updated to reflect it. Real-*feature-value* validation is done. Real-
  *graph-structure* validation is still pending — needs real edges to exist
  first (see above). A fallback custom weighted layer exists either way
  (`ml/weighted_sage_conv.py`) if GraphSAGE ever becomes wanted for
  unrelated reasons (large-scale neighbor sampling).
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

1. `git status` (expect clean) and `pytest tests/` fresh (expect 68
   passing, ~20-30s) before anything else — standard self-check, do this
   even though last round left things clean.
2. `git fetch origin` and read Track A's `DATA_COLLECTION_STATUS.md` +
   Track C's `API_CONTRACTS.md` in full, not just diffed — re-verify the
   real collaboration/co-occurrence edge counts and the Kohli/Agilitas
   status **live**, not from this file or from other tracks' memory. Ask
   the user for the Supabase `DATABASE_URL` if a live pull is needed (see
   Lesson 5) — it changes each session, was never persisted.
3. **If real collaboration or co-occurrence edges now exist** (even a
   handful): re-run `scripts/validate_gat_on_real_data.py` — this is the
   one thing standing between "provisional" and "settled" on the
   GAT-vs-GraphSAGE decision. May need updating to also pull co-occurrence
   edges (it currently only pulls `collaborates_with`).
4. **If a real sponsorship event now exists** (`is_sponsored=true` with a
   real `brand_id`): this is the trigger to start building temporal
   engagement-delta computation — the biggest remaining gap before any
   real training can happen. Don't build it against dummy data first; the
   whole point is real temporal signal.
5. **If neither of the above has changed**: no urgent data-dependent work
   is unblocked. Reasonable filler: early prep for Weeks 14-15's Sentiment
   Propagation model (following the same "de-risk against dummy data
   early" pattern used for the causal regularization and training-loop
   work), or just report status plainly if genuinely nothing moved — don't
   manufacture busywork.
6. Update `GRAPH_SCHEMA.md` and this file together with whatever you find —
   both are living docs, not append-only logs; correct stale sections
   rather than only adding new ones.
