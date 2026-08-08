# Frontend Wireframes & API Field Expectations (Track D)

Status: Weeks 3-4 deliverable (Weeks 1-2 wireframes below, now wired to
Track C's real API). See `PROJECT_PLAN.md` Section 5 (Application Layer) for
the feature list this implements.

**Cross-track note (2026-08-09):** Track C's `API_CONTRACTS.md` is now
published on `origin/track-c-fusion-backend` (checked fresh via
`git fetch origin && git show origin/track-c-fusion-backend:API_CONTRACTS.md`,
plus the exact Pydantic schemas in `backend/app/schemas.py`). Field names
below have been **reconciled to match it exactly** — see the mismatch table
at the bottom for what Track D's Weeks 1-2 guesses got wrong, since those
were never checked against a real contract at the time.

Track A's `SCHEMA.md` and Track B's `GRAPH_SCHEMA.md` are also now published
(cross-checked via other tracks' shared memory — see `cross_track_memory_leak`
memory entry — plus `git show` against their branches). Nothing in those two
affects the frontend directly; Track D only consumes Track C's API.

## Tech stack decision

Next.js (App Router, v16) + TypeScript + Tailwind CSS v4, scaffolded via
`create-next-app` into `frontend/`. No change since Weeks 1-2.

## Routes

| Route | Purpose | Status |
|---|---|---|
| `/` | Landing page, CTA into the flow | Static |
| `/brand-input` | Brand-input flow | **Wired** — real form (client component), `POST /recommendations` on submit, result handed to `/dashboard` via `sessionStorage` |
| `/dashboard` | Ranked recommendation dashboard | **Wired** — reads the stored `/recommendations` response, shows `is_mock_data` banner, cross-references `GET /alerts` for per-creator risk badges |
| `/monitoring` | Monitoring & alerts | **Wired** — `GET /alerts` on mount, renders severity/reason/source/creator |
| `/explainability` | Network-graph explainability | Text placeholder only — lowest priority per plan, build after recommendation engine + fusion layer are stable |

Docker deployment skeleton (`frontend/Dockerfile`, `.dockerignore`,
`next.config.ts` → `output: "standalone"`) is done — see "Docker" section
below.

## 1. Brand-input flow (`/brand-input`)

Fields, per PROJECT_PLAN.md Section 1 (region/demographic are proxy signals,
since real third-party audience analytics aren't available):

- **Product / Category** — free text (e.g. "Running shoes — fitness")
- **Budget** — numeric, INR
- **Target Region (proxy)** — free text
- **Target Demographic (proxy)** — free text

Real request shape sent to `POST {NEXT_PUBLIC_API_BASE_URL}/recommendations`
(`src/types/index.ts` → `BrandRecommendationRequest`, matches Track C's
`BrandRecommendationRequest` in `backend/app/schemas.py` exactly):

```ts
{
  product_category: string;
  budget: number; // INR
  target_region?: string;
  target_demographic?: string;
  platform_preference?: ("youtube" | "instagram" | "reddit")[]; // not exposed in the UI yet — optional, server defaults apply
  max_results?: number; // not exposed in the UI yet — server defaults to 10
}
```

## 2. Results dashboard (`/dashboard`)

Ranked list of influencer cards, populated from `BrandRecommendationResponse.results`:

- Rank + name + cross-platform handles (flat `youtube_handle` / `instagram_handle` / `reddit_handle`, each nullable)
- `final_score` (0-100) + `confidence_low`/`confidence_high`
- `score_breakdown`: `spillover_score`, `sentiment_risk_score`, `creator_feature_score` (each 0-1, per-branch weights also included but not surfaced in the UI yet)
- Risk badge: **not** part of the recommendation object (see mismatch #5 below) — computed client-side by cross-referencing `GET /alerts`, grouped by `creator_unique_id`
- `is_mock_data` banner shown when true (currently always true — no real `Creator`/`FusionScore` rows in Track C's DB yet)

Real response shape (`src/types/index.ts` → `BrandRecommendationResponse` /
`InfluencerRecommendation`, matches `backend/app/schemas.py` exactly):

```ts
interface InfluencerRecommendation {
  creator_unique_id: string;
  name: string;
  category: string | null;
  youtube_handle: string | null;
  instagram_handle: string | null;
  reddit_handle: string | null;
  final_score: number; // 0-100
  confidence_low: number;
  confidence_high: number;
  estimated_reach: number | null;
  score_breakdown: {
    spillover_score: number; sentiment_risk_score: number; creator_feature_score: number;
    weight_spillover: number; weight_sentiment_risk: number; weight_creator_feature: number;
  };
}
interface BrandRecommendationResponse {
  query: BrandRecommendationRequest;
  results: InfluencerRecommendation[];
  is_mock_data: boolean;
}
```

## 3. Monitoring & alerts (`/monitoring`)

Fetches `GET {NEXT_PUBLIC_API_BASE_URL}/alerts` on mount. Real response shape
(`src/types/index.ts` → `AlertResponse`, matches `backend/app/schemas.py`
`AlertResponse` exactly):

```ts
interface AlertResponse {
  id: number;
  creator_unique_id: string;
  severity: "low" | "medium" | "high"; // server types this as `str`, not an enum — client assumes these 3 values per the docs, not contractually guaranteed
  reason: string;
  source: string; // e.g. "sentiment_propagation"
  created_at: string;
  resolved: boolean;
}
```

Note: there is **no `influencer_name` or `propagated_from` field** on this
endpoint (see mismatch #6/#7 below) — the UI currently just shows the raw
`creator_unique_id`. If Track C's `/alerts` response ever grows a joined
creator name or a propagation-source field, update `MonitoringPage` to use
it instead of the raw ID.

## 4. Explainability (`/explainability`)

Unchanged from Weeks 1-2 — placeholder text only, per plan (Weeks 18-19).

## Docker

`frontend/Dockerfile` — 3-stage build (`deps` → `builder` → `runner`) on
`node:20-alpine`, using `next.config.ts`'s `output: "standalone"` so the
final image only needs `.next/standalone` + `.next/static` + `public`, not
the full `node_modules`. `.dockerignore` excludes `node_modules`, `.next`,
`.git`, `.env*`.

**Verified:** `next build` with `output: "standalone"` produces
`.next/standalone/server.js` correctly (checked locally). **Not verified:**
the actual `docker build`/`docker run` — the Docker CLI isn't installed in
this environment, so the image itself has never been built or run. Flag this
if Weeks 3-4 sign-off requires an actually-built image, not just a
Dockerfile that should work per the documented `output: standalone` contract.

## Field-name mismatches found when reconciling against Track C's real contract (2026-08-09)

Weeks 1-2 field names were Track D's own guess (no contract existed yet).
Now reconciled — this table exists so nobody assumes the Weeks 1-2 doc
above was ever accurate:

| # | Weeks 1-2 guess | Real contract | Notes |
|---|---|---|---|
| 1 | `BrandInputRequest.budget_inr` | `BrandRecommendationRequest.budget` | Still INR (per field description), just not in the name |
| 2 | `region_proxy` | `target_region` (optional) | |
| 3 | `demographic_proxy` | `target_demographic` (optional) | |
| 4 | `platform_handles: { youtube?, instagram?, reddit? }` (nested object) | `youtube_handle` / `instagram_handle` / `reddit_handle` (flat, nullable) | Structural, not just naming |
| 5 | `risk_flags: RiskFlag[]` embedded on each `InfluencerRecommendation` | **No such field exists.** Risk data lives entirely in the separate `/alerts` resource, joined client-side by `creator_unique_id` | This was a design assumption, not just a name guess — the Weeks 1-2 wireframe assumed risk flags would ride along with the recommendation payload; they don't |
| 6 | `overall_score` / `confidence_interval: [number, number]` | `final_score` / `confidence_low` + `confidence_high` (two separate fields, not a tuple) | |
| 7 | `MonitoringAlert.influencer_name` | **Does not exist.** Only `creator_unique_id` is returned | UI currently shows the raw ID |
| 8 | `MonitoringAlert.propagated_from_influencer_id` | **Does not exist.** Closest is `source` (freeform string, e.g. `"sentiment_propagation"`), which names the *mechanism*, not the source creator | If Track B/C want to expose "propagated from creator X," that needs a new field — flagging for Track C, not adding it unilaterally |
| 9 | `alert_type` | `reason` (freeform string) + `source` | |
| 10 | `feature_score` (in score breakdown) | `creator_feature_score`, plus 3 weight fields (`weight_spillover` etc.) not previously modeled at all | |

No open questions requiring Track C action right now beyond #8 (propagation
source on alerts) — flagged above, not blocking.
