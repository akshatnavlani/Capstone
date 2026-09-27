# manual.md — Review 1 — How to Manually Run the Review 1 Project State

> Branch `review-1` `123f489` (from `main` `816a19e` Review 1 closed 2026-08-26). Frozen live DB: **259 creators / 54 pairs (138 checks, 53 events, 40 yielding, 23 directed/19 undirected, 170 graph) / 1,414 co_occurs_with (giant 185, 72 isolates) / 6,153 posts (1,607 YT /1,811 IG 100% dated /2,748 Reddit) / 58 is_sponsored IG +3 YT +0 Reddit / 19 brands / 134k comments**. End-to-end wired `A 918fb5c` → `B 5f8706f/c6488a6` → `C b3905ef/65ec502` → `D 5861f4d/be89dc1`. Honest small-N: `N=10` effective, `hw≈3.28` trained `±13pts`, `hw≈5.25` inferred `±21pts`.

This doc is for a reviewer who has just `git clone`'d and has never seen the worktrees. It uses only executable sources (`supabase/migrations/*`, `scripts/*`, `backend/*`, `frontend/*`, `ml/*`) — no guesses.

---

## 0. Clone & Checkout

```powershell
git clone https://github.com/akshatnavlani/Capstone.git
cd Capstone
git fetch origin
git checkout review-1          # or git checkout review1-2026-08-26 tag
git log --oneline -2           # expect 123f489 review-1 assemble + 816a19e Review 1 closed
```

Repo layout on this branch (unlike `main` which was docs-only `AGENTS.md:1`):

```
supabase/migrations/  7 files  — Track A schema (creators, creator_related_accounts, youtube_*, instagram_*, reddit_*, brands, reddit_post_creators, has_paid_partnership_label)
scripts/ingestion/    24 py    — Track A scraping + pair_count.py:1 (canonical 54)
scripts/              5  py    — Track B ML (build_real_hetero_data.py:60, train_prod_model.py:492, train_holdout_round3.py:183)
ml/                   14 py    — Track B GAT/GAIL (gail_model.py:19, inference.py:201, feature_extraction.py:64)
models/gail_checkpoint.pt 3.7M — Track B prod artifact c6488a6 (also backend/models/ vendored copy)
backend/app/          20 py    — Track C FastAPI (main.py:1, fusion.py:57, spillover.py:64, feature_store.py:115)
frontend/src/         12 ts    — Track D Next 16 (SpilloverBadge.tsx:51, api.ts:15, dashboard/page.tsx:15)
```

No `opencode.json`. No CI. `.env` files are gitignored — copy from `.env.example` (see §1).

---

## 1. Prerequisites & Env

**System:** Python 3.11, Node 20, `psycopg2-binary` (for `pair_count.py`), `curl`, Git. Docker optional (binary at `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe` `AGENTS.md:1` non-standard path — add to `PATH` if `docker --version` fails).

**Env files — never commit real secrets (`CAPSTONE_NEXT_STEPS.md:920` password leaked, rotate before submission):**

```powershell
# Root / Track A (pair_count + orchestrator) — Pooling required, direct host is IPv6-only WinError 10051 AGENTS.md:1
Copy-Item .env.example .env   # then edit:
# DATABASE_URL=postgresql://postgres.fhbgbtxdtfluzohxyivg:<pwd>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
# YOUTUBE_API_KEY=... (optional for re-running discover_youtube_handles.py; not needed for demo)
# No OPENCLI_PROFILE needed for review demo (no scraping)

# Backend (Track C) — from backend/.env.example:1
Copy-Item backend/.env.example backend/.env
# Edit backend/.env: set same DATABASE_URL as above (postgresql+psycopg2, not sqlite)
# CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
# API_KEY= (leave empty for local frictionless auth; require_api_key bypasses when unset auth.py:14)
# FUSION_WEIGHT_SPILLOVER=0.4  FUSION_WEIGHT_SENTIMENT_RISK=0.3  FUSION_WEIGHT_CREATOR_FEATURE=0.3

# Frontend (Track D) — from frontend/.env.local.example:1
Copy-Item frontend/.env.local.example frontend/.env.local
# Edit frontend/.env.local: NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

**Supabase project:** `https://fhbgbtxdtfluzohxyivg.supabase.co` — anon publishable key for REST read-only checks (orchestrator has no `psycopg2` `AGENTS.md:1`):

