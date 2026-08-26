# Track D — Review 1 Close: Real Shape Wired (be89dc1)

**Commit:** `be89dc1` (Wire real /recommendations spillover_basis with honest N=10 CI) on `track-d-frontend-app`, building on `track-c-fusion-backend:65ec502` + `origin/main:a4b3bed`.

**What wired:** `frontend/src/types/index.ts` (SpilloverBasis `trained|inferred|placeholder|isolated`, optional fallback `?? "placeholder"` for stale sessionStorage, `sentiment_risk_score` annotated placeholder per CAPSTONE_NEXT_STEPS:822) → `frontend/src/lib/api.ts` (documents `hw*100*w1` CI) → `frontend/src/components/SpilloverBadge.tsx` (custom hover card: Trained N=10 ±13, Inferred wide ±21, Placeholder ±10, Isolated no graph signal, never inferred, explains `N=10 df=8 t=2.306 mse1.84 → hw≈3.28/5.25` + propensity 1.000) → `frontend/src/app/dashboard/page.tsx` + `frontend/src/app/explainability/page.tsx` (badge per creator, isolated degrade, out-of-range spillover note, confidence via `backend/app/fusion.py:57`).

---

## Verify — lint + build (must pass, not claimed)

**`npm run lint` @ `frontend`**
```
> frontend@0.1.0 lint
> eslint

LINT_PASS
```

**`npm run build` @ `frontend`**
```
> frontend@0.1.0 build
> next build

▲ Next.js 16.3.0 (Turbopack)
- Environments: .env.local
✓ Running next.config.ts took 20ms
  Creating an optimized production build ...
✓ Compiled successfully in 443ms
  Running TypeScript ...
  Finished TypeScript in 1092ms ...
  Collecting page data using 9 workers ...
  Generating static pages using 9 workers (0/8) ... (8/8) in 489ms
  Finalizing page optimization ...

Route (app)
┌ ○ /  ├ ○ /brand-input  ├ ○ /dashboard  ├ ○ /explainability  └ ○ /monitoring
○  (Static)  prerendered as static content

BUILD_PASS
```

Keep 5 routes; sentiment not invented.

---

## Verify — CORS + live backend

**Backend** `http://127.0.0.1:8000` (pooler DSN from `track-c-fusion-backend/backend/.env`, via `CAPSTONE_NEXT_STEPS:440`):
```
GET /health → {"status":"ok","db_connected":true,"version":"0.1.0"}
```

**CORS** (real browser, not just curl):
- `GET /health` with `Origin: http://localhost:3000` → `access-control-allow-origin: http://localhost:3000` ✅
- `OPTIONS /recommendations` preflight → `200` + `access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT` + `allow-origin: http://localhost:3000` ✅ (verified `frontend/.env.local` = `http://127.0.0.1:8000`, `backend/app/main.py:CORSMiddleware` allowlist `localhost:3000,127.0.0.1:3000`)

**Frontend dev** `http://127.0.0.1:3000` — `next dev --port 3000` (Turbopack) → all 5 routes `200`: `/`, `/brand-input`, `/dashboard`, `/explainability`, `/monitoring` (verified via `curl -s -o /dev/null -w %{http_code}`).

---

## 3 Archetypes — trained / inferred / isolated (via live `POST /recommendations`, pooler)

All carry `spillover_basis` + `confidence_low/high` + `score_breakdown.sentiment_risk_score:0.5` placeholder (CAPSTONE_NEXT_STEPS:822, only w1 real).

**Trained — Virat Kohli `c4b20dc1-14f2-48e9-8bd5-7131af29049f`**
```json
// POST /recommendations {"product_category":"athlete","budget":200000000,"max_results":5} → top
{
  "creator_id": "c4b20dc1-14f2-48e9-8bd5-7131af29049f",
  "name": "Virat Kohli",
  "category": "athlete",
  "instagram_handle": "virat.kohli",
  "reddit_handles": ["KingKohli","ViratKohli"],
  "final_score": 100.0,
  "confidence_low": 0.0,
  "confidence_high": 100.0,
  "spillover_basis": "trained",
  "estimated_reach": 272234883,
  "estimated_cost": 136117441.5,
  "score_breakdown": {
    "spillover_score": 21.615880966186523,
    "sentiment_risk_score": 0.5,
    "creator_feature_score": 0.5,
    "weight_spillover": 0.4,
    "weight_sentiment_risk": 0.3,
    "weight_creator_feature": 0.3
  }
}
```
UI: emerald badge `Trained — N=10` + custom hover (`hw≈3.28 → ±13pts`, propensity 1.000, still wide), spillover raw `21.61` + amber note `raw GAIL outside 0-1; final clamped [0,100]`.

