# GAIL Branch: Heterogeneous Graph Schema

Owner: Track B (ML-Core). Source: `ml/schema.py` (this doc mirrors that code —
if they ever disagree, the code is authoritative). Implements
PROJECT_PLAN.md Section 3a.

Validated end-to-end against synthetic data (`ml/dummy_data.py`,
`tests/test_schema.py`) with a basic GAT forward pass, AND (as of Weeks
7-10) against real data pulled from the live DB via Track C's
feature-store API — see "Real-data status" near the end of this doc for
current row counts and what's still missing before real GAIL training can
start.

## Node types

### `creator`

Feature vector = CLIP embedding ++ BERT embedding ++ metadata, dim **1289**:

| Segment | Dim | Source |
|---|---|---|
| CLIP embedding | 512 | `openai/clip-vit-base-patch32` pooled image embedding of representative thumbnail(s) |
| BERT embedding | 768 | `bert-base-uncased` pooled embedding of scrubbed post/bio text |
| `log_subscriber_count` | 1 | log-scaled per PROJECT_PLAN.md Section 2 metric scaling |
| `engagement_rate` | 1 | |
| `reputation_score` | 1 | |
| category one-hot | 6 (`NUM_CATEGORIES`) | matches Track A's `creators.category` enum exactly (confirmed 2026-08-08): `athlete \| team \| league \| fitness_influencer \| lifestyle_influencer \| other` |

### `brand`

**Rewritten 2026-08-09 against Track A's real `brands` table** (migration
`20260809010000_add_brands.sql`, confirmed live). Metadata only, dim **9**:

| Segment | Dim | Source |
|---|---|---|
| `log_follower_count` | 1 | `brands.follower_count`, log-scaled to match creator metadata convention |
| `log_post_count` | 1 | `brands.post_count` |
| `is_verified` | 1 | `brands.is_verified` |
| `num_platforms_present` | 1 | count of non-null `youtube_handle`/`instagram_handle`/`reddit_handle` (0-3) |
| category one-hot | 5 (`NUM_BRAND_CATEGORIES`, **placeholder**) | `brands.category` is free-text/nullable ("industry/vertical") with no fixed enum yet — NOT the same taxonomy as `CREATOR_CATEGORIES` |

**Structural gap vs. `creator` (1289-dim), not a bug:** Track A's real
`brands` table has **no text/bio field at all** — their scope is "basic
profile data" (category, follower/post counts, verification, handles), not
brand content the way creator posts/captions are characterized. So there is
currently no source for CLIP or BERT features on brand nodes, under the
current (deliberately bounded) scraping scope. If the thesis later needs
richer brand features, that requires Track A scraping brand post
content/bio text — a real scope question, not something to invent
client-side. `NUM_BRAND_CATEGORIES` is still a placeholder pending Track
A's real category taxonomy (open item below).

Zero real rows in the DB yet, but for a more precise reason than "still
blocked": Track A's 2026-08-09 update shows all three platforms' scraping
*mechanisms* now proven end-to-end with real pilot calls (YouTube API key
live, Instagram/Reddit via a real logged-in Chrome + OpenCLI, real
comment/post yields measured) — the remaining gap is that the orchestrator
that writes scraped results into the shared Supabase DB isn't wired up yet
("Wire the orchestrator's platform-call TODOs" is still an open item on
their side). So bulk collection is not "still blocked" so much as "proven
but not yet flowing into the DB" — dummy data is still the correct
validation method for now, but this is likely to change soon; worth
re-checking every session, not just once.

## Edge types

| Edge type | Direction | Weighted? | Meaning |
|---|---|---|---|
| `(creator, collaborates_with, creator)` | both directions populated | yes (`edge_attr`, scalar) | collaboration frequency between two creators |
| `(creator, co_occurs_with, creator)` | both directions populated | yes (`edge_attr`, scalar) | platform co-occurrence (shared platforms / joint appearances) |
| `(brand, sponsors, creator)` | brand → creator | no | treatment edge; existence derived from `is_sponsored` disclosure-tag labeling. `is_sponsored` is currently **nullable/unpopulated** (Track C's Weeks 7-8 labeling pipeline, not built yet — confirmed, don't build a separate labeler against raw text meanwhile). Brand-identity gap resolved (real `brands` table exists), but 0 real brand rows and 0 real sponsorship edges as of 2026-08-09 — both expected at this stage, not a new problem. |
| `(creator, sponsored_by, brand)` | creator → brand (reverse of `sponsors`) | no | required so PyG can message-pass into brand nodes; not a separate data source, just the transpose |

Both directions of `collaborates_with` / `co_occurs_with` must be populated
explicitly (Track B does not apply `ToUndirected()` at load time) — if
creator A collaborated with creator B, both `(A,B)` and `(B,A)` edges should
be present with the same weight.

## Why GAT over GraphSAGE (for this smoke test) — and whether the swap is even needed

PROJECT_PLAN.md Section 3a names both as acceptable backbones and gives
GraphSAGE a specific rationale: *"Inductive setting: GraphSAGE-style
inductive aggregation so new influencer nodes can get embeddings without a
full retrain."* GAT was used for the Week 1-2 schema-validation model
(`ml/model.py`) because its attention coefficients directly implement
GAIL's "personalized spillover weight per collaborator" (GAIL working-doc
Step 6).

**Swap-cost check (2026-08-09):** verified empirically — `torch_geometric.nn.SAGEConv`
has no `edge_attr`/`edge_dim` parameter at all (confirmed via signature
inspection and by reproducing the `TypeError` when passing `edge_attr` into
a `HeteroConv`-wrapped `SAGEConv`). GAT's weighted-edge handling in
`ml/model.py` depends entirely on `edge_dim`, which GraphSAGE has no
equivalent for.

**Re-examined 2026-08-09, per the user's request to check for a middle
option before treating "custom layer needed" as settled.** Question asked:
is GraphSAGE's cited rationale (inductive, no-retrain-for-new-nodes) even a
real reason to swap away from GAT, given GAT already has `edge_attr`
support? **Finding: no, PROJECT_PLAN's stated rationale doesn't force a
swap.** GAT is *also* inductive — this isn't a guess, it's the headline
result of the original GAT paper (Veličković et al. 2018), which evaluates
on the inductive PPI benchmark (train on one set of graphs, test on
completely unseen ones). Verified two ways here, not just cited:
1. **Structural check:** `GATConv`'s only learnable parameters are
   `att_src`, `att_dst`, `lin.weight`, `bias` — all shape-fixed, none
   indexed by node identity. Same category of parameterization as
   `SAGEConv`'s `lin_l`/`lin_r`. Neither layer holds a per-node lookup
   table, which is the actual structural reason either one generalizes to
   unseen nodes.
2. **Empirical check:** ran the exact same trained `SchemaSmokeTestGAT`
   instance — no retraining — first on a 6-creator/3-brand dummy graph,
   then on an unrelated 20-creator/8-brand graph. Correct output shapes
   both times, same module, zero errors.

