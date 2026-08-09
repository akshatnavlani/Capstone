# API Contracts — Fusion + Backend (Track C)

Owner: Track C (Fusion+Backend). Updated whenever the contract changes — treat
edits to this file as high-signal for Tracks A/B/D, since there's no live
channel between sessions, only git.

**Status as of 2026-08-10:** all endpoints below are live
(FastAPI + SQLModel, `backend/`). Full OpenAPI/Swagger UI is auto-generated at
`/docs` when the server is running (`GET /openapi.json` for the raw spec).

Base URL (local dev): `http://127.0.0.1:8000`. Basic auth now exists — see
the **Auth** section below — off by default, opt-in via `API_KEY`. CORS is
now configured — see the incident below before assuming any prior "verified
end-to-end" claim covered real browser behavior.

## ⚠️ Incident (2026-08-10): no CORS middleware existed at all, since Weeks 1-2

Found by Track D's first real browser test of the product. **Every prior
"verified end-to-end" check across every track (mine included) used curl,
which does not enforce or even send `Origin`/CORS the way a real browser
does** — so this was invisible for 8 weeks despite blocking all real
browser use of the API. Fixed by adding `CORSMiddleware` in `main.py`,
allowing `http://localhost:3000`/`http://127.0.0.1:3000` (Track D's `next
dev` origins) by default — extend via `CORS_ALLOW_ORIGINS` (comma-separated)
in `.env` once a deployed frontend origin exists. `allow_credentials=False`
since auth here is an explicit `X-API-Key` header, not a cookie.

Verified server-side via curl (checking the actual `Access-Control-Allow-*`
response headers, which is what determines whether a real browser accepts
the response — this is a legitimate way to check the *server's* behavior,
just not a substitute for confirming a *browser* accepts it): allowed
origin (`http://localhost:3000`) gets `access-control-allow-origin` back on
both simple requests and preflight `OPTIONS`; a disallowed origin
(`http://evil.example.com`) does not, confirming the allowlist is actually
enforced, not a wildcard. Checked uniformly across `/health`,
`/recommendations`, `POST /ingestion/creators`, `POST /alerts`, and `GET
/alerts` — same middleware applies globally, so no per-router gap. **Not
yet confirmed by an actual browser** — ask Track D to re-test now that this
is pushed, since they have the working browser tool and this session
doesn't.

## Weeks 7-8 update summary

- **New:** `POST /labeling/run` — the actual disclosure-tag (`is_sponsored`)
  labeling pipeline, see its own section below. Already run against the
  live DB: 21/21 real content rows labeled (0 false positives on real data).
- Text scrubbing (`app/text_processing.py::scrub_text`) now applied to the
  feature store's `raw_text` before staging it for Track B's BERT step —
  not a wire-shape change, just better content.
- **Fixed a real latent bug in `build_collaboration_edges`**, found while
  re-checking the feature store against live data per this round's
  instructions: ambiguous handles (the same handle claimed by 2+ creator
  rows — confirmed live, from Track A's pre-fix creator-dedup bug) were
  previously resolved to whichever creator got processed last while
  building the lookup map, silently and non-deterministically. Now treated
  as unresolvable instead. Wasn't yet causing a wrong result (
  `creator_related_accounts` was empty at the time), but would have the
  moment it wasn't.
- `reputation_score` / `co_occurs_with` gaps (flagged Weeks 5-6): re-checked
  against Track A's latest work (creator-ID dedup fix, Reddit profile
  enrichment) — neither is addressed by it. Still open, no new derivable
  signal found. Not force-fixed with an invented formula.

## ⚠️ Incident (2026-08-09): `POST /alerts` was returning 500 against the real DB

