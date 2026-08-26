# Track D (Frontend+App) — Handoff

Last updated: 2026-08-26, P1.6 wired. Branch `track-d-frontend-app`, worktree `D:\Capstone-worktrees\track-d-frontend-app`, off `github.com/akshatnavlani/Capstone`. Frontend code lives in `frontend/` (not repo root). `WIREFRAMES.md` is the living wireframe/API-contract doc — read it alongside this file. `CAPSTONE_NEXT_STEPS.md:1` (restored this round via `git pull origin main`) and `API_CONTRACTS.md:1` (from `track-c-fusion-backend:65ec502`) are the cross-track sources of truth.

## Current state (one paragraph)

Next.js 16 + TypeScript + Tailwind v4 app with 5 routes (`/`, `/brand-input`, `/dashboard`, `/monitoring`, `/explainability`), wired to Track C's real backend at `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000`). **NEW this round:** `/recommendations` now serves honest `spillover_basis: "trained"|"inferred"|"placeholder"|"isolated"` + `confidence_low/high` + `score_breakdown` where `sentiment_risk_score` is still **placeholder 0.5** per `CAPSTONE_NEXT_STEPS.md:822` (Temporal branch 0% built, only `w1=0.4` real). Dashboard and explainability render a `SpilloverBadge` per creator (Trained / Inferred — wide CI / Placeholder / Isolated — no graph signal) with a custom accessible hover card explaining `N=10 df=8 t=2.306 mse1.84 → hw≈3.28 trained / 5.25 inferred` → final margin `hw·100·w1` clamped [0,100] (`±13pts` trained, `±21pts` inferred, `±10pts` placeholder/isolated) and propensity `1.000` uncertainty — never present inferred as validated. Isolated creators (degree 0) degrade gracefully to placeholder `0.5` with explicit "no graph signal" text, never inferred. `sentiment_risk_score` is labeled as placeholder in both views; we do not invent a sentiment score. `useStoredRecommendationResult` falls back `spillover_basis ?? "placeholder"` for old cached `sessionStorage`. Docker `next build` verified; `frontend/.env.local` points at live backend. Prior browser-verified flow (brand-input → dashboard → explainability → monitoring, creator-name resolution, CORS) remains intact.

## Real response shape (Track C 65ec502, API_CONTRACTS.md P1.6)

```ts
// frontend/src/types/index.ts mirrors backend/app/schemas.py exactly (65ec502)
type SpilloverBasis = "trained" | "inferred" | "placeholder" | "isolated";
interface InfluencerRecommendation {
  creator_id: string; // uuid
  name: string; category: string | null;
  youtube_handle: string | null; instagram_handle: string | null; reddit_handles: string[];
  final_score: number; // 0-100, clamped
  confidence_low: number; confidence_high: number; // honest: hw*100*w1, see fusion.py:57
  spillover_basis?: SpilloverBasis; // optional on client for stale cache, ?? "placeholder"
  estimated_reach: number | null; estimated_cost: number | null;
  score_breakdown: {
    spillover_score: number; // nominal 0-1, but live GAIL can be >>1 (Virat 21.61) — render raw
    sentiment_risk_score: number; // still 0.5 placeholder per CAPSTONE_NEXT_STEPS.md:822 — not real
    creator_feature_score: number; // still 0.5 placeholder
    weight_spillover: number; weight_sentiment_risk: number; weight_creator_feature: number;
  };
}
```

- `trained` = in GAIL N=10 labeled set (tighter but still wide `±13pts`);
- `inferred` = graph-connected unlabeled via GAT inductive (`±21pts` wide, 1.6×);
- `placeholder` = checkpoint missing/fallback `0.5 ±10pts`;
- `isolated` = degree 0 on both `collaborates_with` + `co_occurs_with` → `0.5` with `±10pts`, never `inferred`, rendered as "no graph signal".
- `sentiment_risk_score` remains `0.5` placeholder — only `w1` (spillover) real per CAPSTONE_NEXT_STEPS:822, weights stay `0.4/0.3/0.3` not recalibrated. See `frontend/src/components/SpilloverBadge.tsx` for badge colors + tooltip copy.

Verified against live `POST /recommendations` via pooler: Virat Kohli `c4b20…` trained `21.6→100`, PV Sindhu/AB `inferred` ~`8.59/1.19`, Nisha/_bungy `isolated` `0.5→50` with CI `40-60` — all with correct `spillover_basis` (see report.md from 65ec502).

## Open items

- **Explainability network-graph/causal-insights — still honest placeholder.** `co_occurs_with` is now `~1,400+` (319 posts overlap, giant component 185) per CAPSTONE_NEXT_STEPS Review 2 backlog, but no causal insights UI built yet. Keep explicit placeholder text; do not fabricate.
- **Kohli/Agilitas — closed 2026-08-14** (full text confirms `is_sponsored=false`, not blocked).
- **`product_category`/`platform_preference` filtering — fully real** per API_CONTRACTS.md (soft/hard filters, keyword-overlap). No frontend action.
- **Sentiment/risk (`sentiment_risk_score`, `reputation_score`) — still placeholder 0.5** (`CAPSTONE_NEXT_STEPS:822`, `808`). Labeled honestly in UI; Temporal branch 0% built, do not invent scores.
- **Real Fusion Layer scores — partially wired.** `spillover_score` now real via GAIL `c6488a6`; `sentiment_risk`/`creator_feature` remain `0.5`. Dashboard/explainability correctly badge each basis with wide CI; no flat `0.5` mock across all creators anymore.

## Non-obvious lessons (carry-forward)

1. "Tool X enabled" ≠ reachable — verify directly, restart if needed (Docker, browser tool).
2. `curl` does not enforce CORS — use real browser. Fixed via `CORSMiddleware` in `backend/app/main.py` (allow `localhost:3000`).
3. Track C's contract has broken same-day — always `git show origin/track-c-fusion-backend:backend/app/schemas.py` fresh.
4. Infrastructure ≠ data — re-query live DB row counts each round.
5. Clean `git status` ≠ safe — explicitly commit+push before ending round.
6. Supabase `DATABASE_URL` pooler is `aws-0-ap-south-1.pooler.supabase.com:5432`, not direct `db.*` (IPv6 fails `WinError 10051`).
7. **New:** `spillover_basis` must be honored — never collapse `inferred`/`isolated` into `trained`; `isolated` → placeholder, never inferred; `hw` margins are wide by design at N=10.

## Exact next steps

1. `npm run lint` + `npm run build` must pass before any claim deployable.
2. `npm run dev` + real-browser check against live backend (`NEXT_PUBLIC_API_BASE_URL`), confirming CORS and 3 archetypes render differently (trained / inferred / isolated).
3. Keep `WIREFRAMES.md` in sync with any future `spillover_basis` changes; commit+push both docs immediately.
4. Periodically re-check Track B temporal branch — when `sentiment_risk_score` becomes real, remove placeholder labels (per CAPSTONE_NEXT_STEPS Phase 5).
