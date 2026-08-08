# API Contracts — Fusion + Backend (Track C)

Owner: Track C (Fusion+Backend). Updated whenever the contract changes — treat
edits to this file as high-signal for Tracks A/B/D, since there's no live
channel between sessions, only git.

**Status as of 2026-08-08 (Weeks 1-2 deliverable):** all endpoints below are
live and running (FastAPI + SQLModel, `backend/`), backed by SQLite locally.
Ranking/scoring logic is a **stub** — see "What's real vs. placeholder" at the
bottom. Full OpenAPI/Swagger UI is auto-generated at `/docs` when the server
is running (`GET /openapi.json` for the raw spec).

Base URL (local dev): `http://127.0.0.1:8000` (or whatever port you run
uvicorn on). No auth yet — add before any non-local deployment.

---

## Cross-track dependency flags

- **Track A (Data/Infra):** the `Creator` / `YouTubePost` / `InstagramPost` /
  `RedditPost` models below are Track C's best guess at Track A's schema,
  taken from PROJECT_PLAN.md Section 1. **No `SCHEMA.md` has been published
  on `origin/track-a-data-infra` yet** (checked via `git show` as of
  2026-08-08). Once it lands, Track C will reconcile field names/types and
  flag any breaking changes here.
- **Track B (ML-Core):** `POST /scores/compute` expects `spillover_score`,
  `sentiment_risk_score`, `creator_feature_score` each as floats in `[0, 1]`.
  No `GRAPH_SCHEMA.md` published yet on `origin/track-b-ml-core`. Track B
  should treat this endpoint's request shape as the target output format for
  the GAIL branch, Temporal branch, and feature-extraction pipeline
  respectively.
- **Track D (Frontend+App):** build against the schemas below. `POST
  /recommendations` and `GET /scores/{id}` responses include an
  `is_mock_data` / `is_placeholder_formula` boolean — **check it** before
  treating scores as real; today it will almost always be `true`.

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

Response: `{ query, results: [InfluencerRecommendation...], is_mock_data }`

`InfluencerRecommendation`:
```json
{
  "creator_unique_id": "c1",
  "name": "TestCreator",
  "category": "fitness",
  "youtube_handle": "@testcreator",
  "instagram_handle": null,
  "reddit_handle": null,
  "final_score": 60.0,
  "confidence_low": 52.0,
  "confidence_high": 68.0,
  "estimated_reach": null,
  "score_breakdown": { "spillover_score": 0.6, "sentiment_risk_score": 0.7, "creator_feature_score": 0.5,
                        "weight_spillover": 0.4, "weight_sentiment_risk": 0.3, "weight_creator_feature": 0.3 }
}
```

Current behavior: reads real `Creator` rows from the DB if any exist, joins
each to its latest stored `FusionScore` if one exists; otherwise fills in
with mock creators / a placeholder 0.5/0.5/0.5 fusion score. **Budget/region/
demographic filtering is not implemented yet** — the endpoint accepts and
echoes these fields but doesn't filter or rank by them. `estimated_reach` is
always `null` for now (planned: engagement-per-rupee proxy, not sales).

### Ingestion (Track A → this API)

- `POST /ingestion/creators` — body: list of `CreatorIngest` (see schema
  below). Upserts by `unique_id`.
- `POST /ingestion/youtube` — body: list of `YouTubePostIngest`. Upserts by
  `(creator_unique_id, platform_post_id)`.
- `POST /ingestion/instagram` — body: list of `InstagramPostIngest`. Same
  upsert key.
- `POST /ingestion/reddit` — body: list of `RedditPostIngest`. Same upsert
  key.

All four return `{ received, created, updated }`.

`CreatorIngest`:
```json
{
  "unique_id": "c1", "name": "TestCreator", "category": "fitness",
  "youtube_handle": "@testcreator", "instagram_handle": null, "reddit_handle": null,
  "related_accounts": ["@relatedhandle"], "prior_endorsements": ["BrandX 2025"],
  "bio_text": "...", "posting_timezone": "Asia/Kolkata",
  "reputation_score": null, "is_bot_suspected": false
}
```