Fixed same-day, but flagging prominently since it may explain a live 500
Track D or anyone else hit. `RiskAlert.propagated_from_creator_id` was
added to `models.py` in the Weeks 5-6 commit, but `init_db()`'s
`create_all()` only creates tables that don't already exist — it silently
does **not** alter existing ones. Since `riskalert` already existed in the
live Supabase DB from Weeks 3-4, the new column never actually reached the
real table, even though the ORM model claimed it did. Every `POST /alerts`
against the real DB failed with `psycopg2.errors.UndefinedColumn` until
caught here. Confirmed via `information_schema.columns` before/after, plus
a real insert/delete round-trip. Fixed with a real migration
(`backend/migrations/0002_add_alerts_propagated_from.sql`, applied directly
against the live DB) instead of just editing the model again — see that
folder's README for the new rule this establishes: schema changes to an
*existing* Track C-owned table now require a hand-written migration file,
not just a `models.py` edit. Also diffed `fusionscore`'s live columns
against its model as a sanity check — no drift there.

## Weeks 5-6 update summary

- **New:** `GET /feature-store/creators`, `GET /feature-store/edges/collaborations`,
  `GET /feature-store/edges/sponsorships` — the DB → feature-store pipeline
  for Track B, see its own section below.
- **New:** `POST /ingestion/creators/related-accounts` — was missing an
  ingestion path even though the `Brand`/collaboration-edge logic needed to
  read it.
- **`product_category` / `platform_preference` filtering in
  `/recommendations` is now real** (was still-open as of the Weeks 3-4
  version of this doc).
- **`AlertResponse`/`AlertCreate` gained `propagated_from_creator_id`**
  (nullable uuid) — added ahead of the Weeks 14-15 Sentiment Propagation
  work landing, per Track D's flag that the freeform `source` string alone
  would force a second breaking change later.
- **Basic auth added**, opt-in via `API_KEY` env var, off by default.

---

## ⚠️ BREAKING CHANGE (2026-08-09) — read this if you read the Weeks 1-2 version

Two things changed from the version published 2026-08-08. **If Track A or
Track D built against the old version, re-check against this one:**

### 1. `creator_unique_id: str` → `creator_id: uuid.UUID`, everywhere

The Weeks 1-2 version invented a placeholder `unique_id: str` field before
Track A's real schema existed. Track A's actual, live `SCHEMA.md` uses
`creators.creator_id` (a Postgres `uuid`). Every endpoint below now uses
`creator_id` (UUID) instead of `creator_unique_id` (string) — this affects
`POST /recommendations` results, `POST /scores/compute`, `GET
/scores/{creator_id}`, `POST /alerts`, `GET /alerts`.

### 2. `is_sponsored` ownership — Track C's Weeks 1-2 assumption was wrong

The Weeks 1-2 version of this doc assumed **Track A pre-computes
`is_sponsored`** and sends it via ingestion. That was wrong. Per
PROJECT_PLAN.md Section 6, Weeks 7-8 explicitly assigns "sponsorship
labeling pipeline" to **Track C**, not Track A. Track A's real, live schema
confirms this: `is_sponsored` and `sponsorship_raw_matches` are **nullable,
unpopulated by design** on `youtube_videos` / `instagram_posts` /
`reddit_posts` — Track A stores raw scraped text only.

Fixed: every content-level ingestion schema below (`YouTubeVideoIngest`,
`InstagramPostIngest`, `RedditPostIngest`) now has `is_sponsored: Optional[bool]
= None` and `sponsorship_raw_matches: Optional[list[str]] = None`. The actual
disclosure-tag labeling logic itself is still a Weeks 7-8 deliverable — not
built yet — but the ingestion contract shape is now correct so Track A's
real Weeks 3-4 data lands without a schema mismatch.

### 3. (Not a break, but important) Track A's real pipeline bypasses `/ingestion/*` entirely

Discovered while reconciling schemas 2026-08-09: Track A's actual ingestion
orchestrator (`scripts/ingestion/orchestrator.py` on `track-a-data-infra`)
writes **directly to the shared Supabase Postgres DB** via `DATABASE_URL`,
not through this API. So `/ingestion/*` below is **not the primary
ingestion pipeline** — it's a secondary/manual write path (testing, other
tracks seeding data). The tables it writes to are the same tables Track A's
orchestrator writes to directly, so it stays useful, just not load-bearing
for the real Weeks 3-4 scraping pipeline the way Weeks 1-2 assumed.