**Revised conclusion:** a custom `MessagePassing` layer is **not
definitely required** — "avoid the swap entirely, stay on GAT for
production" is a legitimate option, not just a fallback. GraphSAGE's real
remaining edges over GAT are unrelated to inductive capability: neighbor
*sampling* for scalability to very large graphs (probably not needed at
this thesis's scale — thousands, not millions, of nodes) and mean
aggregation's potentially different robustness properties when node degree
varies a lot (a mega-influencer with thousands of collaborators vs. a niche
creator with a handful) — a modeling-quality question, not an architecture
necessity. **This changes PROJECT_PLAN.md Section 3a's stated rationale and
is a thesis-level architecture call — flagging for the user's judgment,
not deciding unilaterally to drop GraphSAGE from the plan.**

**Prototype built anyway** (`ml/weighted_sage_conv.py`, `WeightedSAGEConv`,
tested in `tests/test_weighted_sage_conv.py`), per the Weeks 5-6 ask to
de-risk this regardless of whether it turns out to be necessary — a small
custom `MessagePassing` layer (self-transform + edge-weight-scaled
mean-aggregated neighbor transform) that *does* consume `edge_attr`,
unlike stock `SAGEConv`. Validated: produces correct shapes on dummy data,
edge weight demonstrably changes the output (proving it's actually
consumed, not silently ignored), and — same inductive check as GAT above —
the same trained instance generalizes to a graph with more nodes without
retraining. Not production-ready (no bias/normalization options,
unbenchmarked for accuracy) — confirms the approach works structurally, no
more. The data contract (`ml/schema.py`'s scalar `edge_attr`) is unaffected
by any of this either way.

**Real-data validation (2026-08-09) — settles the open item above.** The
Weeks 5-6 inductive-generalization check used only synthetic dummy data
(scaled 6→20 nodes); re-run against real data per the user's request, since
"good evidence" isn't "real-data evidence." Pulled real data via Track C's
live `/feature-store/*` endpoints (against the real Supabase DB — user
shared the connection string for this session only, never committed or
written to memory) and ran `scripts/validate_gat_on_real_data.py`:
- **3 real creators** (`athleanx`, `kingjames`, `lebron`), real feature
  values (real subscriber counts, real 42k-character channel description
  text, real YouTube thumbnail URLs fetched and CLIP-embedded, real `None`
  metadata for two mostly-empty stub rows) — model produced correct
  `(3, 16)` output, no NaNs, no crashes.
- **Same trained model instance**, no retraining, then run on the 3 real
  creators plus 10 synthetic ones appended — correct `(13, 16)` output.
- **Honest limitation, not fully closed:** real collaboration-edge data is
  currently **0 edges** (Track A's `creator_related_accounts`
  "frequent_collaborator" rows aren't populated for these 3 creators yet —
  this is a data-collection gap, not evidence these creators have no real
  collaborators). So this validates the finding against real *feature
  values*, not yet against real *graph structure* — worth re-running once
  Track A has real collaboration edges for at least a few creators.

**Found and fixed a real bug in the process:** `ml/dummy_data.py`'s
`make_dummy_hetero_data(num_brands=0, ...)` crashed
(`torch.randint(0, 0, ...)` is invalid) — needed for this real-data test
since 0 real brands exist. The sponsor-edge generation forced a minimum of
1 edge even with zero brands to reference it. Fixed (skip sponsor-edge
generation entirely when `num_brands == 0`); regression test added
(`tests/test_schema.py::test_dummy_hetero_data_with_zero_brands_does_not_crash`).

## CLIP + BERT feature extraction (prepped early from Weeks 9-10)

`ml/feature_extraction.py` — built against Track C's real
`CreatorFeatureRecord` contract (`raw_text`, `thumbnail_urls`), not guessed.
Two real integration findings from testing against the real 3-creator
sample, both fixed here rather than left to surprise Weeks 9-10 at volume:
1. **`transformers` 5.14.1's `CLIPModel.get_image_features()` doesn't
   return a plain tensor** — it returns a `BaseModelOutputWithPooling`;
   the actual embedding is `.pooler_output`. Most CLIP tutorials assume the
   old plain-tensor return; verified the real shape empirically against a
   real YouTube thumbnail before trusting it.
2. **Real feature-store rows have partial `None` metadata** — of 3 real
   creators, one is a fully empty stub (no subscriber count, no text, no
   thumbnails at all) and another has metadata but zero content.
   `ml/schema.py`'s tensor contract has no room for `None`; handled by
   zero-filling missing numeric fields, a real (documented, not hidden)
   modeling choice — a creator with genuinely zero engagement is currently
   indistinguishable from one whose engagement was never measured.

Tested with mocked network calls but real model inference
(`tests/test_feature_extraction.py`, 7 tests, ~65s — real CLIP+BERT loads
are the cost, not slow test logic).

## Causal regularization (pulled forward from Weeks 5-6)

`ml/causal_regularization.py` implements the three PROJECT_PLAN.md Section 3c
regularization terms as standalone, tested primitives (not yet wired into a
training loop — no GAIL predictor exists yet to regularize):
- `PropensityScoreModel` + `overlap_penalty` + `doubly_robust_weights` —
  logistic-regression/small-MLP propensity model, overlap violation penalty,
  and inverse-propensity correction weights for selection bias.
- `laplacian_smoothness_penalty` — weighted graph-Laplacian quadratic form
  over the `collaborates_with` graph.
- `has_sponsored_neighbor` + `consistency_penalty` — zero-exposure
  constraint for creators with no sponsored collaborators.

Tested against both hand-built small graphs (exact expected values) and the
real `ml/dummy_data.py` HeteroData (`tests/test_causal_regularization.py`).
The end-to-end test derives a stand-in "is_sponsored" signal from the
`sponsors` edge (since real `is_sponsored` labels aren't populated yet) —
noted inline as a placeholder, not a real treatment label source.

## Bot detection (pulled forward from Weeks 7-8)

`ml/bot_detection.py` implements the four PROJECT_PLAN.md Section 2
heuristics — deliberately not a trained classifier (no labeled ground truth
exists, an intentional simplification): follower/following ratio outliers,
account age, posting-frequency anomalies, engagement-rate-vs-follower-count
mismatch. Combines them into `bot_score` (float, 0-1) and `is_bot_flagged`
(bool via threshold) — matching Track A's reserved `bot_score real` /
`is_bot_flagged boolean` columns exactly. Missing `account_age_days`
(Instagram doesn't expose it) scores as 0/not-suspicious rather than being
excluded or guessed, so an Instagram account isn't penalized for data that
was never available. Tested against synthetic normal and obvious-bot cases
(`tests/test_bot_detection.py`) — thresholds are reasonable defaults, not
fit to real data, since none exists yet; revisit once real profiles land.

## What Track A / Track C actually produce (updated 2026-08-09)

Track C built the DB → feature-store transformation (`backend/app/
feature_store.py`, live at `GET /feature-store/creators` /
`/edges/collaborations` / `/edges/sponsorships`) — Track B doesn't need to
write its own DB-loading code, just consume this API's output shape (see
`ml/feature_extraction.py::RawCreatorRecord`, mirrors their
`CreatorFeatureRecord` exactly). Confirmed working against the real DB
(2026-08-09 session, 3 real creators pulled and embedded successfully).

Two real gaps Track C flagged in their own code (not fabricated by Track
B): **`reputation_score` has no source column anywhere in Track A's
schema** — always `None` from the feature-store, open cross-track item, no
owner yet. **`co_occurs_with` edges have no signal in Track A's schema
either** — no co-starring/tagging table exists, so Track C's feature-store
doesn't build these edges at all (only `collaborates_with`, from
`creator_related_accounts` "frequent_collaborator" rows, currently 0 real
edges for the 3 real creators that exist).

Bot-detection heuristic signals are confirmed available per Track A's
SCHEMA.md and now actually consumed by `ml/bot_detection.py`:
`follower_count`/`following_count` ratio, `account_created_at`
(YouTube/Reddit only — Instagram doesn't expose this), and posting
frequency from `posted_at`/`published_at` timestamps.

## What Track C should expect as output

Confirmed via `origin/track-c-fusion-backend:API_CONTRACTS.md`
(2026-08-08): `POST /scores/compute` expects `spillover_score`,
`sentiment_risk_score`, and `creator_feature_score`, each a float in
`[0, 1]`, one per creator. The GAIL branch (this doc) is responsible for
`spillover_score`; `sentiment_risk_score` comes from the Temporal branch and
`creator_feature_score` from the feature-extraction pipeline (Section 2).
None of these are wired up yet — Track C's endpoint currently accepts
caller-supplied or placeholder `0.5` values. Actual GAIL output lands per
the Weeks 11-15 timeline (Causal Inference combiner validation).

## Open items

- Brand category/industry taxonomy (`NUM_BRAND_CATEGORIES`, currently a
  5-value placeholder) — `brands.category` is free-text/nullable with no
  fixed enum yet; revisit once Track A classifies/fixes a real taxonomy.
- Edge weight semantics (raw counts vs. normalized) for `collaborates_with`
  — currently unspecified pending real data shape from Track A;
  `ml/schema.py` just reserves a scalar `edge_attr` slot.
- **`co_occurs_with` now HAS a data source (resolved 2026-08-22, updated 2026-08-26: 0 → 1414 directed via `reddit_post_creators` junction, 185-node giant).** Was "no source" until Track A's junction landed — now real, verified live via `pair_count` and `scripts/train_prod_model.py` build. `pair_count.py` still draws only from `creator_related_accounts` (REVIEW 2 BACKLOG undercount) — pair count may undercount until co_occurs is included in its adjacency.
- **`reputation_score` has no source column anywhere** (same — confirmed by
  Track C, always `None`). Open, no owner assigned yet.
- **Real-data validation of the GAT/GraphSAGE finding is now real-graph-structure validated (340 collab directed, 1414 co_occurs, 259 creators) as of 2026-08-22/26** — forward pass + inductive (append 15 synthetic nodes, no retrain, no NaN) re-passed on both. See newest Real-data status.
- **GraphSAGE backbone decision — provisionally accepted 2026-08-09,
  PROJECT_PLAN.md Section 3a updated** (see "Why GAT over GraphSAGE"
  above): GAT already satisfies the plan's stated inductive rationale, so
  staying on GAT for production and skipping the swap is accepted, not just
  a fallback. A prototype weighted `MessagePassing` layer still exists
  (`ml/weighted_sage_conv.py`) in case GraphSAGE is wanted later for
  unrelated reasons (large-scale neighbor sampling, degree-variance
  robustness). **Not fully closed:** real-data validation so far covers
  real feature values but not real graph structure — re-run once real edges
  land.
- Brand feature richness is capped by Track A's current bounded scope (no
  brand post/bio content, only profile-level counts) — revisit only if the
  thesis specifically needs richer brand features and Track A's scope is
  deliberately expanded for it.
- **Who computes `is_sponsored`? RESOLVED (2026-08-09) per Track A's
  SCHEMA.md** — Track C owns the labeling pipeline (Weeks 7-8), confirmed
  by the user. Track C's `API_CONTRACTS.md` fix has landed (re-checked
  below) — `is_sponsored`/`sponsorship_raw_matches` are now correctly
  `Optional`/unpopulated in their ingestion schemas, matching Track A's
  real DB. No longer open.

## Real-data status (2026-08-26, prod artifact — train ONCE on ALL pairs, P1.6 unblock)

**Same live graph as 2026-08-22 LOO** — re-pulled via `pair_count.py` + `scripts/train_prod_model.py:1` DB-direct build (not feature-store dump): **259 creators, 19 brands, 340 directed collab edges (170 undirected pairs), 1414 co_occurs_with directed, 16-17 sponsorship edges, 185-node giant component + 2-node pair + 72 isolates (27.8 %)**, max degree 39-40, `checks_evaluated` 138 / `events_total` 53 / `events_yielding` 40. **Canonical pair count unchanged: 54 rows, 23 directed / 19 undirected pairs** (`pair_count.py` fresh import, Track A's single definition).

**Prod vs LOO — what changed beyond the graph staying put.** `scripts/train_holdout_round3.py:1` is LEAVE-ONE-OUT (10 folds, hold out 1 of 10 nodes, 50 epochs/fold) for *evaluation* — headline MSE 67.19 vs 67.36 baseline (>99 % from Kohli outlier). `scripts/train_prod_model.py:1` is the *deployable* path: train **ONCE on ALL 10** labelled nodes (100 epochs, full `train_mask` over all, `doubly_robust_weights` with `treatment`, same `ml/gail_model.py:1` / `ml/training.py:1` / `ml/schema.py:1` stack). **Fixes the two NULL bugs** (`WHERE e1 IS NOT NULL AND e2 IS NOT NULL`, per-platform lift `(after-before)/(before+1)` mean, cross-platform-only 20/54 counted separately) — same fixes as `scripts/compute_training_pair_deltas.py`. **Fixes propensity saturation** (`CAPSTONE_NEXT_STEPS.md:795`, `GRAPH_SCHEMA.md:402`): per-dim z-score `feature_scaler` (mean abs 0.224 std 0.236, std clamped 1e-6) applied as `data["creator"].x = x_norm` so `PropensityScoreModel` sees normalized 1289-dim input.

**Prod calibration (honest, not held-out):** `MSE trained 1.84 vs baseline 67.36` — headline 97 % drop is *not* generalization (no held-out), it is in-sample fit on N=10 and is dominated by Virat Kohli (`target +25.874 pred +21.616 sq_err 18.13` = 98 % of residual sum). Other 9 all sq_err <0.10 (Gurfateh 0.092, Wamiqa 0.063, Mohitt 0.055, ...). LOO 67.19 remains the honest held-out number; prod is for shipment. Propensity now mean 0.61 min 0.00 max 1.00 (was 1.000 on held-out in all 10 LOO folds) — centred, not stuck, but extremes (0, 1) persist at N=10: overlap not fully satisfied, reported as limitation. No NaN. Deterministic (seed 0, `hidden 16 heads 2`).

**Artifact & loader (Track C integration point).** `models/gail_checkpoint.pt` (3.7 MB, git SHA `ef826cd` baked, <100 MB so committed) — `state_dict` + `config` + `feature_scaler` (z-score) + `training_pair_ids` (10) + 4-reading + `graph` (order, names) + `tensors` (creator_x_norm, brand_x, 340/1414 edges, treatment/target) + `training_stats` (per-node, final propensity). `ml/inference.py:1` — `load_predict(creator_id: str) -> {spillover_score, basis: "trained"|"inferred", confidence_low/high}` (`IsolatedCreatorError` for degree 0, `FileNotFoundError` if checkpoint missing) + `load_predict_batch`; **confidence WIDE for small-N** (t 2.306 df=8 × residual_std 1.355 × sqrt(1+1/10) ≈ 3.28 half-width trained, 5.25 inferred, floors 0.15/0.25). GAT inductive for `inferred` (single cached forward pass, no retrain). Verified on live HeteroData: `trained` CarryMinati `0.339 [-2.94,3.62]`, `inferred` abdevilliers17 `1.191 [-4.06,6.44]`, `isolated` _bungy_lover_.01 raises `IsolatedCreatorError`; batch + missing-file also verified. `report.md` at worktree root is the durable trail; `backend/app/routers/scores.py:1` 0.5 placeholder at `deaf630` can now be wired via `load_predict`.

**Sufficiency call unchanged in kind:** 54 rows / 10 nodes clears pair-COUNT bar (~50-100 tier) but N=10 with one pseudo-replicated outlier (16 of 34 rows = same Kohli Reddit jump) is **pipeline/methods validation, not a validated predictive result** for the thesis. Top lever remains per-(event,neighbour) target design (16 real signals vs 1); second lever (propensity norm) now done.

## Real-data status (2026-08-22, Phase 1 round 3 — first genuine held-out training attempt)

Orchestrator flagged this round as different in kind: the canonical pair count
(`pair_count.py`, Track A — one shared definition after two rounds of independent
recomputation disagreeing) is **54**, live-reconfirmed before building on it,
clearing the ~50-100 thesis-defensible tier in `CAPSTONE_NEXT_STEPS.md`, not just
the >=20 floor. First round where a real held-out evaluation is warranted rather
than premature.

**Task 1 — rebuilt the real HeteroData, current state.** Pulled fresh via Track
C's `/feature-store/*` (259 creators, 340 directed collab edges, **1,414
co_occurs_with edges — up from 0 at round 2**, 19 brands (up from 10), 16
sponsorship edges). The co-occurrence jump is the real structural story this
round, bigger than the collaboration-edge growth:

| | round 2 (08-17) | round 3 (08-22) |
|---|---|---|
| isolated nodes | 36.3% | **27.8%** (72/259) |
| non-trivial components | 12 | **2** |
| largest component | 53 nodes | **185 nodes** |
| max degree | 18 | 39 |
| collab edges (directed) | 322 | 340 |
| co_occurs_with edges | 0 | **1,414** |

The graph went from a dozen small clusters to essentially one giant component
(185 of 259 creators) plus a lone 2-node pair — driven almost entirely by
co-occurrence data landing for the first time, not by collaboration-edge growth.
Worth flagging to Track A/C: co-occurrence was reported "still 0" as recently as
2026-08-17's entry below; it clearly isn't anymore, and nothing in this round's
brief flagged that change, so this was caught only by re-pulling the endpoint
live rather than trusting the prior number.

**Task 2 — GAT forward pass + inductive check re-passed on the current
topology.** No NaN on 259 creators/19 brands; same trained instance handled 15
appended synthetic nodes with no retraining. Not assumed to generalize from
round 2's sparser graph — re-run for real.

**Task 3 — computed real before/after engagement deltas for all 54 canonical
pairs (`scripts/compute_training_pair_deltas.py`, imports `pair_count.py`
directly rather than re-deriving the pair definition).** Found and fixed two
real NULL-handling data-quality bugs while doing this, not silently averaged
past:

1. **Fully-unmeasured posts miscounted as zero engagement.** Instagram
   `like_count`/`comment_count` are sparse (28%/40% populated) and the
   population is temporally skewed — most of Virat Kohli's and Anushka
   Sharma's pre-2026 posts have BOTH columns NULL, only their mid-2026 posts
   are populated. Coalescing NULL to 0 fabricated a near-zero "before" baseline
   against a real "after" value, producing multi-million-percent fake lifts.
   Fix: exclude posts where both columns are NULL from the before/after pools.
2. **Partial measurement still biased after fix #1.** Of Instagram's
   measured-or-partial posts, 208 have `comment_count` but NULL `like_count`,
   and zero have the reverse — `like_count` (the dominant-magnitude metric) is
   selectively missing on real posts, not missing at random. Same pattern on
   Reddit (`score` selectively missing, `num_comments` always present). A post
   with only its small metric measured still looked artificially low. Fix:
   require BOTH engagement columns non-null to count a post at all.

After both fixes: **34 of 54 canonical pairs have a same-platform-computable
relative-engagement-lift** `(after_avg - before_avg) / (before_avg + 1)`; the
other 20 satisfy the STRADDLE clause only via different platforms on each side
(e.g. before-activity on Reddit only, after-activity on YouTube only) and have
no same-unit lift to compute — reported separately rather than mixed into one
number. Distribution over the 34: min -0.998, median +0.39, mean +12.07 (mean
pulled hard by one real but pseudo-replicated outlier — Virat Kohli's Reddit
engagement genuinely jumped from near-zero scores across 2023-2025 to real
double/triple-digit scores starting 2026-08-05, and 16 of the 34 rows are all
different Anushka Sharma sponsorship-event anchor dates measuring that SAME
underlying jump, not 16 independent signals).

**Task 4 — leave-one-out held-out evaluation, the first real one.** The target
tensor is one scalar PER CREATOR NODE (transductive), not per (event,
neighbour) pair, so multiple events on the same neighbour collapse to one
averaged target — the honest N for a node-level held-out split is **10
distinct labeled creator-nodes**, not 54 or 34. At N=10, an 80/20 split holds
out ~2 nodes on one random draw with no way to know if that draw was lucky;
leave-one-out uses each of the 10 as the held-out example exactly once (10
folds, fresh model per fold, 50 epochs), the standard choice at this scale.
Also wired `doubly_robust_weights` (defined in `ml/causal_regularization.py`
since Weeks 3-4, never actually called) into `compute_gail_loss` as an opt-in
`treatment` parameter — inverse-propensity-weighted supervised loss, real
doubly-robust correction exercised for the first time, not just a
standalone-tested primitive. Backward-compatible: existing callers/tests
untouched, new test added (`test_treatment_arg_applies_doubly_robust_weighting`).

**Task 5 — calibration, reported honestly:**
- Raw LOO mean squared error: **67.19** across 10 folds, vs. an always-predict-
  zero baseline of 67.36 — a 0.26% "improvement" that is entirely noise: one
  fold (Kohli, target≈+25.87) contributes 668.3 of the total 671.9 squared-error
  sum (>99%). This headline number is not a meaningful result on its own.
- **Excluding the Kohli fold**, the other 9: model mean sq_err ≈0.397 vs.
  baseline ≈0.463 — a real, if modest, ~14% reduction, but N=9 with no formal
  significance test is nowhere close to establishing generalization.
- **Propensity model saturated to 1.000 for the held-out node in all 10
  folds.** The overlap penalty should push extreme propensity scores back
  toward the interior, but a linear+sigmoid propensity head over the real
  1,289-dim creator feature space appears to saturate immediately (classic
  sigmoid-saturation/vanishing-gradient behavior on high-dimensional,
  unnormalized real features) and doesn't recover within 50 epochs. **The
  overlap assumption (no unit's propensity extremely close to 0 or 1) is not
  empirically satisfied by this run** — flagged as a real identification-
  assumption limitation, not glossed over. Doubly-robust weights computed from
  a saturated propensity are unreliable; this caveats the Task 4 result
  further, on top of the small-N and pseudo-replication issues above.
- No NaN in any of the 10 folds.

**Direct sufficiency call.** 54 canonical (event, neighbour) pairs clears the
pair-COUNT bar the orchestrator set. But the current node-level target
architecture collapses that to 10 independent labeled examples, one of which
(Kohli) is a single underlying signal restated 16 times and dominates any
aggregate metric. **This is real evidence the pipeline produces a genuine,
non-trivial, non-crashing result on real data end-to-end — a real training
signal exists, doubly-robust correction is now actually exercised, and there
is a small real (non-outlier-driven) improvement over baseline — but it is
NOT yet a validated, generalizable model.** Reportable in the thesis as
pipeline/methods validation with explicit small-N caveats; not reportable as
a proven predictive result. Two concrete levers, in order: (1) redesign the
target to be per-(event, neighbour) rather than per-node, so Kohli's 16 rows
become 16 genuinely separate training signals instead of collapsing to one
node's dominant value — architecturally the bigger fix; (2) normalize/scale
creator features before the propensity head so it stops saturating.

## Real-data status (2026-08-17, Phase 1 round 2 — systematic pair enumeration, real target)

Base state grew substantially since 2026-08-15 (63→259 creators, 10→161
resolved collaboration pairs, 18→32 sponsorship events, still 10 with
`brand_id`). Re-verified live via direct SQL before building on
`CAPSTONE_NEXT_STEPS.md` P0.2/P0.4's numbers — matched exactly (259
creators; 668 `creator_related_accounts` rows / 161 distinct resolved pairs
via the same ambiguous-handle-dropping resolver logic as Track C's
`build_collaboration_edges()`; 32 events / 10 with `brand_id`).

**Task 1 — enumerated ALL 32 events, not just the one known pair
(`scripts/find_computable_training_pairs.py`).** Only mrbeast→CarryMinati
had been individually checked before. Result:

| # | Sponsored creator | Event date | Neighbor | Platform | Before / After | Avg before → after | Delta |
|---|---|---|---|---|---|---|---|
| 1 | Cristiano Ronaldo | 2026-07-21 | LeBron James | reddit | 17 / 162 | 164.9 → 186.4 | +21.6 |
| 2 | mrbeast | 2026-08-12 | CarryMinati | instagram | 11 / 1 | 929,235.3 → 1,584,116.0 | +654,880.7 |
| 3 | mrbeast | 2026-08-12 | CarryMinati | reddit | 50 / 12 | 554.1 → 517.3 | -36.8 |
| 4 | mrbeast | 2026-08-12 | LeBron James | instagram | 12 / 4 | 245,547.4 → 82,599.8 | -162,947.7 |
| 5 | mrbeast | 2026-08-12 | LeBron James | reddit | 128 / 51 | 197.1 → 152.4 | -44.7 |

**Headline number: 2 distinct events, 5 (event, neighbor, platform)
triples, 2 distinct neighbor creators with a real computable outcome.**
Both real edges verified directly against raw `creator_related_accounts`
rows, not just the resolver's output (LeBron James's own relation rows
literally include the handle `mrbeast`, resolving via mrbeast's real
`instagram_handle`; similarly `cristiano` and `carryminati` resolve via
their own handles).