```powershell
$K="sb_publishable_l-j6rKSWn4DuT2lCJHB1zA_8T1XbUvV"  # from CAPSTONE_NEXT_STEPS.md:259
curl -s "https://fhbgbtxdtfluzohxyivg.supabase.co/rest/v1/creators?select=creator_id&limit=1" -H "apikey: $K" | head
# count: curl -s "https://.../rest/v1/creators?select=creator_id" -H "apikey: $K" -H "Prefer: count=exact" -H "Range: 0-0" -D - -o /dev/null | grep -i content-range
# expect ~259
```

Migrations are already live on that project. If you need a local DB, run the 7 + 3 migrations in order:

```powershell
psql $env:DATABASE_URL -f supabase/migrations/20260808163402_init_schema.sql
psql $env:DATABASE_URL -f supabase/migrations/20260809000000_fix_missing_reddit_indexes.sql
psql $env:DATABASE_URL -f supabase/migrations/20260809010000_add_brands.sql
psql $env:DATABASE_URL -f supabase/migrations/20260809020000_dedupe_creators.sql
psql $env:DATABASE_URL -f supabase/migrations/20260810000000_reddit_post_creators_junction.sql
psql $env:DATABASE_URL -f supabase/migrations/20260810000000_reddit_topic_subs.sql
psql $env:DATABASE_URL -f supabase/migrations/20260811000000_paid_partnership_label.sql
psql $env:DATABASE_URL -f backend/migrations/0001_init_fusion_alerts.sql
psql $env:DATABASE_URL -f backend/migrations/0002_add_alerts_propagated_from.sql
psql $env:DATABASE_URL -f backend/migrations/0003_add_fusion_spillover_basis.sql
```

---

## 2. Verify Data (no scraping, read-only)

**Canonical pair count — sole definition `scripts/ingestion/pair_count.py:1` `AGENTS.md:1`:**

```powershell
# From repo root, with .env DATABASE_URL set (pooler)
python scripts/ingestion/pair_count.py
# Expected (2026-08-26 frozen):
# COMPUTABLE TRAINING PAIRS   54   (target >= 20)
#   event x neighbour checks evaluated    138
#   dated sponsorship events               53   (54 IG +3 YT +0 Reddit, 53 connected)
#   events yielding at least one pair      40
#   distinct directed creator pairs        23
#   distinct undirected creator pairs      19
#   collaboration edge pairs (graph)      170
#   why rest fail: neighbour has NO activity BEFORE 37 / AFTER 9 / no dated activity 38

python scripts/ingestion/pair_count.py --json   # machine-readable same 4 readings + fail buckets

python scripts/ingestion/loop_stats.py
# Expected: creators 259, IG 163/259 attempted 56 with content, YT 259/259 attempted 41 handles 40/41 deepened, Reddit 230/259 attempted 117 with content 24 name-gated 5 untouched, computable_pairs 54

# Direct SQL spot-checks via pooler (psycopg2) or REST:
# select count(*) from creators; -- 259
# select count(*) from creator_related_accounts; -- 873 rows / 203 directed distinct / 170 undirected
# select count(*) from instagram_posts; -- 1811 (100% posted_at not null)
# select count(*) from instagram_posts where is_sponsored=true; -- 58
# select count(*) from brands; -- 19
```

If counts differ, data changed since frozen `816a19e` — re-run is expected; do not hand-roll a different pair definition.

**ML artifact — offline inference, no DB needed after training:**