---

## Note: `brands` table (added by Track A 2026-08-09, reconciled here same day)

Track A added a `brands` table + nullable `brand_id` FK on `youtube_videos`/
`instagram_posts`/`reddit_posts` (migration `20260809010000_add_brands.sql`,
bounded scope: populated only from brand names found in sponsorship-disclosure
text already on creator content, not an open crawl — see their SCHEMA.md).
Added a matching `Brand` model in `backend/app/models.py` so this stays in
sync. **Not yet exposed via `/ingestion/*` or used in `/recommendations`** —
Track A's orchestrator writes it directly like everything else (see breaking-
change note #3), and no Track C endpoint reads/writes it yet. Flag if Track B
or D need it surfaced through this API.

## Cross-track dependency flags

- **Track A (Data/Infra):** models in `backend/app/models.py` now mirror
  Track A's real `SCHEMA.md` + `supabase/migrations/20260808163402_init_schema.sql`
  as of 2026-08-09 (checked via `git show origin/track-a-data-infra:SCHEMA.md`).
  Re-diff if their schema changes — this repo doesn't auto-detect drift.
- **Track B (ML-Core):** `POST /scores/compute` expects `spillover_score`,
  `sentiment_risk_score`, `creator_feature_score` each as finite floats in
  `[0, 1]` (NaN/Infinity now explicitly rejected, see Validation section).
  Also flags an **open item from Track A's SCHEMA.md**: Track B's
  `GRAPH_SCHEMA.md` assumes brand-node features that no Track A table
  supplies — not a Track C concern directly, but worth knowing if you're
  coordinating with Track B.
- **Track D (Frontend+App):** build against the schemas below. `creator_id`
  is now a UUID string in JSON, not an arbitrary string — validate/parse
  accordingly. `POST /recommendations` responses include `is_mock_data`;
  check it before treating scores/results as real.

---

## Endpoints

### Health

`GET /health` → `{ status, db_connected, version }`

### Brand-input recommendation engine

`POST /recommendations`

Request:
```json
{
  "product_category": "fitness apparel",
  "budget": 50000,
  "target_region": "IN-south",
  "target_demographic": "18-24 fitness enthusiasts",
  "platform_preference": ["youtube", "instagram"],
  "max_results": 10
}
```
`budget` must be `> 0` and finite (NaN/Infinity rejected with 422).

Response: `{ query, results: [InfluencerRecommendation...], is_mock_data }`

`InfluencerRecommendation`:
```json
{
  "creator_id": "758b86ea-266d-48dd-848e-564f47ad8275",
  "name": "TestCreator",
  "category": "fitness_influencer",
  "youtube_handle": "@testcreator",
  "instagram_handle": null,
  "reddit_handles": ["r/test"],
  "final_score": 60.0,
  "confidence_low": 52.0,
  "confidence_high": 68.0,
  "estimated_reach": 1000000,
  "estimated_cost": 500000.0,
  "score_breakdown": { "...": "..." }
}
```

**Filtering/ranking behavior (fully real as of 2026-08-09):**
- **Budget** — hard filter. `estimated_cost = max(youtube subscriber_count,
  instagram follower_count) * 0.5 INR` — a **placeholder rate**, no real
  rate-card data exists yet. Candidates with no reach data at all aren't
  excluded (cost unknown, not assumed zero or infinite).
- **`platform_preference`** — hard filter. Creator must have a handle on at
  least one requested platform. Unlike the soft filters below, "no handle
  on this platform" is a directly known fact, not missing data.
