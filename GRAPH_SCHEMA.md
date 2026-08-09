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
- **`co_occurs_with` has no data source at all** (confirmed by Track C's
  feature-store code, not just unbuilt) — no co-starring/tagging signal
  exists anywhere in Track A's schema. Either needs a new Track A ingestion
  field or gets inferred from something not yet collected. Not Track B's
  call to add scope to Track A's pipeline unilaterally.
- **`reputation_score` has no source column anywhere** (same — confirmed by
  Track C, always `None`). Open, no owner assigned yet.
- **Real-data validation of the GAT/GraphSAGE finding is real-feature-value
  validated but STILL NOT real-graph-structure validated as of 2026-08-10**
  — re-checked this round, still 0 real `collaborates_with` edges (data
  collection gap, not evidence against real collaborations). Re-run
  `scripts/validate_gat_on_real_data.py` the moment real edges exist — see
  "Real-data status" below for exact current counts.
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

## Weeks 11-13 training-loop gap analysis

Per the user's request: what's missing between today's tested primitives
(schema, dummy data, GAT forward pass, causal regularization terms,
CLIP+BERT extraction) and an actual trainable GAIL pipeline — so Weeks
11-13 isn't a cold start. Not built this round (real data isn't ready at
volume, and this was explicitly scoped as analysis, not implementation).

**Blocked on real data (can't be built against dummy data meaningfully):**
1. **Training examples don't exist yet.** GAIL trains on historical
   sponsorship events, predicting neighbor engagement-gain. This needs real
   `(sponsored creator, timestamp, collaborator, engagement before,
   engagement after)` tuples. Currently: 0 real sponsorship events (see
   "Real-data status" above) and, separately, no code anywhere computes
   *temporal engagement deltas* at all — the current feature vectors are a
   single static snapshot (`log_subscriber_count`, `engagement_rate` as of
   scrape time), not a before/after time series. Even once a real
   sponsorship event exists, extracting its training pair requires
   per-post timestamped engagement history, which Track A's raw tables can
   support (they have `posted_at`/`published_at` per post) but nothing in
   Track B's or Track C's pipeline currently constructs this. **This is
   the single biggest gap** — likely needs a small new module (a
   time-windowed engagement-delta calculator) once real events exist.
2. **Propensity model can't be meaningfully fit yet** — `PropensityScoreModel`
   (`ml/causal_regularization.py`) is architecturally ready and unit-tested,
   but fitting it needs real treated/untreated creator examples, and there
   are currently 0 real treated (sponsored) creators.

**NOT blocked on real data — could be built and dummy-data-tested now,
the same way the regularization terms were in Weeks 3-4:**
3. **No explicit "exposure" computation.** `ml/model.py`'s
   `SchemaSmokeTestGAT` outputs generic per-node embeddings, not GAIL's
   named "exposure" quantity (GAIL doc Step 7: exposure = f(sponsored
   neighbors, attention weights)). Needs a small module that reads GAT's
   attention weights (or recomputes an attention-weighted aggregate over
   sponsored neighbors specifically) into a single per-creator exposure
   scalar/vector.
4. **No spillover prediction head.** Nothing turns embeddings/exposure into
   a scalar engagement-gain prediction (GAIL doc Step 8). Needs a small
   MLP head, straightforward to add and dummy-data-testable today.
5. **No combined loss function.** The three regularization terms
   (`overlap_penalty`, `laplacian_smoothness_penalty`,
   `consistency_penalty`) exist and are tested individually, but nothing
   sums them with a prediction loss (e.g. MSE against actual engagement
   gain) and tunable weights (`λ1`, `λ2`, `λ3`). Straightforward once the
   prediction head (#4) exists.
6. **No training loop at all** — no optimizer, no epoch loop, no train/val
   split, no checkpointing. Standard PyTorch boilerplate, buildable and
   testable against dummy data now (a fake "training run" that converges on
   synthetic targets would at least prove the loop's plumbing).
7. **No evaluation harness** — PROJECT_PLAN.md Section 3c calls for
   "empirical train/test split on historical campaigns, held-out
   accuracy/calibration reporting." Doesn't need real data to build the
   harness itself, just something to evaluate.

**Recommendation for next round with schedule slack:** items 3-7 above are
worth building against dummy data before Weeks 11-13 proper starts, mirroring
how the regularization terms were de-risked early — they're pure engineering
work, not blocked on anything external. Item 1 (real training-pair
construction) is the one piece that's genuinely blocked and worth
monitoring Track A/C for rather than attempting against dummy data (a fake
temporal-delta calculator would validate the code shape but not the real
signal it needs to prove out).

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
