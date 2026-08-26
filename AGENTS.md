# AGENTS.md — Track C (Fusion + Backend)

> Scope: this worktree is `track-c-fusion-backend` only. For cross-track state read `CAPSTONE_NEXT_STEPS.md` at repo root — it supersedes this file, `CLAUDE.md`, and memory. Re-verify live counts before acting; data changes daily.

## Read first
- `CAPSTONE_NEXT_STEPS.md` — single source of truth (live DB state, P0/P1/P2, review bars, standing rules). Updated 2026-08-22, commit `deaf630`.
- `HANDOFF.md` — track-C current state, open items, exact next steps (pair recount, P1.6 blocker).
- `API_CONTRACTS.md` — endpoint shapes, CORS/auth incidents, labeling breakdown (61 events: 58 IG / 3 YT / 0 Reddit).
- `CLAUDE.md` — behavioral rules (verify consumer not writer, `enabled != reachable`, etc.).

## Ownership — do not blur
- **Track C owns:** `backend/app/fusion.py`, `feature_store.py`, `labeling.py`, `routers/scores.py|feature_store.py|labeling.py`, `models.FusionScore/RiskAlert`, `backend/migrations/`. Resolves `creator_related_accounts` -> weighted edges; runs disclosure labeling (`is_sponsored`).
- **Does NOT own:** scraping/DB population (`scripts/ingestion/`), graph construction / GAIL / bot / CLIP-BERT (`ml/`), UI/Docker. Track A's orchestrator writes **direct to Postgres via `DATABASE_URL`** and bypasses `POST /ingestion/*` entirely — that path is manual/testing only (`backend/app/routers/ingestion.py:1`).

## Setup & run

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
.\.venv\Scripts\python.exe -m pytest                         # 49 tests
.\.venv\Scripts\python.exe -m pytest tests/test_labeling.py -k test_name  # single test
.\.venv\Scripts\python.exe -m pytest tests/test_labeling_router.py -k test_force
```

- No `DATABASE_URL` needed for local dev — defaults to `sqlite:///./fusion_backend.db` (`backend/app/config.py:17`). Copy `backend/.env.example` -> `backend/.env` for Supabase.
- **Supabase DSN must use pooler** (IPv4): `postgresql://postgres.fhbgbtxdtfluzohxyivg:<pwd>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres` (`CAPSTONE_NEXT_STEPS.md:441`). Direct host `db.fhbgbtxdtfluzohxyivg.supabase.co` is IPv6-only and fails `WinError 10051` on this machine.
- `backend/.env` is gitignored and **disappears between sessions** — recreate from credential in prior turns, never ask user to re-share, never commit.
- Docker path on this host: `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe`.

## Database quirks
- `init_db()` (`backend/app/database.py:11`): on Postgres creates **only** `TRACK_C_OWNED_TABLES` (`FusionScore`, `RiskAlert`); on SQLite creates full `SQLModel.metadata` for local dev. `create_all()` **never alters** existing tables — any column added to an existing Track C table needs a hand-written `backend/migrations/*.sql` applied manually to live DB (`backend/migrations/README.md:1`). Incident `2026-08-09`: `RiskAlert.propagated_from_creator_id` added to `models.py` but never reached live table -> `UndefinedColumn` on `POST /alerts`.
- Postgres `text[]` columns (`creators.reddit_handles`, `youtube_videos.tags`, `instagram_posts.hashtags`) use `_string_array_column()` = `ARRAY(String).with_variant(JSON(), "sqlite")` (`backend/app/models.py:47`). Must be `ARRAY(String)` not `ARRAY(str)` or reads from real Postgres crash; without variant local SQLite has no table.
- `creator_related_accounts` requires exact `relation_type="frequent_collaborator"` and both endpoints already in `creators` (`CAPSTONE_NEXT_STEPS.md:375`). `category` CHECK is `athlete|team|league|fitness_influencer|lifestyle_influencer|other`.