Of the other 30 events: **28 of 32 have no `posted_at` at all** (a bigger,
more tractable gap than straddling depth — these can't be checked at all
until dated), and the remaining events either have 0 graph neighbors or
neighbors whose dated content doesn't straddle. Full per-event detail in
the script's stdout output (not reproduced here — see HANDOFF.md for how
to re-run).

**Task 2 — rebuilt the real HeteroData on the new 259-creator/161-pair
graph.** Structure changed shape, not just size, vs. 2026-08-15:

| Metric | 2026-08-15 (63 creators) | 2026-08-17 (259 creators) |
|---|---|---|
| Isolated nodes | 47 (74.6%) | 94 (36.3%) |
| Connected components | 53 total, 6 non-trivial | 106 total, 12 non-trivial |
| Largest non-trivial component | 6 nodes | 53 nodes |
| Max degree | 5 | 18 |
| `collaborates_with` edges | 20 | 322 |

Confirms the orchestrator's P0.2 retraction: the graph was never
structurally sparse in the sense implied — its endpoints just weren't
promoted to `creators` yet. Real degree distribution now has genuine hubs
(degree 14-18: LeBron James, mrbeast's collaborator cluster, the
Kohli/PV Sindhu cricket cluster).

**Task 3 — GAT forward pass + inductive check re-run, not assumed to
generalize from the sparser first pass.** Both passed again: forward pass
on 259 creators/10 brands, no NaN; same trained instance ran cleanly on 15
new nodes appended to the real graph, no retraining, no NaN.