```powershell
# Track B prod artifact c6488a6, trained once on all 54 pairs (N=10 effective, not LOO)
dir models/gail_checkpoint.pt          # 3,864,983 bytes
dir backend/models/gail_checkpoint.pt  # vendored copy 65ec502 — same 3.7M, either path works

# With .venv (see §4 for setup), inference offline:
python -c "from ml.inference import load_predict, get_model_info; print(get_model_info()['pair_count']); print(load_predict('c086bf2e-80f8-4902-b155-bbec78610798'))"
# → {"computable_pairs":54,...} + {"spillover_score":0.339, "basis":"trained", "confidence_low":-2.94, "confidence_high":3.618} for CarryMinati
python -c "from ml.inference import load_predict; print(load_predict('89972049-1966-4f17-9c9d-e3343c62d090'))"
# → {"spillover_score":1.191, "basis":"inferred", "confidence_low":-4.055, "confidence_high":6.436} AB de Villiers degree 1
python -c "from ml.inference import load_predict; print(load_predict('78e4817c-077f-4b4c-95de-2a8c043e5cf5'))"
# → IsolatedCreatorError: Creator _bungy_lover_.01 is graph-isolated (degree 0 on collaborates_with + co_occurs_with) — no spillover can be inferred

# Missing checkpoint → FileNotFoundError, never fabricated (spillover.py:64 fallback to placeholder 0.5)
```

---

## 3. Backend — Fusion+Backend `backend/app/main.py:1` + `backend/requirements.txt:1`

**Install & run (from `backend/`):**

```powershell
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # FastAPI 0.141.1 + SQLModel + psycopg2-binary + uvicorn, no torch needed (lazy import)
# If you need GAIL live (not placeholder fallback), also in repo root:
# uv pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124; uv pip install -r requirements.txt  # Track B 69 tests need torch

uvicorn app.main:app --reload --port 8000   # from backend/
# or: python -m uvicorn app.main:app --reload --port 8000
```

**Health & feature-store (live Supabase pooler `DATABASE_URL`):**

```powershell
curl http://127.0.0.1:8000/health
# {"status":"ok","db_connected":true,"version":"0.1.0"}

curl http://127.0.0.1:8000/feature-store/edges/sponsorships | python -m json.tool | head
# 16 edges (reconciles is_sponsored=true AND brand_id IS NOT NULL — was 10 before brand backfill)

curl http://127.0.0.1:8000/feature-store/creators | python -c "import sys,json; print(len(json.load(sys.stdin)))"
# 259

curl http://127.0.0.1:8000/feature-store/edges/collaborations | python -c "import sys,json; print(len(json.load(sys.stdin)))"
# 340 directed (170 undirected)

curl http://127.0.0.1:8000/feature-store/edges/co-occurrence | python -c "import sys,json; print(len(json.load(sys.stdin)))"
# 1414 directed (was 0 before Reddit junction)
```

**Labeling (if you change captions/text — not needed for frozen demo):**

```powershell
curl -X POST "http://127.0.0.1:8000/labeling/run" -H "X-API-Key: $env:API_KEY"  # only where is_sponsored IS NULL
curl -X POST "http://127.0.0.1:8000/labeling/run?force=true" -H "X-API-Key: $env:API_KEY"  # reprocess all — needed after fixing 100-char truncation CAPSTONE_NEXT_STEPS.md:2
# Returns {"youtube_videos":{"checked":..., "labeled_sponsored":...}, "instagram_posts":..., "reddit_posts":...}
```

**Fusion — 3 archetypes (honest small-N, `backend/app/fusion.py:57` `margin=hw*100*w1` clamped [0,100], `w1=0.4` only real, `w2=0.5` placeholder `CAPSTONE_NEXT_STEPS.md:822`):**

