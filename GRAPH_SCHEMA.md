# GAIL Branch: Heterogeneous Graph Schema

Owner: Track B (ML-Core). Source: `ml/schema.py` (this doc mirrors that code —
if they ever disagree, the code is authoritative). Implements
PROJECT_PLAN.md Section 3a.

This is validated end-to-end against synthetic data (`ml/dummy_data.py`,
`tests/test_schema.py`) with a basic GAT forward pass — real data doesn't
exist until Track A finishes Weeks 3-4 scraping, so dummy data is the
correct validation method for this stage.

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

Feature vector = BERT embedding ++ metadata, dim **775**:

| Segment | Dim | Source |
|---|---|---|
| BERT embedding | 768 | `bert-base-uncased` pooled embedding of brand product/marketing copy |
| `budget_tier` | 1 | |
| category/industry one-hot | 6 (reuses `NUM_CATEGORIES`, shared-taxonomy assumption — **unconfirmed**) | |

**⏳ RESOLVED direction, not yet landed (2026-08-09):** user decided on real
brand scraping (option (b)/schema-extension from the 2026-08-08 discussion),
not a text-derived approximation. **Track A is adding a `brands` table this
week**, scoped to brands that appear in sponsorship text. Until that lands,
the feature vector above stays a placeholder — every field in
`ml/schema.py`'s `BRAND_METADATA_DIM`/`BRAND_FEATURE_DIM` block is now
marked with an explicit `# PLACEHOLDER` comment pointing back here, so it
can't be mistaken for a confirmed contract. Once Track A publishes the
`brands` table shape, this section needs a full rewrite against real
columns, not just an update.

## Edge types

| Edge type | Direction | Weighted? | Meaning |
|---|---|---|---|
| `(creator, collaborates_with, creator)` | both directions populated | yes (`edge_attr`, scalar) | collaboration frequency between two creators |
| `(creator, co_occurs_with, creator)` | both directions populated | yes (`edge_attr`, scalar) | platform co-occurrence (shared platforms / joint appearances) |
| `(brand, sponsors, creator)` | brand → creator | no | treatment edge; existence derived from `is_sponsored` disclosure-tag labeling. Per Track A's SCHEMA.md, `is_sponsored` is currently **nullable/unpopulated** — the labeling pipeline is Track C's Weeks 7-8 deliverable, and per Track A, don't build a separate labeler against raw text in the meantime. Also blocked on the brand-identity gap above: even once `is_sponsored` is populated, this edge needs a `brand` endpoint to attach to. |
| `(creator, sponsored_by, brand)` | creator → brand (reverse of `sponsors`) | no | required so PyG can message-pass into brand nodes; not a separate data source, just the transpose |

Both directions of `collaborates_with` / `co_occurs_with` must be populated
explicitly (Track B does not apply `ToUndirected()` at load time) — if
creator A collaborated with creator B, both `(A,B)` and `(B,A)` edges should
be present with the same weight.

## Why GAT over GraphSAGE (for this smoke test)

PROJECT_PLAN.md Section 3a names both as acceptable backbones. GAT was used
for the Week 1-2 schema-validation model (`ml/model.py`) because its
per-edge attention coefficients are the direct implementation of GAIL's
"personalized spillover weight per collaborator" (see the GAIL working-doc
Step 6). GraphSAGE's inductive aggregation (new nodes without full retrain)
is still the plan for the production GAIL branch in Weeks 11-13 — this
isn't a final architecture decision, just what Week 1-2 needed to prove the
schema works with attention-based message passing.

**Swap-cost check (2026-08-09):** verified empirically, not assumed —
`torch_geometric.nn.SAGEConv` has no `edge_attr`/`edge_dim` parameter at
all (`SAGEConv.forward` only takes `x`, `edge_index`, `size`; confirmed by
inspecting the signature and by reproducing the `TypeError` when passing
`edge_attr` into a `HeteroConv`-wrapped `SAGEConv`). GAT's weighted-edge
handling in `ml/model.py` depends entirely on `edge_dim`, which GraphSAGE
has no equivalent for. **This means swapping backbones for the Weeks 11-13
production model is not a one-line class swap** — the `collaborates_with`/
`co_occurs_with` weighted relations will need either a small custom
`MessagePassing` layer (e.g. scale `x_j` by edge weight before mean
aggregation — the standard way to add edge weights to GraphSAGE) or another
mechanism. The good news: this only affects `ml/model.py`, not the data
contract — `ml/schema.py`'s scalar `edge_attr` representation is
backbone-agnostic and doesn't need to change. Budget real implementation
time for this in Weeks 11-13 rather than assuming it's free.

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

## What Track A needs to produce

Populate `ml/schema.py::empty_hetero_data()` — i.e., for each creator/brand,
the raw inputs needed to compute the feature segments above (thumbnail
image(s) for CLIP, scrubbed text for BERT, the metadata fields, and category
label), plus the edge lists for all four edge types with weights where
applicable. **Brand-side data is entirely unscoped — see the blocker above.**

Bot-detection heuristic signals (Track B's Weeks 7-8 deliverable) are
already confirmed available per Track A's SCHEMA.md: `follower_count`/
`following_count` ratio, `account_created_at` (YouTube/Reddit only —
Instagram doesn't expose this), and posting frequency from
`posted_at`/`published_at` timestamps. No action needed now, just noting
the dependency is resolved.

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

- **Brand-entity data — direction resolved, not yet landed.** Real brand
  scraping confirmed (see ⏳ above); waiting on Track A's `brands` table this
  week. Once it lands, rewrite the `brand` node section against real
  columns and drop the `# PLACEHOLDER` markers in `ml/schema.py`.
- Brand category/industry taxonomy — currently reuses creator's 6-value
  taxonomy as a placeholder assumption; brands likely need a different,
  currently-undefined taxonomy (e.g. industry verticals vs. content niches).
  Revisit once Track A's `brands` table shape is known.
- Edge weight semantics (raw counts vs. normalized) for `collaborates_with`
  / `co_occurs_with` — currently unspecified pending real data shape from
  Track A; `ml/schema.py` just reserves a scalar `edge_attr` slot.
- **GraphSAGE weighted-edge support** (see "Why GAT over GraphSAGE" above) —
  needs a custom `MessagePassing` layer before the Weeks 11-13 production
  swap, not a config change.
- **Who computes `is_sponsored`? (FYI, not Track B's call to make.)** Track
  A's SCHEMA.md flags a real disagreement with Track C's API_CONTRACTS.md:
  Track C assumes Track A pre-computes and sends `is_sponsored`; Track A's
  reading of PROJECT_PLAN.md's timeline (row "7-8", Track C's column: "...
  sponsorship labeling pipeline") assigns that step to Track C. Unresolved
  as of the last check. This matters to Track B because `is_sponsored` is
  GAIL's sole treatment-label source — if it falls through the cracks
  between A and C, the `sponsors` edge has no data regardless of the
  brand-entity resolution above. Not Track B's dispute to settle, but worth
  the user's attention alongside the brand-table work.

## Cross-track check (2026-08-09)

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