**Task 4 — real (not placeholder) engagement deltas computed, for the
first time.** The 5 triples above are genuine before/after averages from
real dated content. `scripts/build_real_hetero_data.py`'s
`load_real_targets` converts each into a relative lift
`(after_avg - before_avg) / (before_avg + 1)` and averages across a
neighbor's triples: CarryMinati ≈ **+0.32** (dominated by the huge
Instagram post-event spike, partly offset by a small Reddit dip), LeBron
James ≈ **-0.25** (mixed: up slightly for Ronaldo's event, down for
mrbeast's, on a small-before/after-count basis). Every other creator (257
of 259) still gets 0 — "no real signal computed," not "confirmed zero."

**Task 5 — training run, framed honestly.** 50 epochs, no NaN/crash
(`prediction`/`overlap`/`smoothness`/`consistency` all finite throughout).
2 real target values is a genuine step up from last round's all-zero
plumbing check, but is **still a pipeline-correctness check, not a trained
model** — 2 labeled nodes cannot support a held-out split, cross-validation,
or any claim about generalization. Loss went from `total=0.0297` (epoch 0)
to `total=0.00087` (epoch 49), but with N=2 this reflects the model
memorizing two numbers, not learning a generalizable spillover function —
stated explicitly so it isn't later mistaken for a real training curve.

