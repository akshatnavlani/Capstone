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

Feature vector = CLIP embedding ++ BERT embedding ++ metadata, dim **1291**:

| Segment | Dim | Source |
|---|---|---|
| CLIP embedding | 512 | `openai/clip-vit-base-patch32` pooled image embedding of representative thumbnail(s) |
| BERT embedding | 768 | `bert-base-uncased` pooled embedding of scrubbed post/bio text |
| `log_subscriber_count` | 1 | log-scaled per PROJECT_PLAN.md Section 2 metric scaling |
| `engagement_rate` | 1 | |
| `reputation_score` | 1 | |
| category one-hot | 8 (`NUM_CATEGORIES`, placeholder) | e.g. Fitness, Lifestyle, Sports — **see Open Items** |

### `brand`

Feature vector = BERT embedding ++ metadata, dim **777**:

| Segment | Dim | Source |
|---|---|---|
| BERT embedding | 768 | `bert-base-uncased` pooled embedding of brand product/marketing copy |
| `budget_tier` | 1 | |
| category/industry one-hot | 8 (`NUM_CATEGORIES`, shared taxonomy with creator) | **see Open Items** |

**⚠️ Open item for Track A:** PROJECT_PLAN.md Section 1 (Data Collection)
only scopes creator-side scraping (YouTube/Instagram/Reddit). It doesn't
say what data gets collected for brands, so the brand feature vector above
is Track B's assumption, not a confirmed contract. If brand-side data
collection isn't planned, we need an explicit decision here — either Track A
adds a minimal brand data source (e.g. product descriptions, industry tags),
or Track B drops the BERT component and uses metadata-only brand features.
Flagging now rather than discovering it at Week 9-10 feature-extraction time.

## Edge types

| Edge type | Direction | Weighted? | Meaning |
|---|---|---|---|
| `(creator, collaborates_with, creator)` | both directions populated | yes (`edge_attr`, scalar) | collaboration frequency between two creators |
| `(creator, co_occurs_with, creator)` | both directions populated | yes (`edge_attr`, scalar) | platform co-occurrence (shared platforms / joint appearances) |
| `(brand, sponsors, creator)` | brand → creator | no | treatment edge; existence derived from `is_sponsored` disclosure-tag labeling (PROJECT_PLAN.md Section 1/2) — the sole source of GAIL's training signal |
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
applicable.

## What Track C should expect as output

Not yet built (Weeks 11-15 per the timeline) — the GAIL branch will output
a per-creator spillover/exposure score, combined with the Temporal branch's
output in the Causal Inference layer (PROJECT_PLAN.md Section 3c) before
reaching Track C's Fusion Layer. This doc will be updated with the concrete
output tensor shape once that's implemented; called out here so Track C
knows not to expect it yet.

## Open items

- `NUM_CATEGORIES` (currently 8, placeholder) needs Track A's finalized
  category taxonomy — used identically for creator niche and brand industry
  under a shared-taxonomy assumption (also unconfirmed).
- Brand-side data collection scope (see ⚠️ above).
- Edge weight semantics (raw counts vs. normalized) for `collaborates_with`
  / `co_occurs_with` — currently unspecified pending real data shape from
  Track A; `ml/schema.py` just reserves a scalar `edge_attr` slot.
