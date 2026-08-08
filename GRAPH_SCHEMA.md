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

**🛑 Confirmed cross-track blocker (not just an assumption anymore):**
Track A's `SCHEMA.md` (published 2026-08-08) has **no brand entity at all**.
Sponsorship is stored as a binary `is_sponsored` flag on content rows plus
`sponsorship_raw_matches jsonb` (the matched disclosure phrase text, e.g.
"in partnership with Nike") — there is no parsed/normalized brand name,
brand ID, or brand table anywhere in the data layer. Track A's doc says
explicitly: *"If GAIL needs brand nodes with names (not just a binary
treatment flag), that requires either a NER step downstream or a schema
extension — tell me if you need this and I'll add it."*

GAIL **does** need this — PROJECT_PLAN.md Section 3a specifies a
heterogeneous graph with creator *and brand* nodes, and the whole point of
the `(brand, sponsors, creator)` edge is to know which specific brand
sponsored which creator (so spillover can be attributed and, later, brands
can be recommended creators). A bare `is_sponsored` boolean can't populate
brand nodes.

**This needs a decision, relayed by the user, not resolved silently:**
either (a) Track A extends the schema with a parsed brand entity (would need
NER/entity-linking on `sponsorship_raw_matches`), or (b) Track B owns a
downstream brand-name-extraction step on top of Track A's raw
`sponsorship_raw_matches` text. Until decided, `brand` nodes in this schema
are validated only against synthetic dummy data — there is no real path to
populate them yet. The feature vector above is a placeholder pending that
decision.

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

- **Brand-entity data gap (see 🛑 above)** — needs a decision between Track A
  extending their schema vs. Track B owning brand-name extraction downstream.
  Highest-priority open item; blocks any real (non-dummy) `brand` node data.
- Brand category/industry taxonomy — currently reuses creator's 6-value
  taxonomy as a placeholder assumption; brands likely need a different,
  currently-undefined taxonomy (e.g. industry verticals vs. content niches).
- Edge weight semantics (raw counts vs. normalized) for `collaborates_with`
  / `co_occurs_with` — currently unspecified pending real data shape from
  Track A; `ml/schema.py` just reserves a scalar `edge_attr` slot.

## Cross-track check (2026-08-08)

Checked `origin/track-a-data-infra:SCHEMA.md` and
`origin/track-c-fusion-backend:API_CONTRACTS.md` via `git fetch` + `git
show`. Reconciled: creator category taxonomy (now matches Track A exactly),
Track C's output contract (now referenced above), bot-detection signal
availability (confirmed). Surfaced: the brand-entity gap above. Track D's
`WIREFRAMES.md` also exists but wasn't relevant to this file's scope.