**Task 6 — sufficiency call, direct.** Against the round's own reference
points (~20-30 pairs for a legitimate held-out split, ~50-100 for a
defensible thesis-level claim): **2 real pairs is far below either bar.**
Not close to sufficient yet. What would close the gap, in order of
leverage:
1. **Fix/backfill `posted_at` on the 28 dateless events** — this is pure
   data-completeness, not new scraping; even a modest fraction becoming
   checkable could multiply the real pair count without touching the
   graph at all.
2. **Deepen creators already in a resolved pair, not new creators** — per
   the task brief's reference to Track A's own finding that
   pairs-per-post is far higher when deepening already-connected creators
   than random ones (not independently re-verified by this round, taken
   as given context); the 165 creators with >=1 resolved neighbor are the
   highest-leverage deepening targets specifically for straddling data.
3. **More sponsorship events generally** (32 → 300+ is Review 2's own
   target) — raises the base rate of hits from (1) and (2) both.

## Real-data status (2026-08-15, Phase 1 — first real HeteroData built, blocker cleared)

The blocker every prior round in this section reported (0 real edges, 0 real
sponsorships) is cleared. `main`'s CAPSTONE_NEXT_STEPS.md (rewritten by the
orchestrator, pulled fresh this round) reports 18 real `is_sponsored=true`
events (10 with `brand_id` resolved) and 10 real resolved collaboration
pairs, independently reproduced three times by three different sessions
(Track A → orchestrator → Track C). Re-verified live, independently, via
direct SQL against the pooler `DATABASE_URL` before trusting it: confirmed
exactly — 63 creators, 505 `creator_related_accounts` rows / 10 resolved
pairs, 18 `is_sponsored=true` rows / 10 with `brand_id`.