```powershell
# Trained — Virat Kohli c4b20dc1-14f2-48e9-8bd5-7131af29049f is in GAIL labeled N=10 (hw≈3.28 → ±13pts, still wide due N=10 + propensity 1.000 CAPSTONE_NEXT_STEPS.md:795)
curl http://127.0.0.1:8000/scores/c4b20dc1-14f2-48e9-8bd5-7131af29049f | python -m json.tool
# {"creator_id":"c4b20...","final_score":100.0,"confidence_low":0.0,"confidence_high":100.0,"risk_adjustment":0.0,
#  "breakdown":{"spillover_score":21.615880966186523,"sentiment_risk_score":0.5,"creator_feature_score":0.5,"weight_spillover":0.4,"weight_sentiment_risk":0.3,"weight_creator_feature":0.3},
#  "spillover_basis":"trained","computed_at":"...","is_placeholder_formula":true}

# Inferred — AB de Villiers 89972049 degree 1, not labeled, GAT inductive (hw≈5.25 → ±21pts 1.6×)
curl http://127.0.0.1:8000/scores/89972049-1966-4f17-9c9d-e3343c62d090 | python -m json.tool
# {"spillover_basis":"inferred","breakdown":{"spillover_score":1.1906001567840576,...},"confidence_low":0.0,"confidence_high":100.0}

# Isolated — _bungy_lover_.01 78e4817c degree 0 on both graphs → IsolatedCreatorError → placeholder 0.5 never inferred (spillover.py:64)
curl http://127.0.0.1:8000/scores/78e4817c-077f-4b4c-95de-2a8c043e5cf5 | python -m json.tool
# {"spillover_basis":"isolated","final_score":50.0,"confidence_low":40.0,"confidence_high":60.0,"breakdown":{"spillover_score":0.5,"sentiment_risk_score":0.5,"creator_feature_score":0.5,...}}

# Batch recommendations — what Track D actually calls (frontend/src/lib/api.ts:15 POST /recommendations, budget hard, platform hard, region/demographic/product soft):
curl -X POST http://127.0.0.1:8000/recommendations -H "Content-Type: application/json" -d "{\"product_category\":\"athlete\",\"budget\":200000000,\"max_results\":5}" | python -m json.tool
# top result is Virat trained 21.61→100, includes spillover_basis + confidence_low/high per row; other budgets surface inferred/isolated:
curl -X POST http://127.0.0.1:8000/recommendations -H "Content-Type: application/json" -d "{\"product_category\":\"athlete\",\"budget\":5000000,\"max_results\":10}" | python -m json.tool | grep -A2 spillover_basis
# shows mixed: PV Sindhu inferred 8.59 [0-100], isolated rows 0.5 [40-60]

# Auto-resolve: POST /scores/compute without spillover_score uses GAIL live (spillover.py:64), never crashes
curl -X POST http://127.0.0.1:8000/scores/compute -H "Content-Type: application/json" -H "X-API-Key: $env:API_KEY" -d "{\"creator_id\":\"c4b20dc1-14f2-48e9-8bd5-7131af29049f\",\"sentiment_risk_score\":0.5,\"creator_feature_score\":0.5}" | python -m json.tool
# same trained basis as GET above, persists fusionscore row with spillover_basis
```

**CORS verification (curl hid bug for 8 weeks `CAPSTONE_NEXT_STEPS.md:965`, must check headers):**

```powershell
curl -i http://127.0.0.1:8000/health -H "Origin: http://localhost:3000" | Select-String access-control
# access-control-allow-origin: http://localhost:3000  ✓
curl -i -X OPTIONS http://127.0.0.1:8000/recommendations -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST" | Select-String access-control
# access-control-allow-origin: http://localhost:3000 + allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT ✓
# disallowed origin → no header (not wildcard) — correct
```

**Tests (49, no torch needed — spillover.py lazy):**

```powershell
cd backend; .\.venv\Scripts\Activate.ps1; pytest backend/tests -q  # but from backend/ just: pytest tests -q
# 49 passed
```

---

## 4. ML — Track B (`requirements.txt:1` CUDA 12.4, 69 tests)

