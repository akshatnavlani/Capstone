# Track D (Frontend+App) — Handoff

Last updated: 2026-08-26, P1.6 wired. Branch `track-d-frontend-app`, worktree `D:\Capstone-worktrees\track-d-frontend-app`, off `github.com/akshatnavlani/Capstone`. Frontend code lives in `frontend/` (not repo root). `WIREFRAMES.md` is the living wireframe/API-contract doc — read it alongside this file. `CAPSTONE_NEXT_STEPS.md:1` (restored this round via `git pull origin main`) and `API_CONTRACTS.md:1` (from `track-c-fusion-backend:65ec502`) are the cross-track sources of truth.

**✅ 2026-08-26 — Review 1 close: P1.6 WIRED, contracts finalized (`65ec502`).** Real `spillover_score` live via GAIL checkpoint `c6488a6` (`ml/inference.py` + `models/gail_checkpoint.pt`, 54 pairs, `effective N=10`, `mse 1.84`). Vendored `backend/app/gail/` + `backend/models/gail_checkpoint.pt` (3.7M) + `backend/app/spillover.py` wrapper never-crash: `FileNotFoundError`/`IsolatedCreatorError`/`KeyError`/no `torch` → `basis="placeholder"`/`"isolated"` `0.5` `±10pts`. **API shape finalized for Track D:** `SpilloverBasis = Literal["trained","inferred","placeholder","isolated"]` on `FusionScoreResponse` + `InfluencerRecommendation` (`backend/app/schemas.py:41,184`), `POST /scores/compute` `spillover_score` optional (auto `get_spillover`), `GET /scores/{id}` live recompute, `POST /recommendations` batch `get_spillover_batch` (`isolated→placeholder` never `inferred`). `backend/app/fusion.py:57` honest: `hw = t*sqrt(mse)*sqrt(1+1/N)` `N=10 t=2.306 mse1.84` → `trained hw≈3.28 → ±13pts` `inferred hw≈5.25 → ±21pts` `isolated/placeholder 0.25→±10pts` via `hw*100*w1` (`w1=0.4` only, `CAPSTONE_NEXT_STEPS.md:795` propensity 1.000), clamped `[0,100]` — `w2` (`sentiment_risk`) stays `0.5` placeholder `CAPSTONE_NEXT_STEPS.md:822` not recalibrated. `0003` migration live. Verified `pytest backend/tests -q` **49 pass** + `/health` + `/feature-store/edges/sponsorships` 16 + 3 JSONs (`c4b20 Virat 21.61→100 [0-100] trained`, `89972 AB 1.19→77 [0-100] inferred wide`, `78e48 _bungy 0.5→50 [40-60] isolated`) — `report.md`.

## 2026-09-24 Re-scope — Review 2 = pipeline-complete, Review 3 = improve

Team decision 2026-09-24 (`origin/main c795138`, `CAPSTONE_NEXT_STEPS.md` 2026-09-24 re-scope section): all 21 PendingWork items are the Review 2 exit gate. This track covers the A2 build gate (`pytest` both suites + `npm run lint` + `npm run build` green, Docker smoke) and the S6 explainability graph surface (PendingWork assigns S6 to Shimona — D provides the UI surface/support against live `GET /feature-store/edges/`; coordinate, don't duplicate). Keep `sentiment_risk_score`/`creator_feature_score` placeholder labels until S1/S2 land; remove them only when the scores go real. Fresh sessions: `git pull origin main` first.

Last updated: 2026-08-26 — Review 1 close, contracts finalized (`65ec502` wiring, `c6488a6` artifact) — `CAPSTONE_NEXT_STEPS.md` (`778-795` N=10 `795` propensity 1.000, `822` w2 placeholder, `808` reputation_score null, `484` ownership), `API_CONTRACTS.md:1` SpilloverBasis Literal finalized, `report.md` 3 JSONs verified.

## 2026-09-24 Re-scope — Review 2 = pipeline-complete, Review 3 = improve

Team decision 2026-09-24 (`origin/main c795138`, `CAPSTONE_NEXT_STEPS.md` 2026-09-24 re-scope section): all 21 PendingWork items are the Review 2 exit gate. This track owns S3 fusion calibration (recalibrate `w1/w2/w3`, backfill fusionscore, remove `is_mock_data:true`, CI over all 3 branches — only after S1+S2 go real), `risk_alerts.propagated_from_creator_id` + alerts-router wiring with Shimona, S8 cross-platform support, and A1 `ml/` vs `backend/app/gail/` dedup (active hazard once Eesha edits `exposure.py`/`gail_loss.py` — land it first). Precision-first labeling discipline unchanged. Fresh sessions: `git pull origin main` first.

✅ **A1 LANDED 2026-09-24 (Option A):** `backend/app/gail/` deleted (9 vendored files), `spillover.py` imports `ml.inference`, repo-root `sys.path` shim in `backend/app/__init__.py`, orphaned `backend/models/gail_checkpoint.pt` removed (canonical artifact stays track-b `models/`). Verified: 49 backend tests pass; live wiring via a temporary canonical copy returned trained 0.339 / inferred 1.191 / isolated 0.5 — exact match to `c6488a6` artifact values (temp copy removed afterwards). Standalone track-c runs without root `ml/`+`models/` fall back to placeholder by design; deploy/build context must include both.

✅ **A2 (this round):** new `backend/tests/test_spillover.py` — served loader must resolve to `ml.inference` (fails if model code is ever re-vendored) + placeholder/isolated fallback when `ml` is missing (locks the never-crash contract for backend-only deploys). Suite now 50 passed + 1 env-skip (skip = backend-only checkout without `ml/`; both new tests pass where `ml/` is present). The cross-track runner `gate.ps1` lives on track-d (Docker owner).

✅ **A3 (this round):** new `backend/tests/test_influencers.py` red-team canary — empty/1-char `product_category` must pass through (2026-08-09 wipeout guards hold; tests lock them), genuine mismatch (`zxywq`) must still filter to empty. Suite now 53 passed + 1 env-skip. No source change needed.

✅ **A2 LANDED 2026-09-24:** `backend/` synced to track-c A1 (vendored `app/gail/` + checkpoint copy deleted — byte-identical to track-c). New `backend/Dockerfile` (python:3.11-slim, placeholder-mode smoke: `ml/` not baked in by design) + `.dockerignore` (excludes `.venv`/`.env`/`node_modules`) + `gate.ps1` (5 steps: pytest B, pytest C, lint, build, docker smoke with `/health` + `/recommendations` 200). Verified `GATE GREEN` this round: 69 + 50(+1 skip) + lint + build + smoke. Gate probes use `curl.exe`, not `Invoke-WebRequest` (PS 5.1 throws a host prompt in non-interactive shells).

✅ **A3 (this round):** `gate.ps1` grew a sixth step — pair-count canary (new `$ARoot` param; exit 2 from the canary = loud SKIP without DATABASE_URL, not failure). Full gate re-verified GREEN including the canary running live.

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