**Built and ran `scripts/build_real_hetero_data.py` — the first real
end-to-end HeteroData, GAT pass, and training attempt this project has had.**
Real creator features (CLIP+BERT via Track C's `/feature-store/creators`),
real brand features (direct DB read — see gap below), real
`collaborates_with` (20 directed edges = 10 pairs), real `co_occurs_with`
(0, unchanged), real `sponsors`/`sponsored_by` (10 edges from
`/feature-store/edges/sponsorships`).

**Real structure:** 63 creators, 10 brands. Degree distribution over the
creator-creator graph (collaborates_with + co_occurs_with combined): 47
nodes degree 0, 15 nodes degree 1, 1 node degree 5 (Virat Kohli — hub of 4
of the 10 pairs). **74.6% of creators (47/63) are isolated nodes.** 53
connected components total, 6 non-trivial (all size 2 except Kohli's, size
6: PV Sindhu/Kohli/anushkasharma/karanaujla/royalchallengers.bengaluru/
sporting.beyond). This is the confirmed real shape of the curated set per
CAPSTONE_NEXT_STEPS §2 — Track A tested and disproved the "more coverage
closes it" hypothesis (267 more posts scanned, 0 new resolved pairs). Not a
pipeline bug to chase.

**GAT forward pass + inductive check: PASSED on real topology.** No NaN on
real features + real sparse structure (0-edge `co_occurs_with` relation
included). Same trained instance, no retraining, ran cleanly on 15 synthetic
nodes appended to the real 63/10 graph — the inductive property (Weeks 7-8's
original finding, previously only checked against synthetic-only graphs)
now holds against real topology specifically, not just real node features.

**Real brand feature gap, found this round:** all 10 real `brands` rows have
`category`/`follower_count`/`post_count`/`is_verified`/all three handles
NULL — Track A's documented scope (brands populated only from
disclosure-text name extraction) means every brand node's metadata vector is
currently all-zero except node identity. Not a bug here; flagged for
whoever eventually wants brand nodes to be distinguishable by feature rather
than graph position alone.

**Training attempt: ran, but on a placeholder target — real gap found, not
stubbed silently.** Built the treatment tensor for real (8 of 63 creators
have a real `is_sponsored=true` event). Then tried to compute the actual
supervised target (temporal engagement-delta) for the 6 creators with a
real sponsored neighbor. **Found a new, more specific blocker than "not
built yet": of Kohli's 4 neighbors and Ronaldo's 1, only 3 have any dated
Instagram content at all, and for every one of them, EVERY dated post falls
entirely AFTER their collaborator's sponsorship-event date — none straddle
it.** Root cause: per-creator scraping depth currently reaches back only
1-3 months, and the sponsorship events are themselves recent, so the
"before" window needed for a real delta doesn't exist yet for any
graph-connected pair. This is a data-coverage timing gap (Track A's), not a
missing computation — the delta itself is a simple before/after aggregation
once both sides of an event have dated posts. Ran the training loop anyway
with an explicit all-zero placeholder target, clearly labeled as a
**plumbing check only** (confirms `compute_gail_loss`'s four terms — MSE +
overlap + smoothness + consistency — run to completion with no NaN/crash on
real sparse structure across 50 epochs), not a real result.

**Sufficiency call (Task 4, direct):** **Not sufficient yet, and the
binding reason isn't sample size — it's that the real number of computable
training PAIRS today is 0, not 10.** CAPSTONE_NEXT_STEPS' "10 real
sponsorship events" describes treatment examples; a GAIL training pair also
needs a measured outcome (a neighbor's real engagement delta), and none of
the 10 events currently have one — see the temporal-coverage gap above. This
is a stronger and more specific finding than "N=10 is underpowered" (which
would still have been true even if the deltas WERE computable) — it means
zero real training signal exists right now, full stop. The graph structure
and GAT plumbing are proven real and correct; what's missing is any real
observed outcome to train against. Recommend re-checking after Track A's
Instagram scraping naturally accumulates more historical depth per
creator (older posts) or enough time passes that new dated posts land after
existing events — worth flagging upstream to CAPSTONE_NEXT_STEPS' P0.4/P2
temporal-engagement-delta item, since this specific straddle-the-event
requirement wasn't previously identified as its own gap.

## Real-data status (2026-08-10, Weeks 14-16 check-in — no new build this round)

Fresh session, no memory of prior rounds. Per HANDOFF.md's standing instruction,
did not trust any doc's claim (including this file's own prior entries) — asked
the user for the live Supabase `DATABASE_URL` and ran direct read-only SQL against
the three specific blockers, rather than re-deriving from Track A/C's docs alone.

- **Collaboration edges: still 0.** `SELECT count(*) FROM
  creator_related_accounts` → 0 (all relation types, not just
  `frequent_collaborator`). Unchanged since first measured.
- **Co-occurrence edges: still 0.** `reddit_post_creators` has grown to 346
  rows (up from 233 last round), but a direct `GROUP BY post_id HAVING
  count(distinct creator_id) > 1` query returns 0 rows — every post is still
  linked to exactly one creator. Matches Track C's own concurrent live-DB
  finding this same day (their Weeks 14-16 memory entry) — two independent
  checks, same result.
- **Sponsorships: still 0.** `is_sponsored = true` count is 0 across
  `youtube_videos`/`instagram_posts`/`reddit_posts` (695 total content rows:
  252/97/346). Re-checked the Kohli/Agilitas rows specifically (4 Instagram
  posts mentioning "Agilitas"/"one8", `creator_id
  c4b20dc1-14f2-48e9-8bd5-7131af29049f`): all still exactly 100 characters,
  `fetched_at` still 2026-08-09, `is_sponsored=false`. One row does carry a
  real `brand_id` (Agilitas) — brand-name extraction succeeded — but that's
  a separate signal from the disclosure-tag `is_sponsored` label, which is
  what GAIL actually needs. Track A's caption-fix commit (`8b493d1`) is
  code-complete but Instagram has not been re-scraped since it landed, so
  the existing rows are still pre-fix text.
- **Nothing in HANDOFF.md's steps 3-4 unblocks this round** (re-run
  `scripts/validate_gat_on_real_data.py`'s structural check, or start
  temporal engagement-delta computation) — both are still gated on data
  that doesn't exist yet.

**Cross-branch note, not yet actionable for this file:** `main` carries an
unmerged 2026-08-10 PROJECT_PLAN.md revision pivoting Section 1 from ~15
deep creators to breadth-over-depth (~1,000 curated creators, 200-400
datapoints/entity), explicitly adding team/league accounts to attack the
zero-collaboration-edges blocker documented above. Not yet merged into any
track's branch and not yet visible in Track A's actual HANDOFF.md (still
describes the 15-creator list) — flagging since it's the most direct
planned fix for this doc's oldest open item, worth watching for next round
rather than assuming it's already in effect.