**Inferred — PV Sindhu (via POST) + AB de Villiers `89972…` (via GET /scores)**
```json
// POST /recommendations {"product_category":"athlete","budget":5000000} → PV Sindhu
{
  "name": "PV Sindhu",
  "spillover_basis": "inferred",
  "score_breakdown": {"spillover_score": 8.592735290527344, "sentiment_risk_score": 0.5, "creator_feature_score": 0.5, "weight_spillover": 0.4, "weight_sentiment_risk": 0.3, "weight_creator_feature": 0.3},
  "confidence_low": 0.0,
  "confidence_high": 100.0,
  "final_score": 100.0
}
// GET /scores/89972049-1966-4f17-9c9d-e3343c62d090 → AB de Villiers
{
  "creator_id": "89972049-1966-4f17-9c9d-e3343c62d090",
  "final_score": 77.6240062713623,
  "confidence_low": 0.0,
  "confidence_high": 100.0,
  "spillover_basis": "inferred",
  "breakdown": {"spillover_score": 1.1906001567840576, "sentiment_risk_score": 0.5, "creator_feature_score": 0.5, "weight_spillover": 0.4, "weight_sentiment_risk": 0.3, "weight_creator_feature": 0.3}
}
```
UI: violet outline badge `Inferred — wide CI` + hover (`hw≈5.25 1.6× → ±21pts wide, GAT inductive, not validated`).

**Isolated — _bungy `78e48…` + Athletics (via POST)**
```json
// GET /scores/78e4817c-077f-4b4c-95de-2a8c043e5cf5 → _bungy_lover_.01
{
  "creator_id": "78e4817c-077f-4b4c-95de-2a8c043e5cf5",
  "final_score": 50.0,
  "confidence_low": 40.0,
  "confidence_high": 60.0,
  "spillover_basis": "isolated",
  "breakdown": {"spillover_score": 0.5, "sentiment_risk_score": 0.5, "creator_feature_score": 0.5, "weight_spillover": 0.4, "weight_sentiment_risk": 0.3, "weight_creator_feature": 0.3}
}
// POST /recommendations {"product_category":"other","budget":10000000} → Athletics
{
  "name": "Athletics",
  "spillover_basis": "isolated",
  "score_breakdown": {"spillover_score": 0.5, "sentiment_risk_score": 0.5, "creator_feature_score": 0.5, ...},
  "confidence_low": 40.0,
  "confidence_high": 60.0,
  "final_score": 50.0
}
// also Nisha Kumari fab5e… isolated 0.5 40-60 via fitness apparel 5M
```
UI: zinc dashed badge `Isolated — no signal` + subtext `no graph signal — degree 0 on collaborates_with + co_occurs_with; placeholder 0.5, never inferred`, confidence `40–60 ±10pts (hw 0.25)`.

All three archetypes render differently (badge color + CI width + isolated degrade) per `frontend/src/components/SpilloverBadge.tsx:1` and `frontend/src/app/dashboard/page.tsx` / `explainability/page.tsx`.

---

## What's real vs placeholder

- `spillover_score` real via GAIL `c6488a6` (effective N=10, `fusion.py:57` honest CI), `confidence` via `hw*100*w1` (trained ±13, inferred ±21, isolated/placeholder ±10).
- `sentiment_risk_score` still `0.5` placeholder — Temporal 0% built per CAPSTONE_NEXT_STEPS:822, only w1 real, weights `0.4/0.3/0.3` not recalibrated. See `frontend/src/types/index.ts:9` + `frontend/src/components/SpilloverBadge.tsx:36` tooltip.

---

## Track C source (preserved from merge, for reference)

Commit `65ec502` (P1.6 wired) on `track-c-fusion-backend`, vendoring `origin/track-b-ml-core:c6488a6` (`ml/inference.py` + `models/gail_checkpoint.pt`, 3.7M, `effective N=10`, 259 nodes, `mse 1.84`). See `backend/app/fusion.py:57` (`margin = hw*100*w1` clamped [0,100]) + `backend/app/spillover.py` (never crash: `IsolatedCreatorError` → `isolated`).

```json
// InfluencerRecommendation & FusionScoreResponse now include:
{
  "spillover_basis": "trained" | "inferred" | "placeholder" | "isolated",
  "confidence_low": 0.0,
  "confidence_high": 100.0,
  "score_breakdown": {
    "spillover_score": 1.19,
    "sentiment_risk_score": 0.5,
    "creator_feature_score": 0.5,
    "weight_spillover": 0.4,
    "weight_sentiment_risk": 0.3,
    "weight_creator_feature": 0.3
  }
}
```
