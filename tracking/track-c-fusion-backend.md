# Track C — Fusion + Backend — Change Log (review-1 branch)

Owner: Track C (Edge resolution, disclosure labeling, feature store, fusion, API)
Branch: `review-1`
Standing rule: Work is in `D:\Capstone\backend\`. No commits until user says so; tell when commit warranted. Restart backend via subagent when needed.

## Change Log

### 2026-08-27 — Initial tracking files created
- Created `tracking/` with per-track files.

### 2026-08-27 — Hosting confirmed
- Env: `backend\.env` pooler DB `aws-0-ap-south-1.pooler.supabase.com:5432`, `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` on frontend.
- Health: `GET /health` ok, `GET /scores/c4b20…` (Virat trained 21.61→100), `POST /recommendations` live.

### 2026-08-27 — Fix: explain empty creators (user report: "Athletic water bottle, 5000000, India" → 0 results, no explanation)
- **Motivation:** Budget/keyword soft filters were honestly dropping creators but Dashboard showed empty list with no guidance.
- **Files:**
  - `backend/app/schemas.py:60` — `BrandRecommendationResponse` added `explanation: Optional[str]=None` and `counts: Optional[dict]=None` (backwards-compatible).
  - `backend/app/routers/influencers.py:194` — added counters `considered`, `dropped_by_budget/platform/region/demographic/product`, set `explanation` when `results==[]` (e.g. `"No creators matched your query. 259 creators considered. 15 dropped by budget. 116 dropped by region. 128 dropped by product category."`), and always return `counts` dict. No filter semantics changed — filters remain honest (budget hard, region/demographic/product soft).
  - `frontend/src/types/index.ts:43` — mirrored `explanation?`/`counts?` in `BrandRecommendationResponse`.
  - `frontend/src/app/dashboard/page.tsx:35` — added empty-results branch that renders `explanation` + `counts` when `result.results.length===0`.
- **Verify:** `curl -X POST http://127.0.0.1:8000/recommendations -d '{"product_category":"Athletic water bottle","budget":5000000,"target_region":"India","max_results":10}'` now returns `explanation`+`counts`; `{"product_category":"athlete","budget":5000000,"target_region":"India"}` still returns real ranked results.

### 2026-08-27 — Fix: placeholder rate consistency + LeBron smoke-test rectified (Task 2-3)
- **Motivation:** `COST_PER_FOLLOWER_INR=0.5` flat made athlete vs fitness_influencer costs arbitrary (5k reach → ₹2.5k vs 272M → ₹136M but same 0.5 scalar); LeBron James showed `high` risk due to a single `riskalert` id 2 `"Weeks 7-8 propagation-field smoke test"` seeded 2026-08-09.
- **Files:**
  - `backend/app/routers/influencers.py:54` — Replaced single `COST_PER_FOLLOWER_INR` with tiered `CATEGORY_RATE` (`athlete:0.60, team/league:0.45, fitness_influencer:0.35, lifestyle_influencer:0.40, other:0.50`) + helper `_rate_for(category)`; both ` _to_recommendation:168` (`estimated_cost`) and budget filter `get_recommendations:222` now use `_rate_for(creator.category)` so same budget ranks consistently across categories. Flat `0.5` kept as fallback for unknown category. See `tracking/TASK2_ANALYSIS.md` for full migration path to `brand_rate_cards` table.
  - **DB fix (no file):** `riskalert` id 2 (`LeBron James`, `150e2138-…`) set `resolved=true` via pooler psycopg2 (`UPDATE riskalert SET resolved=true WHERE id=2`). Default `GET /alerts` filters `resolved=false`, so Monitoring now shows `No alerts yet` (expected until Temporal branch ships). Verified via `curl http://127.0.0.1:8000/alerts` → `[]`. Undo: `UPDATE riskalert SET resolved=false WHERE id=2`.
- **Verify:** `curl -X POST /recommendations -d '{"product_category":"athlete","budget":5000000}'` now uses tiered rate (athlete cost ~20% higher than fitness); `curl http://127.0.0.1:8000/alerts` shows no LeBron risk.

---

## Master Prompt — Track C (update after each change)