## Real-data status (2026-08-10, Weeks 11-13 — second check this round)

Re-checked partway through this round per the user's instruction, since
Track A was diversifying the target list and Track C was re-running
labeling specifically because of last round's finding. Real progress
happened, but not yet on the two things that unblock GAIL:

- **Creators: 16** (up from 10), reflecting Track A's target-list expansion
  9→15 (6 new verified Indian content creators: BB Ki Vines, CarryMinati,
  MostlySane, Technical Guruji, Mumbiker Nikhil, Guru Mann — all with real
  YouTube channels) plus the original `athleanx` pilot creator.
- **Content volume grew substantially in the background** (collection runs
  via Windows Task Scheduler, independent of git commits) — 97 → 449 real
  content rows just within this session, confirmed via a direct DB
  recheck, not a doc claim.
- **Collaboration edges: still 0.** Unchanged.
- **Co-occurrence edges: still 0** — and this needed its own investigation,
  since Track C's doc claimed a real example existed (PV Sindhu/Saina
  Nehwal via r/badminton). Checked directly: `reddit_post_creators` now has
  233 rows but **zero posts have 2+ distinct creators linked** — every row
  is single-creator. Root cause found via Track A's own commit message:
  their Weeks 11-13 Reddit relevance-gating fix purged 289 of 330 existing
  creator↔post links (88%) as topically-adjacent noise, and the PV
  Sindhu/Saina Nehwal r/badminton links were almost certainly exactly that
  class of noise (the same shared-subreddit-without-actual-mention pattern
  the purge specifically targeted) — Track C's claim was accurate when
  written, the underlying data has since changed (correctly, as a
  data-quality fix) out from under it. Real co-occurrence may reappear
  under the new relevance-gated methodology, just hasn't yet.
- **Kohli/Agilitas still not a training pair, checked precisely again**:
  Track A's latest commit (`8b493d1`) root-caused and fixed the caption
  truncation *going forward* ("opencli instagram user truncates to exactly
  100 chars... parse the full text from the page extract already fetched
  at zero extra cost") — but this is a scraper fix, not a backfill.
  Verified directly: the already-stored Kohli post's caption is still
  exactly 100 characters in the live DB right now. The fix will apply the
  next time this post (or a similar one) is scraped fresh, not
  retroactively. `is_sponsored` is still `False`, all 449 real content rows
  now have a real (non-null) `is_sponsored` value, 0 are `true`.

**GAT structural (graph-structure) re-validation not run this round** —
both edge types are still empirically at 0 real edges despite the volume
growth elsewhere, so there is nothing new to validate against yet. Worth
checking again next round rather than assuming either the co-occurrence or
collaboration gap has closed just because upstream work is happening.

## Real-data status (2026-08-10, Weeks 9-10)

Pulled fresh via Track C's live `/feature-store/*` endpoints against the
real Supabase DB, plus a direct read-only SQL check for what the
feature-store API doesn't expose (raw `is_sponsored`/`brand_id` state).

**Creators: 10 real rows** (up from 3 last round) — the 9 curated
Indian-first target-list creators (Virat Kohli, Neeraj Chopra, Ranveer
Allahbadia, PV Sindhu, Saina Nehwal, Sania Mirza, MC Mary Kom, LeBron James,
Cristiano Ronaldo) plus `athleanx` from the earlier pilot. 8/10 have real
content (text/thumbnails); LeBron James and Cristiano Ronaldo are still
stubs (metadata only, per Track A's real per-creator datapoint table —
their scraping attempts partially failed this round, see Track A's
`DATA_COLLECTION_STATUS.md` Section 8).

**Collaboration edges: still 0.** Unchanged from last round — Track A's
`creator_related_accounts` "frequent_collaborator" rows aren't populated
for these creators yet. **GAT structural (graph-structure) validation
remains blocked on this, not a Track B gap.**

**Sponsorship edges: still 0, but for a nuanced reason worth documenting
precisely** (checked via direct read-only SQL, not just the feature-store
API, since the API only exposes derived edges):
- `brands` table: **1 real row** — "Agilitas" (matches Track A's
  Virat-Kohli/Agilitas positive brand-extraction case from Weeks 7-8).
- Exactly **1 content row has `brand_id` set**: an Instagram post from
  Virat Kohli — caption starts *"2 years back I joined hands with Agilitas
  to build a dream..."* — genuine partnership language, a strong candidate.
- **But `is_sponsored` is `None` (not `false`) on that exact row** — it
  hasn't been run through the disclosure-tag labeler at all. Checked why:
  labeling has only ever been run on the original 21-row pre-bulk-collection
  sample (10 YouTube + 5 Instagram + 6 Reddit) — the real content table
  totals are now 20/41/36 respectively, so **most content, including this
  specific promising row, has never been labeled**. This is not a labeler
  bug — Track A's own SCHEMA.md explicitly warns `brand_id` presence isn't
  proof of `is_sponsored`, and that's exactly what's being observed here:
  a brand *mention* was found, but disclosure-tag labeling is a separate,
  not-yet-applied step for this row.
- **Did not trigger Track C's `POST /labeling/run` myself** — that's their
  pipeline against shared production data, not something to invoke
  unilaterally while just checking status. Flagging as an actionable,
  specific next step instead: re-running labeling against the full current
  dataset is likely to produce at least one real `is_sponsored=true` row
  (the Kohli/Agilitas post looks like a strong candidate on its text
  alone), which would be GAIL's first real training pair.

**CLIP+BERT extraction: run across the full current real dataset (all 10
creators, not just the 3-creator sample from last round)** — 10/10
succeeded, correct `(1289,)` shape, no NaNs, no new integration bugs at
this larger scale. Creators with real thumbnails took ~2.5-3s each (real
CLIP inference on real fetched images); text-only/stub creators were
near-instant. No code changes needed this round — `ml/feature_extraction.py`
held up at 3x the data volume.

## Weeks 11-13 training-loop components — 5 of 7 gap-analysis items now built

The Weeks 9-10 gap analysis (below, preserved for history) identified 7
missing pieces between the tested primitives and an actual trainable GAIL
pipeline. Items 3-7 (not blocked on real data) are now built and tested
against dummy data, same pattern as the Weeks 3-4 regularization work:

3. **Exposure computation — DONE** (`ml/exposure.py`, `ExposureModule`).
   Off-the-shelf per PROJECT_PLAN's stated preference: reuses PyG
   `GATConv`'s own `return_attention_weights` output (already
   softmax-normalized per destination node — exactly GAIL Step 6's
   "personalized weight per collaborator") rather than a separate
   attention mechanism. By construction, exposure is exactly 0 for a node
   with no sponsored neighbors (not just approximately — every term in the
   weighted sum is `attention * treatment`, and `treatment=0` for every
   neighbor zeroes it out exactly).
4. **Spillover prediction head — DONE** (`ml/spillover_head.py`,
   `SpilloverPredictionHead`). Small MLP over `[embedding, exposure]` ->
   scalar prediction (GAIL Step 8).
