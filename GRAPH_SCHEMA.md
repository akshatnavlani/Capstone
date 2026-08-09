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
- **`co_occurs_with` has no data source at all** (confirmed by Track C's
  feature-store code, not just unbuilt) — no co-starring/tagging signal
  exists anywhere in Track A's schema. Either needs a new Track A ingestion
  field or gets inferred from something not yet collected. Not Track B's
  call to add scope to Track A's pipeline unilaterally.
- **`reputation_score` has no source column anywhere** (same — confirmed by
  Track C, always `None`). Open, no owner assigned yet.
- **Real-data validation of the GAT/GraphSAGE finding is real-feature-value
  validated but NOT real-graph-structure validated** — 0 real collaboration
  edges exist yet (data-collection gap, not evidence of no real
  collaborations). Re-run `scripts/validate_gat_on_real_data.py` once real
  `collaborates_with` edges exist for at least a few creators.
- **GraphSAGE backbone decision — provisionally accepted 2026-08-09,
  PROJECT_PLAN.md Section 3a updated** (see "Why GAT over GraphSAGE"
  above): GAT already satisfies the plan's stated inductive rationale, so
  staying on GAT for production and skipping the swap is accepted, not just
  a fallback. A prototype weighted `MessagePassing` layer still exists
  (`ml/weighted_sage_conv.py`) in case GraphSAGE is wanted later for
  unrelated reasons (large-scale neighbor sampling, degree-variance
  robustness). **Not fully closed:** real-data validation so far covers
  real feature values but not real graph structure (0 real collaboration
  edges exist) — re-run once real edges land.
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