```powershell
# From repo root (review-1)
python -m venv .venv; .\.venv\Scripts\Activate.ps1
# GPU machine (like RTX 3050 verified): uv pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124; uv pip install -r requirements.txt
# CPU-only: pip install -r requirements.txt (or uv pip install -r requirements.txt — CPU wheels from PyPI)
python scripts/verify_environment.py
# torch 2.6.0+cu124, PyG 2.8.0.post1, CUDA True — OK (or CPU fallback)

pytest tests -q  # from repo root with .venv: 69 passed, ~12s (bot_detection, causal_regularization, exposure, gail_model, schema, training, weighted_sage_conv)

python scripts/build_real_hetero_data.py  # expects 5 JSON dumps + DATABASE_URL — for review, use train_prod_model instead (DB-direct)
python scripts/compute_training_pair_deltas.py  # writes training_pair_deltas.json (34/54 same-platform computable, 20 cross-platform-only)
python scripts/train_holdout_round3.py    # LOO over N=10, throwaway models — no checkpoint, headline 67.19 vs 67.36 baseline (99% Kohli outlier), ex-Kohli ~14% win — not for deployment
python scripts/train_prod_model.py        # prod entrypoint: train ONCE on all 10 nodes 100 epochs, hw≈3.28, writes models/gail_checkpoint.pt + feature_scaler.json (already vendored c6488a6 — re-running is optional, needs DATABASE_URL pooler)
```

Do not run `train_prod_model.py` unless you intend to overwrite the frozen `c6488a6` checkpoint — reviewer runs inference only.

---

## 5. Frontend — Track D `frontend/package.json:1` (Next 16 + Tailwind v4)

```powershell
cd frontend
npm ci                     # or npm install (package-lock.json 6895 lines, frontend/README.md 36B is create-next-app stub)
npm run lint               # eslint — must pass (D be89dc1 lint PASS)
npm run build              # next build — must pass (8/8 static pages, 443ms, Turbopack). Verifies deployable before claiming it AGENTS.md:1
npm run dev                # next dev --port 3000 (or -- --port 3000). Then open http://localhost:3000
# Routes:  /  →  /brand-input  →  /dashboard  →  /explainability  →  /monitoring (5 routes, all 200)
# Env: NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 (frontend/.env.local)
```

**Manual browser flow (the Review 1 demo):**

1. Open `http://localhost:3000` → click `Start a new brand request` → `http://localhost:3000/brand-input`.
2. Fill **Brand Input** (`frontend/src/app/brand-input/page.tsx:12`): `Product/Category: athlete`, `Budget: 200000000` (or `5000000` to surface inferred/isolated mix), `Target Region/Demographic` optional proxy, `Platform` optional. On submit, `postRecommendations` stores `BrandRecommendationResponse` in `sessionStorage` (`frontend/src/lib/useStoredRecommendationResult.ts:9`) and navigates to `/dashboard`.
3. **Dashboard** (`frontend/src/app/dashboard/page.tsx:15`): shows `Results for "athlete", budget ₹…`, amber banner if `is_mock_data` (no scores), cards with `final_score`, `confidence {low}–{high}`, and `SpilloverBadge` (`frontend/src/components/SpilloverBadge.tsx:51`):
   - **Trained** emerald `Trained — N=10 ±13pts` — Virat Kohli `c4b20` spillover `21.61` → `final 100 [0-100]`, raw `21.61` triggers amber `out-of-range` note (GAIL outside 0-1, final clamped `[0,100]`).
   - **Inferred** violet outline `Inferred — wide CI ±21pts` — PV Sindhu `8.59` or AB `1.19` → `[0-100]`, tooltip `hw≈5.25 1.6×`.
   - **Isolated** zinc dashed `Placeholder — no graph signal` `±10pts` — Athletics `_bungy` `0.5` → `50 [40-60]`, subtext `no graph signal — degree 0 on collaborates_with + co_occurs_with (IsolatedCreatorError → placeholder 0.5, never inferred)` (`isolatedNote()`).
   Hover/focus/click the badge for provenance tooltip (role=tooltip, aria-describedby): `trained N=10 df=8 t=2.306 mse=1.84 → hw≈3.28 → ±13pts` etc + `sentiment placeholder per CAPSTONE_NEXT_STEPS:822`.