5. **Combined loss function — DONE** (`ml/gail_loss.py`,
   `compute_gail_loss`). Wires MSE prediction loss to the three existing
   regularization terms with tunable `GAILLossWeights`. **Found and fixed
   a real bug while wiring this**: `laplacian_smoothness_penalty` returned
   `NaN` on zero edges (`.mean()` over an empty tensor) — and 0 real
   collaboration edges is the *actual current live-data state* (see
   "Real-data status" below), not a hypothetical. Fixed to return 0.
   **Also found and fixed a real architecture bug**: naively subsetting
   `prediction[train_idx]` before passing it (with the *full* graph's
   `collab_edge_index`) into the structural terms desyncs node indices and
   crashes. Fixed with a `prediction_mask` parameter — the full graph
   always runs through smoothness/consistency (standard transductive GNN
   practice), only the supervised MSE term is restricted to train nodes.
6. **Training loop — DONE** (`ml/training.py` + `ml/gail_model.py`, which
   wires backbone+exposure+propensity+head into one `forward()`).
   `train_val_split` always leaves ≥1 train node even for tiny graphs.
   Empirically confirmed the plumbing actually works, not just "runs
   without erroring": trained on dummy data with a synthetic target
   (sponsored-neighbor count), prediction-loss component dropped from
   ~0.52 to ~0.002 over 80 epochs — real gradient flow through the whole
   stack, not a no-op.
7. **Evaluation harness — DONE** (`ml/evaluation.py`,
   `evaluate_predictions`). MAE/RMSE/R²/calibration slope+intercept per
   PROJECT_PLAN.md Section 3c's "held-out accuracy/calibration reporting."
   Written independent of how the held-out split is made, so it's ready to
   consume a real campaign-based split later without changes.

All 5 tested against edge cases per this round's self-check instruction,
not just the happy path: zero exposure, empty/zero collaboration edges,
single-node graphs, and a hand-built fully-symmetric complete graph
(4 nodes, identical features, checked that structurally-interchangeable
nodes get identical exposure). 29 new tests, all passing
(`tests/test_exposure.py`, `test_spillover_head.py`, `test_gail_loss.py`,
`test_gail_model.py`, `test_training.py`, `test_evaluation.py`).

**Still blocked on real data (items 1-2, unchanged from Weeks 9-10):**
training-pair construction (needs real sponsorship events + temporal
engagement deltas — nothing computes the latter yet) and propensity-model
fitting (needs real treated/untreated examples). See "Weeks 9-10 gap
analysis" below for the original full writeup of why these are blocked.

<details>
<summary>Weeks 9-10 gap analysis (original, preserved for history)</summary>

Per the user's request: what's missing between the tested primitives
(schema, dummy data, GAT forward pass, causal regularization terms,
CLIP+BERT extraction) and an actual trainable GAIL pipeline.

**Blocked on real data (can't be built against dummy data meaningfully):**
1. **Training examples don't exist yet.** GAIL trains on historical
   sponsorship events, predicting neighbor engagement-gain. This needs real
   `(sponsored creator, timestamp, collaborator, engagement before,
   engagement after)` tuples. Currently: 0 real sponsorship events and,
   separately, no code anywhere computes *temporal engagement deltas* at
   all — the current feature vectors are a single static snapshot, not a
   before/after time series. **This is the single biggest gap.**
2. **Propensity model can't be meaningfully fit yet** — architecturally
   ready and unit-tested, but fitting it needs real treated/untreated
   creator examples, and there are currently 0 real treated creators.

</details>

## Cross-track check (2026-08-09, fourth pass — late addition)

Track C pushed further commits after the real-data pull above: the actual
`is_sponsored` labeling pipeline now exists and ran for real (`POST
/labeling/run`, 21/21 real content rows labeled, 0 false positives — 21
matches the exact real content count: 10 YouTube videos + 5 Instagram posts
+ 6 Reddit posts). Not yet re-pulled/re-validated this session (found late,
after this round's real-data work was already done) — worth checking next
session whether any of those 21 rows are actually `is_sponsored=true` (0
brand-extraction hits earlier suggests probably not yet, but don't assume).
Track C also fixed a latent bug in their own `build_collaboration_edges`
(non-deterministic handle-collision resolution) found while re-checking
their feature store against live data — not yet triggered against real
rows, but good to know the collaboration-edge path had its own bug fixed
independently.

## Cross-track check (2026-08-09, third pass)

Checked Track A's creator cross-platform dedup bug fix (`supabase/
migrations/20260809020000_dedupe_creators.sql`, found running a real Weeks
5-6 ingestion pilot: a missing unique constraint let the orchestrator
create duplicate `creator_id` rows for the same real channel across reruns)
for whether `ml/` code quietly depends on the old buggy one-row-per-platform
behavior. **Confirmed clean** — grepped `ml/` and `tests/` for any
per-platform handle/identity logic; none exists. The `creator` node has
always been designed as one node per real creator (Track B never queries
per-platform tables directly — that's Track C's `feature_store.py` job),
so this fix requires no changes here. Also verified via the real-data pull
this session: the live feature-store API already returns exactly 3 creator
rows (one per real person), not per-platform duplicates.

## Cross-track check (2026-08-09, second pass)

Re-checked `origin/track-a-data-infra` and `origin/track-c-fusion-backend`
fresh via `git fetch` + `git log`/`git show` before starting Weeks 5-6 work.
Real, substantive changes since the last check (same day): Track A added
the `brands` table (migration `20260809010000_add_brands.sql`) — brand
node section above rewritten against it. Track A also ran an adversarial
self-check of their own and found two real bugs (missing Reddit FK
indexes, an over-capturing brand-name regex) — both fixed, documented in
their SCHEMA.md. All three scraping platforms now proven working
end-to-end via real pilot calls, though the orchestrator→DB wiring isn't
done yet, so no real rows exist in the DB (see brand section above for the
precise distinction). Track C fixed the `is_sponsored` contract and
switched `creator_unique_id: str` → `creator_id: uuid.UUID` to match Track
A's real schema (a breaking change for anyone who built against their
Weeks 1-2 version — noted here since it's a reminder to re-check contracts
after "resolved" cross-track items, not just once). Neither change affects
`ml/schema.py` directly (Track B doesn't reference creator ID strings/UUIDs
in the graph tensors themselves), but worth knowing before any future
real-data loading code is written.

## Cross-track check (2026-08-09, first pass)

Re-checked `origin/track-a-data-infra` (all files, latest commits) via
`git fetch` + `git ls-tree`/`git show`. No `brands` table yet (still just
the 2026-08-08 `SCHEMA.md` state) and no pilot-scraping-batch results yet
(`DATA_COLLECTION_STATUS.md` still shows Weeks 1-2 setup status, Instagram/
Reddit backends still off pending human Chrome-extension/login steps) — both
expected, not a problem, just confirming nothing to reconcile against yet.
Surfaced the `is_sponsored` ownership disagreement above while re-reading
Track A's file (it was already flagged there on 2026-08-08; repeating it
here since it's directly relevant to this doc's `sponsors` edge).

## Cross-track check (2026-08-08)

Checked `origin/track-a-data-infra:SCHEMA.md` and
`origin/track-c-fusion-backend:API_CONTRACTS.md` via `git fetch` + `git
show`. Reconciled: creator category taxonomy (now matches Track A exactly),
Track C's output contract (now referenced above), bot-detection signal
availability (confirmed). Surfaced: the brand-entity gap above. Track D's
`WIREFRAMES.md` also exists but wasn't relevant to this file's scope.
