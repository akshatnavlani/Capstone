# Frontend Wireframes & API Field Expectations (Track D)

Status: P1.6 wired (2026-08-26). See `PROJECT_PLAN.md` Section 5 (Application Layer) for feature list.

**Cross-track note (2026-08-26, re-checked):** re-verified against `origin/track-c-fusion-backend` commit `65ec502` (P1.6). Breaking change: `InfluencerRecommendation` now carries `spillover_basis: "trained"|"inferred"|"placeholder"|"isolated"` + `confidence_low/high` derived from honest small-N `hw` (trained ±13pts, inferred ±21pts, placeholder/isolated ±10pts via `margin = hw*100*w1` clamped [0,100]). `score_breakdown.sentiment_risk_score` is **still placeholder 0.5** per `CAPSTONE_NEXT_STEPS.md:822` (Temporal branch 0% built, only `w1=0.4` real). Always `git fetch origin && git show origin/track-c-fusion-backend:backend/app/schemas.py` fresh — contract has broken multiple times.

**Live data note (2026-08-26):** Track C vendored `backend/app/gail/` + `backend/models/gail_checkpoint.pt` (3.7M, `c6488a6`, effective N=10, 259 nodes). `POST /recommendations` batch-resolves via `get_spillover_batch` (single GAT forward cached), `isolated` (degree 0) → `placeholder` never `inferred`. `is_mock_data` still valid (true if creator table empty or any creator lacks stored FusionScore), now independent of `spillover_basis`.

## Tech stack decision

Next.js (App Router, v16) + TypeScript + Tailwind CSS v4, via `create-next-app` into `frontend/`. No change.

## Routes

| Route | Purpose | Status |
|---|---|---|
| `/` | Landing page, CTA into the flow | Static |
| `/brand-input` | Brand-input flow | Wired — real form, `POST /recommendations`, result via `sessionStorage` (handled stale `spillover_basis` fallback) |
| `/dashboard` | Ranked recommendation dashboard | **Wired — now with spillover_basis badge + custom hover card (Trained / Inferred — wide CI / Placeholder / Isolated — no graph signal), isolated degrade, sentiment placeholder label** |
| `/monitoring` | Monitoring & alerts | Wired — `GET /alerts`, severity/reason/source, creator-name resolve, `propagated_from_creator_id` |
| `/explainability` | Score-breakdown explainability | **Wired — shows weighted fusion formula per influencer with basis badge + wide CI note; network-graph still honest placeholder** |

Docker skeleton done (`frontend/Dockerfile`, `.dockerignore`, `next.config.ts` → `output: "standalone"`).

## 1. Brand-input flow (`/brand-input`)

Real request shape to `POST {NEXT_PUBLIC_API_BASE_URL}/recommendations` (`src/types/index.ts` → `BrandRecommendationRequest`):

```ts
{
  product_category: string;
  budget: number; // INR, >0 finite (NaN/Infinity 422)
  target_region?: string;
  target_demographic?: string;
  platform_preference?: ("youtube" | "instagram" | "reddit")[];
  max_results?: number;
}
```

On submit, stores full `BrandRecommendationResponse` (including `spillover_basis`) in `sessionStorage.recommendationResult` for dashboard/explainability. `useStoredRecommendationResult` falls back `spillover_basis ?? "placeholder"` for old cache.

## 2. Results dashboard (`/dashboard`)

Ranked list from `BrandRecommendationResponse.results`. Filtering is real: budget hard via `estimated_cost` heuristic; region/demographic/category soft (keyword-overlap); `platform_preference` hard.

Current real response shape (`src/types/index.ts`, mirrors `backend/app/schemas.py` @ 65ec502):

```ts
type SpilloverBasis = "trained" | "inferred" | "placeholder" | "isolated";
interface InfluencerRecommendation {
  creator_id: string; // uuid
  name: string;
  category: string | null;
  youtube_handle: string | null;
  instagram_handle: string | null;
  reddit_handles: string[]; // array
  final_score: number; // 0-100 clamped
  confidence_low: number;
  confidence_high: number;
  spillover_basis?: SpilloverBasis; // optional for stale cache fallback; server always sends it
  estimated_reach: number | null;
  estimated_cost: number | null;
  score_breakdown: {
    spillover_score: number; // nominal 0-1, live can be >>1 (e.g. 21.61) — render raw, note clamped
    sentiment_risk_score: number; // STILL PLACEHOLDER 0.5 per CAPSTONE_NEXT_STEPS:822 — label as such
    creator_feature_score: number; // still 0.5 placeholder
    weight_spillover: number; weight_sentiment_risk: number; weight_creator_feature: number;
  };
}
interface BrandRecommendationResponse {
  query: BrandRecommendationRequest;
  results: InfluencerRecommendation[];
  is_mock_data: boolean;
}
```

Rendering per influencer (dashboard):

- **Badge:** `SpilloverBadge` with custom hover card (hover + focus + click toggle, `aria-describedby`, `role=tooltip`):
  - `trained` — emerald “Trained • N=10 ±13” — tooltip: `hw=t·√mse·√(1+1/N)` N=10 df=8 t=2.306 mse1.84 → hw≈3.28 → ±13pts, still wide due small-N + propensity 1.000 (CAPSTONE_NEXT_STEPS:795).
  - `inferred` — violet outline “Inferred — wide CI” — tooltip: hw≈5.25 (1.6×) → ±21pts wide, GAT inductive not validated.
  - `placeholder` — zinc “Placeholder” — 0.5 ±10pts, no GAIL signal.
  - `isolated` — zinc dashed “Isolated — no signal” + subtext “no graph signal — degree 0 on collaborates_with + co_occurs_with; placeholder 0.5, never inferred.”