## Architecture
- Entrypoint `backend/app/main.py:12` — `CORSMiddleware` allowlist from `CORS_ALLOW_ORIGINS` (default `localhost:3000,127.0.0.1:3000`, `allow_credentials=False`). Curl does not enforce CORS — only a real browser test catches missing middleware (8-week incident, `API_CONTRACTS.md:16`).
- Custom `validation_exception_handler` (`backend/app/main.py:48`) sanitizes `NaN`/`Infinity` via `_sanitize_non_finite` — without it `budget: NaN` returns 500 not 422. Fields `budget`/`spillover_score`/`sentiment_risk_score`/`creator_feature_score` have `allow_inf_nan=False`.
- Config `backend/app/config.py:6` via `pydantic-settings` from `.env`. Fusion weights `0.4/0.3/0.3` (`FUSION_WEIGHT_*`), `backend/app/fusion.py:18` margin `8.0`, risk `0.3` -> `-10pts` — all placeholder until Track B calibration.
- Auth `backend/app/auth.py:14` — single `X-API-Key` header, **off when `API_KEY` unset** (local dev). Only `/ingestion/*`, `POST /scores/compute`, `POST /alerts`, `POST /labeling/run` require it; all `GET` and `POST /recommendations` never do.

## Feature store — read-only, live recomputed
- `GET /feature-store/creators|edges/collaborations|edges/co-occurrence|edges/sponsorships` (`backend/app/routers/feature_store.py:1`, logic in `backend/app/feature_store.py:1`). No caching, no CLIP/BERT here (stages scrubbed `raw_text`/`thumbnail_urls` for Track B).
- `build_collaboration_edges` (`backend/app/feature_store.py:179`): resolves `creator_related_accounts.handle` case-insensitive with `@/u//r/` stripped; **ambiguous handles (same normalized handle claimed by 2+ creators) -> unresolvable**, never last-writer-wins (confirmed live `lebron` duplicate). Reports 2 directed rows per pair — count distinct pairs via `sorted((a,b))`.
- `build_co_occurrence_edges` from `reddit_post_creators` junction; weight = shared post count.
- `build_sponsorship_edges` requires `is_sponsored=true AND brand_id IS NOT NULL AND creator_id IS NOT NULL` — sponsorship *events* (61) != *edges* (16) until Track A backfills `brand_id`.

## Labeling pipeline — sole GAIL treatment source
- `POST /labeling/run` (`backend/app/routers/labeling.py:35`, regex in `backend/app/labeling.py:24`): default = `is_sponsored IS NULL` only; `?force=true` reprocesses all rows. Track A's upsert never touches `is_sponsored`/`sponsorship_raw_matches`, so **re-run `force=true` after any Track A text correction** (caption truncation, re-scrape).
- `InstagramPost.has_paid_partnership_label=true` forces `is_sponsored=true` with `native:paid_partnership_label` audit trail regardless of caption (`backend/app/routers/labeling.py:55`) — covers collab posts with `caption=None` (e.g. `DUkDWOYiL8x`).
- Precision-first: `sponsored by` / `in partnership with` hit 5 false positives at 4x scale (Reddit 4/4, IG 1/1) — organizational/third-party mentions, not creator disclosure (`API_CONTRACTS.md:61`). Reverted data-only, no regex loosening. Do not inflate low counts by loosening patterns.

## Testing
- In-memory SQLite needs `poolclass=StaticPool` or each `Session` gets empty DB (`backend/tests/test_labeling_router.py:21`).
- Use `c = TestClient(app)` with `app.dependency_overrides[get_session]` — **never** `with TestClient(app) as c:` — that fires `on_event("startup")` -> `init_db()` against the real `DATABASE_URL` engine, silently hitting prod Supabase (`backend/tests/test_labeling_router.py:40`).

## Workflow
- Verify live DB via REST before trusting docs (`CAPSTONE_NEXT_STEPS.md:259`); commit+push `CAPSTONE_NEXT_STEPS.md`/`HANDOFF.md` immediately after any verified change — other tracks only see it via `origin`.
- Current blocker `HANDOFF.md:3`: no persisted Track B checkpoint exists (`torch.save`/`.pt`/`pth` absent, LOO-CV trains 10 throwaways) — `spillover_score` stays flat `0.5` placeholder. Awaiting user choice: (A) Track C trains single prod model at startup using `ml/gail_model.py` as lib, or (B) stay placeholder. Do not start wiring without that decision.
- `reputation_score` is always `None` — no source column exists anywhere; don't fabricate.