`YouTubePostIngest` / `InstagramPostIngest` / `RedditPostIngest`: each keyed
by `creator_unique_id` + `platform_post_id`, plus platform-specific fields
(title/description/thumbnail for YouTube, caption/media_type for Instagram,
subreddit/body/score for Reddit) + `published_at`, engagement counts,
`is_sponsored`. Full field list in `backend/app/schemas.py`.

**Open question for Track A:** confirm whether `is_sponsored` should be
computed upstream (in your disclosure-tag detection step, per PROJECT_PLAN
Section 1/2) and sent as-is, or left for Track C to derive from raw
caption/description text. Current assumption: **Track A sends it
pre-computed**, since that's where the disclosure-tag detection logic lives
per the plan. Flag if that's wrong.

### Fusion Layer score (Track B → this API)

`POST /scores/compute`
```json
{ "creator_unique_id": "c1", "spillover_score": 0.6, "sentiment_risk_score": 0.7, "creator_feature_score": 0.5 }
```
→ computes, persists, and returns a `FusionScoreResponse`:
```json
{
  "creator_unique_id": "c1", "final_score": 60.0, "confidence_low": 52.0, "confidence_high": 68.0,
  "risk_adjustment": 0.0, "breakdown": { ... }, "computed_at": "2026-08-08T16:32:13Z",
  "is_placeholder_formula": true
}
```

`GET /scores/{creator_unique_id}` → same shape, returns the most recently
computed score, 404 if none exists yet.

Formula (`backend/app/fusion.py`, PROJECT_PLAN Section 4):
`final_score = clamp(100 * (w1*spillover + w2*sentiment_risk + w3*creator_feature) + risk_adjustment, 0, 100)`

- Default weights: `w1=0.4 (spillover), w2=0.3 (sentiment_risk), w3=0.3 (creator_feature)` — tunable via env vars (`FUSION_WEIGHT_*`), **not yet calibrated** against held-out historical outcomes.
- `risk_adjustment`: flat `-10` points if `sentiment_risk_score < 0.3`, else `0`. Placeholder heuristic — will be replaced once Track B's real sentiment propagation output is available.
- Confidence bounds: flat `±8` points. Placeholder — will be replaced with bootstrapped/ensemble variance from the GNN per PROJECT_PLAN Section 4 once Track B ships that.

### Monitoring / alerts

`POST /alerts` — body: `{ creator_unique_id, severity ("low"|"medium"|"high"), reason, source }` (default `source="sentiment_propagation"`). Meant for Track B to call once sentiment propagation risk flags are real; any track can call it manually for now.

`GET /alerts?creator_unique_id=...&include_resolved=false` → list of alerts, newest first. This is what Track D's monitoring/alerts UI should poll.

---

## What's real vs. placeholder (as of 2026-08-08)

| Piece | Status |
|---|---|
| FastAPI app, all routes, request/response validation | Real, working |
| DB (SQLite local / Postgres via `DATABASE_URL` env var) | Real, working. Postgres untested — waiting on Track A's Supabase connection string |
| Ingestion upsert logic | Real, working |
| Fusion formula math | Real formula, placeholder weights/risk-threshold/confidence-margin |
| Recommendation ranking (budget/region/demographic filtering) | Not implemented — accepts and echoes the fields only |
| Spillover / sentiment-risk / creator-feature scores | Always caller-supplied or placeholder 0.5 — no real GAIL/Temporal/feature-extraction pipeline wired in yet |
| Auth | None |

## Running locally

```
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```
Visit `http://127.0.0.1:8000/docs` for interactive Swagger UI. No `.env`
needed for local dev — defaults to `sqlite:///./fusion_backend.db`. Copy
`.env.example` to `.env` and set `DATABASE_URL` once Track A shares the
Supabase connection string.