- **`target_region` / `target_demographic` / `product_category`** — soft
  filters. A creator is excluded only if we *have* text signal for them
  (`youtube_channels.country`/`.description`, `instagram_profiles.bio`, or
  — for `product_category` — the creator's own `category`) and it does
  **not** keyword-match. Creators with no signal data at all are kept — with
  scraping still ramping up, a hard requirement would return empty result
  sets for almost every query right now.
  - Matching is **keyword-overlap** (any word ≥3 chars in the query appears
    in the combined signal text), not whole-phrase substring — a
    whole-phrase requirement almost never matches real bio/description text.
  - **Gotcha found during regression testing:** if the query itself has no
    extractable keywords (e.g. a 1-2 char string), that must be treated as
    "can't judge" and skip the filter, not as a confirmed mismatch — an
    earlier draft of this logic conflated the two and wrongly excluded
    every creator with *any* signal whenever the query was too short to
    yield a keyword. Fixed before this landed; flagging so nobody
    reintroduces it while touching this code later.
- Ordering is always by `final_score` descending among eligible candidates.
- Falls back to 3 mock creators (FitWithPriya/GymBro/YogaGuru) when the
  `creators` table is empty; falls back to a placeholder 0.5/0.5/0.5 fusion
  score per-creator when no `FusionScore` row exists yet for them. Check
  `is_mock_data` in the response — it's `true` if either fallback applied.

### Ingestion (secondary/manual write path — see breaking-change note above)

Requires `X-API-Key` if `API_KEY` is configured (see "Auth" below).

- `POST /ingestion/creators` — list of `CreatorIngest`. Upserts by `creator_id`
  (generated server-side if omitted).
- `POST /ingestion/creators/related-accounts` — list of
  `CreatorRelatedAccountIngest`. Upserts by the table's real unique
  constraint `(creator_id, platform, handle)`. This is the source table for
  the feature store's `collaborates_with` edges (see below) — added
  Weeks 5-6, was missing before even though the edge logic needed it.
- `POST /ingestion/youtube/channels` — list of `YouTubeChannelIngest`. Upserts
  by `channel_id`.
- `POST /ingestion/youtube/videos` — list of `YouTubeVideoIngest`. Upserts by
  `video_id`. `is_sponsored`/`sponsorship_raw_matches` optional/nullable.
- `POST /ingestion/instagram/profiles` — list of `InstagramProfileIngest`.
  Upserts by `username`.
- `POST /ingestion/instagram/posts` — list of `InstagramPostIngest`. Upserts
  by `post_id`. `is_sponsored`/`sponsorship_raw_matches` optional/nullable.
- `POST /ingestion/reddit/profiles` — list of `RedditProfileIngest`. Upserts
  by `username`.
- `POST /ingestion/reddit/posts` — list of `RedditPostIngest`. Upserts by
  `post_id`. `is_sponsored`/`sponsorship_raw_matches` optional/nullable.

All eight return `{ received, created, updated }`. Full field lists in
`backend/app/schemas.py` — they mirror Track A's real table columns exactly
(see SCHEMA.md), so cross-reference there for anything not shown here.
**Reminder:** `InstagramProfileIngest`/`YouTubeChannelIngest`/etc. all accept
an optional `creator_id` — if you omit it, the row never links back to its
creator (`creator_id` stays null), which silently breaks anything that joins
on it (recommendation filtering, feature-store aggregation). Always pass it
when you have it.

### Feature store (DB → Track B's `ml/schema.py` input shape, new Weeks 5-6)

Read-only. Transforms Track A's raw tables into the shape Track B's GAIL
branch needs — see `backend/app/feature_store.py` for the full writeup,
this is a summary. **Does not compute CLIP/BERT embeddings** (that's Track
B's Weeks 9-10 deliverable, confirmed via their GRAPH_SCHEMA.md) — stages
the raw inputs those need instead.

- `GET /feature-store/creators` → list of `CreatorFeatureRecord`:
  `creator_id`, `name`, `category`, `category_one_hot` (order matches Track
  B's `ml/schema.py::CREATOR_CATEGORIES` exactly), `log_subscriber_count`,
  `engagement_rate` (both computed from real data when available),
  `reputation_score` (**always null** — see gap below), `raw_text` /
  `thumbnail_urls` (staged for Track B's embedding step), `is_stub` (true
  if there's nothing to embed yet).
- `GET /feature-store/edges/collaborations` → list of `CollaborationEdge`
  (`source_creator_id`, `target_creator_id`, `weight`). Both directions
  populated per Track B's `ml/schema.py` requirement. Resolved from
  `creator_related_accounts` rows with `relation_type = "frequent_collaborator"`
  — `handle` there is free text, not a FK, so resolution is a
  case-insensitive match against every creator's own handles (`@`/`u/`/`r/`
  stripped). Rows that don't resolve are silently skipped, not an error —
  expect this until many more creators are seeded. **Ambiguous handles**
  (the same handle claimed by 2+ creator rows) are also treated as
  unresolvable rather than arbitrarily picking one — confirmed live
  2026-08-09 that Track A's pre-fix creator-dedup bug left real duplicate
  rows in production (two rows both claiming reddit handle "lebron"); their
  fix (`origin/track-a-data-infra` "Fix cross-platform creator-ID syncing")
  stops new duplicates but doesn't retroactively merge existing ones.
- `GET /feature-store/edges/sponsorships` → list of `SponsorshipEdge`
  (`creator_id`, `brand_id`, `content_id`, `platform`). Populated once
  `is_sponsored` is set — see the labeling pipeline below. Currently empty
  against real data because no real disclosure text has been found yet
  (21/21 real content rows checked, 0 sponsored), not because the pipeline
  hasn't run.

**Known gaps, flagged not fabricated:**
- `reputation_score`: Track B's schema expects this in the creator metadata
  segment, but **no Track A table has a reputation_score source column
  anywhere** (re-checked against Track A's latest work as of 2026-08-09 —
  their creator-ID dedup fix and Reddit profile enrichment don't touch
  this). Open cross-track item — needs either a new Track A column or a
  defined derivation formula.
- `co_occurs_with` edges (platform co-occurrence, PROJECT_PLAN.md Section
  3a): not built. Track A's schema still has no signal for "these creators
  appeared together in the same content" (no co-starring/tagging table).
  Would need either a new ingestion field or inference from data not
  currently collected.

Unit-tested against synthetic data (`backend/tests/test_feature_store.py`,
9 tests) and verified end-to-end through the live HTTP API against real
scraped content (Track A ran their first live bulk collection this week —
59 Instagram profiles, 113 Reddit profiles, 10 YouTube videos as of
2026-08-09).

### Labeling pipeline (`is_sponsored`, new Weeks 7-8)

`POST /labeling/run` (requires `X-API-Key` if configured) — scans every
`youtube_videos`/`instagram_posts`/`reddit_posts` row where `is_sponsored
IS NULL`, sets it to a real `true`/`false` (not left null), and records
matched phrases in `sponsorship_raw_matches`. Idempotent-safe: only
processes rows still null, so re-running after new content lands only
touches the new rows. No trigger/webhook wiring it automatically yet —
invoke manually (or from a script) after Track A lands new content.

Response: `{ youtube_videos: {checked, labeled_sponsored}, instagram_posts: {...}, reddit_posts: {...} }`.

**Detection approach** (`backend/app/labeling.py`): regex-based, matching
PROJECT_PLAN.md Section 1's own framing — `#ad`, `#sponsored`, `#spon`,
`#paidpartnership`, "sponsored by", "paid partnership", "paid promotion",
"in partnership with", "brought to you by", plus common misspellings
("sponser"/"sponsered", "spon-con"/"spon con"). Every pattern requires a
real word boundary so it can't fire inside an unrelated longer word/hashtag.

**This is the sole source of GAIL's treatment labels (PROJECT_PLAN.md
Section 1), so precision was validated deliberately, not just "it finds
#ad"** — `backend/tests/test_labeling.py`, 21 tests, split across:
- Positive cases covering every convention above.
- **Decoys targeting the exact regex risks a naive substring match would
  fall into**: `#adventure`/`#adidas` (must not match `#ad`), "advice"
  (must not match standalone "ad"), "spontaneous" (must not match
  "spon-con"), a brand name mentioned with no disclosure language, and a
  genuinely ambiguous "institutional partnership" phrasing (university
  affiliation, not a brand deal).
- **Two decoys pulled verbatim from real scraped content** (ATHLEAN-X
  YouTube descriptions, live DB, 2026-08-09): a 4600+ character
  self-promotional video description (own website/product links, zero
  actual sponsorship) and a professional-credentials bio (former team,
  university) — both correctly produce no match.
- Already run against all real content in the live DB: **21/21 rows
  checked, 0 labeled sponsored, 0 false positives** (matches manual
  verification against the same rows before the pipeline existed).

Text scrubbing (`app/text_processing.py::scrub_text` — URLs, HTML tags,
`@mentions` removed, whitespace collapsed) and temporal normalization
(`normalize_to_utc` — naive timestamps assumed UTC, aware ones properly
converted) also added this round (PROJECT_PLAN.md Section 2). Scrubbing is
wired into the feature store's `raw_text` staging; normalization is a
utility available for any datetime handling, though Postgres `timestamptz`
columns already normalize to UTC internally for anything already in the DB.

### Fusion Layer score (Track B → this API)

`POST /scores/compute`
```json
{ "creator_id": "758b86ea-266d-48dd-848e-564f47ad8275", "spillover_score": 0.6, "sentiment_risk_score": 0.7, "creator_feature_score": 0.5 }
```
Score fields must be finite and in `[0, 1]` (NaN/Infinity rejected with 422).
→ computes, persists, and returns a `FusionScoreResponse` (same shape, `creator_id` key).

`GET /scores/{creator_id}` → most recently computed score, 404 if none exists.

Formula (`backend/app/fusion.py`, PROJECT_PLAN Section 4) and placeholder
weights/risk-threshold/confidence-margin — **unchanged from Weeks 1-2**, still
not calibrated against held-out historical outcomes.

### Monitoring / alerts

`POST /alerts` (requires `X-API-Key` if configured) — body:
```json
{ "creator_id": "...", "severity": "high", "reason": "...", "source": "sentiment_propagation", "propagated_from_creator_id": null }
```
**`severity` is a strict enum** (`"low" | "medium" | "high"`) — Weeks
1-2 accepted any string; found via adversarial testing that this let
`"catastrophic_meltdown"` through undetected. Default `source="sentiment_propagation"`.

**`propagated_from_creator_id`** (nullable uuid, new Weeks 5-6): if this
alert exists because risk propagated from *another* creator's controversy
(PROJECT_PLAN.md Section 3b/5), that creator's id — added ahead of the
Weeks 14-15 Sentiment Propagation work landing so the shape is right when
Track D builds against it now, instead of forcing a second breaking change
later. Expect this to stay `null` until then.

`GET /alerts?creator_id=...&include_resolved=false` → list of alerts, newest
first (no auth required). This is what Track D's monitoring/alerts UI should poll.

### Auth (new Weeks 5-6)

Basic shared-secret auth via `X-API-Key` header, **off by default**. Set
`API_KEY` in `backend/.env` to enable — once set, all `/ingestion/*`
endpoints, `POST /scores/compute`, and `POST /alerts` require a matching
header (401 otherwise). Every `GET` endpoint and `POST /recommendations`
never require it — deliberately, since brand users and Track D's dashboard
need to read without a shared secret. This is intentionally minimal (one
shared key, no per-track keys or roles) — flagged as missing twice before
this, closing the basic gap rather than over-building auth for a 4-person
thesis capstone backend.

---

## Validation fixes (2026-08-09, found via adversarial self-check)

- **Fixed a 500 crash:** any request with `NaN` in a float field that has a
  `gt`/`ge`/`le` bound (e.g. `budget`, the three score fields) crashed with
  an unhandled 500 instead of a clean 422. Cause: Starlette's default JSON
  encoder for error responses is strict (`allow_nan=False`), but FastAPI's
  default validation-error handler echoes the raw invalid input back in the
  error body — trying to serialize a raw `NaN` float there raised
  `ValueError: Out of range float values are not JSON compliant`, unhandled.
  Fixed with a custom `RequestValidationError` handler in `main.py` that
  sanitizes non-finite floats before serializing (applies globally, not
  just to the field that surfaced it).
- **Fixed silent data corruption:** `budget: Infinity` previously passed the
  `gt=0` check (mathematically true) and then got silently serialized back
  as `null` in the response echo (Pydantic's default `Infinity`→`null` JSON
  behavior) — the client would see `"budget": null` with no error, hiding
  that an absurd value was accepted. Fixed with `allow_inf_nan=False` on
  `budget` and the three fusion score fields — both now cleanly rejected
  with 422.
- **Fixed a real ranking bug** in `/recommendations` (not just a validation
  gap): the Weeks 1-2 loop gated the FusionScore lookup on a single shared
  `is_mock_data` flag, so once *any* real creator was found to have no
  stored score, every creator *after* it in the loop silently stopped
  getting its real score looked up too (even creators that did have one).
  Split into `using_mock_creators` (fixed per-request) and
  `any_score_missing` (per-creator) so this can't happen.
- **Fixed a local-dev crash:** Track A's real schema has three Postgres-only
  `text[]` array columns (`creators.reddit_handles`,
  `youtube_videos.tags`, `instagram_posts.hashtags`). Declaring these with
  the plain Postgres `ARRAY` type meant those tables couldn't be created (or
  queried) at all against the SQLite local-dev fallback — `/recommendations`
  would crash with `OperationalError: no such table` instead of falling
  through to its mock-data path. Fixed with
  `.with_variant(JSON(), "sqlite")` so the same model works against both.
- **Fixed a validation gap:** `alerts.severity` was a freeform `str`
  despite being documented as an enum — tightened to
  `Literal["low", "medium", "high"]`.

## What's real vs. placeholder (as of 2026-08-09, Weeks 7-8)

| Piece | Status |
|---|---|
| FastAPI app, all routes, request/response validation | Real, working |
| DB models matching Track A's live schema (incl. `brands`, `creator_related_accounts`) | Real, working (re-diff if their schema changes) |
| DB (SQLite local fallback / real Supabase Postgres via `DATABASE_URL`) | Both real and verified — connected to the live Supabase instance with real content now landing (Track A's first live bulk collection this week) |
| Track C-owned table migrations (`fusionscore`, `riskalert`) | Real, tracked in `backend/migrations/` after the incident above — no longer relying on `create_all()` for schema evolution |
| Ingestion upsert logic (8 endpoints) | Real, working, but secondary path (see breaking-change note #3) |
| Fusion formula math | Real formula, placeholder weights/risk-threshold/confidence-margin |
| Recommendation budget/region/demographic/product_category/platform_preference filtering | Fully real (see above), heuristic-based (placeholder cost rate, keyword-overlap text match) |
| Feature-store pipeline (`/feature-store/*`) | Real for numeric/categorical/edge data, verified against real scraped content; text now scrubbed before staging; CLIP/BERT embeddings intentionally not computed here (Track B, Weeks 9-10); `reputation_score` and `co_occurs_with` are genuine gaps, not placeholders — see feature-store section |
| **Disclosure-tag (`is_sponsored`) labeling pipeline** | **Real, built and run against live data** (Weeks 7-8) — see labeling section. 21/21 real rows labeled, 0 false positives, precision-validated against real decoy text plus synthetic near-misses |
| Text scrubbing / temporal normalization | Real (`app/text_processing.py`), Section 2 |
| Spillover / sentiment-risk / creator-feature scores | Always caller-supplied (via `/scores/compute`) or placeholder 0.5 — no real GAIL/Temporal/feature-extraction pipeline wired in yet |
| Auth | Basic (shared `API_KEY`), off by default — see Auth section |

## Running locally

```
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```
Visit `http://127.0.0.1:8000/docs` for interactive Swagger UI. No `.env`
needed for local dev — defaults to `sqlite:///./fusion_backend.db` and now
creates the full local schema (including Track A-mirrored tables) so
`/recommendations` etc. work end-to-end without a real DB. Copy
`.env.example` to `.env` and set `DATABASE_URL` to connect to the real
Supabase instance — get the connection string from the user directly (never
committed, never in memory).