4. **Explainability** (`frontend/src/app/explainability/page.tsx:15`): same cards but with mono formula `{final_score.toFixed(1)} = ({weight_spillover}×{spillover_score})+...×100`, 3× `Contribution` (Spillover GAIL, Sentiment/Risk placeholder Temporal 0%, Creator Features), confidence line `Confidence bounds {low}–{high} (basis: {basis}, hw≈3.28→±13pts ...)`, and placeholder footer about network-graph/Granger causality (Track B weeks 11-13).
5. **Monitoring** (`frontend/src/app/monitoring/page.tsx:15`): `getAlerts()` + `getCreators()` → alerts with `SeverityBadge` (`SeverityBadge.tsx:3` low/medium/high), `propagated_from_creator_id` placeholder until sentiment propagation ships.

**Static + build verification (no browser needed):**

```powershell
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/                    # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/brand-input        # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dashboard          # 200 (static shell, data is client-side sessionStorage)
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/explainability    # 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/monitoring         # 200
# Static HTML contains <nav> + title Influencer-Brand Matching (grep the curl body)
```

---

## 6. Docker — Deployable Check (bar is deployable, not deployed `CAPSTONE_NEXT_STEPS.md:50`)

```powershell
# Backend (if Dockerfile present — Track C backend is FastAPI, not Next; frontend Dockerfile is frontend/Dockerfile:1)
# Frontend standalone (output: standalone next.config.ts:3):
docker build -f frontend/Dockerfile -t capstone-frontend:review1 frontend/
docker build -t capstone-backend:review1 backend/  # if backend Dockerfile added; else `docker run -p 8000:8000` via uvicorn in container
# Non-standard Docker path on this machine AGENTS.md:1:
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" build -f frontend/Dockerfile -t capstone-frontend:review1 frontend/
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" run -d -p 3000:3000 capstone-frontend:review1
curl http://localhost:3000/  # 200
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" ps
```

`npm run build` passing already satisfies “deployable” for Review 1; full `docker build` is the Submission bar `CAPSTONE_NEXT_STEPS.md:915`.

---

## 7. What’s Placeholder (honest, not a bug — state in thesis)