> You are Track C (Fusion+Backend) on branch `review-1`. Your ownership is `backend/app/feature_store.py:1`, `backend/app/fusion.py:57`, `backend/app/routers/scores.py:1`, `backend/app/routers/influencers.py:1`, `backend/app/spillover.py`, `API_CONTRACTS.md:1`, `backend/migrations/`.
>
> **Current state (2026-08-27, after demo polish batch):**
> - Fusion: `fusion.py:57` = `final_score = w1*spillover + w2*sentiment + w3*feature` with `w1=0.4,w2=0.3,w3=0.3` (only `w1` real via GAIL checkpoint `c6488a6`; `w2`/`w3` placeholder 0.5 per `CAPSTONE_NEXT_STEPS:822`). CI = `hw*100*w1` clamped [0,100] (trained ±13, inferred ±21, isolated/placeholder ±10, `PLACEHOLDER_CONFIDENCE_MARGIN=8` fallback).
> - Cost placeholder: `routers/influencers.py:54` now tiered `CATEGORY_RATE` (athlete 0.60, fitness 0.35, lifestyle 0.40, team/league 0.45, other 0.50) via `_rate_for(category)`; `estimated_cost = reach * _rate_for(category)` (was flat 0.5). Full DB table migration path in `tracking/TASK2_ANALYSIS.md` option 2 (brand_rate_cards). DB pooler stays `aws-0-ap-south-1.pooler.supabase.com:5432`.
> - Recommendations: `POST /recommendations` now returns `{query,results,is_mock_data,explanation?,counts?}` where `counts` tracks per-filter drops and `explanation` is set when `results==[]`. Filters unchanged: budget hard (`estimated_cost` only when computable), `target_region`/`target_demographic`/`product_category` soft via `_keyword_overlap` (>=3 char words), `platform_preference` hard.
> - Scores: `GET /scores/{creator_id}`, `POST /scores/compute` wired via `spillover.get_spillover_batch`; `spillover_basis` ∈ trained/inferred/isolated/placeholder.
> - Monitoring: `riskalert` smoke-test id 2 (LeBron James "Weeks 7-8 propagation-field smoke test") has been resolved (`resolved=true`); `GET /alerts` now returns `[]` until Temporal branch ships. Undo via `UPDATE riskalert SET resolved=false WHERE id=2`.
>
> **Replay instructions (exact diffs to re-apply in order):**
> 1. `backend/app/schemas.py:60` — Add to `BrandRecommendationResponse`: `explanation: Optional[str]=Field(default=None,...)` and `counts: Optional[dict]=Field(default=None,...)`.
> 2. `backend/app/routers/influencers.py:50` — Replace flat `COST_PER_FOLLOWER_INR` with `CATEGORY_RATE` dict + `_rate_for(category)` helper (see diff in Change Log 2026-08-27 entry 2); then `routers/influencers.py:168` (`_to_recommendation` return) and `routers/influencers.py:222` (budget filter) each change `COST_PER_FOLLOWER_INR` → `_rate_for(creator.category)`.
> 3. `backend/app/routers/influencers.py:194` — After `eligible=[]`, init `considered`, `dropped_by_*`; in loop `considered+=1` and increment the appropriate `dropped_by_*` before each `continue`; after sorting compute `is_mock_data`, then if `not results` build `explanation` by joining non-zero drop parts, build `counts` dict, and return `BrandRecommendationResponse(query=request,results=results,is_mock_data=is_mock_data,explanation=explanation,counts=counts)`.
> 4. DB: `UPDATE riskalert SET resolved=true WHERE id=2` (LeBron smoke-test); verify `GET /alerts` → `[]`.
> 5. `frontend/src/types/index.ts:43` — Mirror `explanation?`/`counts?` in `BrandRecommendationResponse` (this file lives in Track D but Track C's API change requires the type update; if replaying strictly by track boundary, tell Track D to apply it).
> 6. `frontend/src/app/dashboard/page.tsx:35` — Add the `if (result.results.length===0) return (<empty-state with explanation+counts>)` branch described in Change Log (again a Track D file; coordinate).
> 7. Restart backend via subagent (`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend/`) and re-verify both payloads plus `GET /alerts`.