- **Scores:** `spillover_score.toFixed(2)` with sublabel hint (`±13/±21/±10`), `sentiment_risk_score` sublabel “placeholder 0.5 (Temporal 0%)”, `creator_feature_score` sublabel “placeholder 0.5”. Out-of-range spillover (>1) shows amber note “raw GAIL output; final_score clamped [0,100]”.
- **Confidence:** `confidence_low–high` with basis tag.
- Risk badge: cross-references `GET /alerts` grouped by `creator_id` (unchanged).

**Real-browser-tested:** diversified stubs (`estimated_cost` null guard) + now 3 basis archetypes via live backend (Virat trained, PV/AB inferred, Nisha/_bungy isolated) — see HANDOFF.md.

## 3. Monitoring (`/monitoring`)

Fetches `GET {NEXT_PUBLIC_API_BASE_URL}/alerts`. Shape:

```ts
interface AlertResponse {
  id: number;
  creator_id: string; // uuid
  severity: "low" | "medium" | "high";
  reason: string;
  source: string; // e.g. "sentiment_propagation"
  propagated_from_creator_id: string | null;
  created_at: string;
  resolved: boolean;
}
```

`resolved` is dead (no endpoint sets it true); no toggle built. `propagated_from_creator_id` wired and live-tested. Creator names resolved via `GET /feature-store/creators` with raw-id fallback.

## 4. Explainability (`/explainability`)

Uses same `sessionStorage` result via `src/lib/useStoredRecommendationResult.ts` to show per influencer: basis badge + formula `final_score = (w1×spillover + w2×sentiment_risk + w3×creator_feature)×100 [+ risk_adjustment]` with derived risk caveat (clamping). Each influencer shows:

- Badge (same as dashboard) + isolated subtext if needed
- Formula line with raw spillover; out-of-range note if spillover outside 0-1
- 3 contribution boxes with hints (`±13/±21/±10` for spillover, `placeholder 0.5` for sentiment/creator)
- Confidence line with `hw` provenance + `sentiment still placeholder per CAPSTONE_NEXT_STEPS:822`
- Per-basis explanatory paragraph (trained: still wide due N=10+propensity 1.000; inferred: not validated; etc.)

Network-graph + Granger-causality insights remain explicit placeholder (blocked on Track B temporal branch), not bare "coming soon". Co-occurrence edges are now `~1,400+` per CAPSTONE_NEXT_STEPS Review 2 backlog, but causal insights still not built.

## Docker

`frontend/Dockerfile` 3-stage (`node:20-alpine`, `output: standalone`). `.dockerignore` excludes `node_modules`, `.next`, `.git`, `.env*`. `next build` produces `.next/standalone/server.js`.

## Field-name mismatch history

### Round 1 (Weeks 1-2 → Weeks 3-4, 2026-08-09)

| # | guess | real |
|---|---|---|
| 1 | `budget_inr` | `budget` |
| 2 | `region_proxy` | `target_region` |
| 3 | `demographic_proxy` | `target_demographic` |
| 4 | `platform_handles: {...}` | flat `youtube_handle`/`instagram_handle`/`reddit_handle` |
| 5 | `risk_flags: RiskFlag[]` | separate `/alerts` |
| 6 | `overall_score`/`confidence_interval` | `final_score`/`confidence_low`+`confidence_high` |
| 7 | `MonitoringAlert.influencer_name` | only `creator_unique_id` |
| 8 | `MonitoringAlert.propagated_from_influencer_id` | `source` |
| 9 | `alert_type` | `reason`+`source` |
| 10 | `feature_score` | `creator_feature_score`+3 weights |

### Round 2 (Weeks 3-4 → Weeks 5-6, same-day)

| # | before | after |
|---|---|---|
| 11 | `creator_unique_id: string` | `creator_id: string` (uuid) |
| 12 | `reddit_handle: string\|null` | `reddit_handles: string[]` |
| 13 | — | `estimated_cost: number\|null` |
| 14 | `propagated_from_influencer_id` flagged open | uncommitted `propagated_from_creator_id` causing live 500 |

### Round 3 (Weeks 5-6 → Weeks 7-8, 2026-08-09/10)

| # | before | after |
|---|---|---|
| 15 | no propagation field | `AlertResponse.propagated_from_creator_id: uuid\|null` — committed, live-tested |

### Round 4 (Weeks 7-8 → P1.6, 2026-08-26)

| # | before | after |
|---|---|---|
| 16 | `InfluencerRecommendation` had no `spillover_basis` | `spillover_basis: "trained"\|"inferred"\|"placeholder"\|"isolated"` — honest provenance, wide CI documented in `fusion.py:57` + `API_CONTRACTS.md` P1.6 |
| 17 | `ScoreBreakdown.sentiment_risk_score` assumed real at some point | still placeholder `0.5` per `CAPSTONE_NEXT_STEPS.md:822` (Temporal 0%) — only `w1` real |
| 18 | `confidence_low/high` fixed `±8` fallback | honest `hw*100*w1` when GAIL available (`trained ±13`, `inferred ±21`, else `±10`/`±8`) |

### CORS blocker (2026-08-09 — RESOLVED)

Track C had no `CORSMiddleware` — browser preflight `405` with no `Access-Control-Allow-Origin`. Fixed via `app.add_middleware(CORSMiddleware, allow_origins=settings.cors_allow_origins_list, allow_methods=["*"], allow_headers=["*"])` (commit `71e7d85`). Re-verified via real browser + preflight headers (`access-control-allow-origin: http://localhost:3000`). Still enforced (disallowed origin gets no header).