- `sentiment_risk_score` always `0.5` + `reputation_score` always `null` via `feature_store.py:115` `reputation_score=None` — Temporal branch (lag 12-24h, Granger, sentiment propagation, CLIP/BERT weekly buckets) is **0% built** `CAPSTONE_NEXT_STEPS.md:822` + `functions.md` cross-ref. `fusion.py:57` only `w1` real `w1=0.4 w2=0.3 w3=0.3` not recalibrated; `SpilloverBadge.tsx:36` tooltip documents this so UI never presents inferred as validated. `w2` stays `0.5` in `score_breakdown` everywhere — reviewer should cite as limitation, not file a bug.
- `creator_feature_score` also placeholder `0.5` (CLIP/BERT not in fusion yet).
- `confidence_low/high` already wide even for trained due small-N `N=10` + `propensity mean 0.61` (was 1.000 saturated `CAPSTONE_NEXT_STEPS.md:795` before z-score fix `ml/training.py:133`/`train_prod_model.py:133`). Isolated `0.5` clamped `[40,60]` never fabricated as inferred.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `could not translate host name "db.fhb...supabase.co"` or `WinError 10051` | Direct host is IPv6-only, no IPv6 route `AGENTS.md:1` | Use pooler `DATABASE_URL=postgresql://postgres.fhbgbtxdtfluzohxyivg:<pwd>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres` `CAPSTONE_NEXT_STEPS.md:439` (keep `postgres.<ref>` user) |
| `curl /health` 500 or `SELECT 1` fails | `DATABASE_URL` wrong or `backend/.env` not found (backend loads `env_file=".env"` `config.py:6` relative to `backend/`) | Check `backend/.env` exists, `DATABASE_URL` starts `postgresql://`, restart `uvicorn` from `backend/` |
| `/recommendations` returns `is_mock_data: true` + 3 mock creators (`FitWithPriya`) | DB has 0 `creators` or `fusionscore`/`feature_store.py` unreachable | Verify `GET /feature-store/creators` returns 259; `GET /health db_connected:true`; run migrations §1 |
| `/scores/{id}` 404 or `spillover_score` always 0.5 with `basis: placeholder` | `models/gail_checkpoint.pt` missing or `torch` not installed; `spillover.py:64` fallback is intentional | Check `backend/models/gail_checkpoint.pt` exists (3.7M) + `models/gail_checkpoint.pt`; `pip show torch` or `python -c "import torch; print(torch.__version__)"`; `python -c "from backend.app.gail.inference import get_model_info; print(get_model_info())"` — if `FileNotFoundError`, reinstall checkpoint via `git lfs`/`git checkout origin/review-1 -- backend/models/gail_checkpoint.pt models/gail_checkpoint.pt` |
| `IsolatedCreatorError` for isolated creator | Correct — degree 0 on both graphs `ml/inference.py:56` → `basis: isolated` not `inferred` `spillover.py:64` | UI shows zinc dashed `Placeholder — no graph signal` `50 [40-60]` — never present as validated |
| CORS `blocked by CORS policy` in browser but `curl` succeeds | `CORS_ALLOW_ORIGINS` missing `http://localhost:3000` or `allow_credentials` mismatch `main.py:19` | Set `CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000` in `backend/.env`, restart backend; verify `curl -H "Origin: http://localhost:3000"` returns `allow-origin` header (§3) |
| `npm run build` fails `output: standalone` | `frontend/next.config.ts:3` requires Next 16.3.0 | `cd frontend; npm ci; npm run build -- --turbo` (already verified 443ms be89dc1) |
| `docker: command not found` | Non-standard path `AGENTS.md:1` | Use `& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" ...` |
| `sentiment_risk_score` always 0.5 — “is the backend broken?” | No — Temporal/sentiment 0% built `CAPSTONE_NEXT_STEPS.md:822`; only spillover is real | Note in review as honest limitation, cite `functions.md` cross-ref; `reputation_score` 0% is expected for Review 1 |
| `final_score` always 0 or 100 with `confidence 0–100` | Honest wide CI due small-N `N=10` `hw≈3.28` → `±13pts` `margin=hw*100*w1` clamped `[0,100]` `fusion.py:57`; `spillover 21.61` outside [0,1] triggers out-of-range note | Not a bug — thesis caveat; do not narrow CI artificially |

---

## 9. One-Command Smoke Test (copy-paste after `uvicorn` + `next dev` running)

```powershell
# 0. Health
curl http://127.0.0.1:8000/health | python -m json.tool
# 1. Feature-store
curl http://127.0.0.1:8000/feature-store/creators | python -c "import sys,json; print('creators',len(json.load(sys.stdin)))"
curl http://127.0.0.1:8000/feature-store/edges/collaborations | python -c "import sys,json; print('collab',len(json.load(sys.stdin)))"
curl http://127.0.0.1:8000/feature-store/edges/co-occurrence | python -c "import sys,json; print('coocc',len(json.load(sys.stdin)))"
# 2. Pair count (needs DATABASE_URL pooler)
python scripts/ingestion/pair_count.py
# 3. Fusion archetypes
curl http://127.0.0.1:8000/scores/c4b20dc1-14f2-48e9-8bd5-7131af29049f | python -m json.tool
curl http://127.0.0.1:8000/scores/89972049-1966-4f17-9c9d-e3343c62d090 | python -m json.tool
curl http://127.0.0.1:8000/scores/78e4817c-077f-4b4c-95de-2a8c043e5cf5 | python -m json.tool
curl -X POST http://127.0.0.1:8000/recommendations -H "Content-Type: application/json" -d "{\"product_category\":\"athlete\",\"budget\":200000000,\"max_results\":3}" | python -m json.tool
# 4. Frontend
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/brand-input
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/dashboard
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/explainability
# Then open http://localhost:3000/brand-input in browser and run the §5 demo flow
```

If all above return `ok`/`200`/`54`/`259`/`trained`/`inferred`/`isolated`, Review 1 is running as frozen.

---

*End of `manual.md` — for function-level logic see `functions.md`. For live state see `CAPSTONE_NEXT_STEPS.md:1` Review 1 closed section + `602ff` pair_count derivation.*
