# Frontend Wireframes & API Field Expectations (Track D)

Status: Weeks 1-2 deliverable. Low-fidelity — the goal is a clear shape for
Weeks 3-4 implementation, not polish. See `PROJECT_PLAN.md` Section 5
(Application Layer) for the feature list this implements.

**Cross-track note:** as of 2026-08-08, none of Track A/B/C have published
`SCHEMA.md` / `GRAPH_SCHEMA.md` / `API_CONTRACTS.md` yet (checked via
`git show origin/track-{a,b,c}-*:...`, all 404). The field names below are
Track D's own best guess, derived from `PROJECT_PLAN.md` Sections 1, 4, and 5.
**Once Track C publishes `API_CONTRACTS.md`, re-check every field name in this
doc against it and flag mismatches here — do not silently rename to match
without noting the diff.**

## Tech stack decision

Next.js (App Router, v16) + TypeScript + Tailwind CSS v4, scaffolded via
`create-next-app` into `frontend/`. Rationale: matches the default suggested
for a small thesis app (fast to build, easy to deploy, no team-familiarity
data pushing elsewhere). No stack question was raised back to the user since
no strong reason to deviate came up.

Note: `create-next-app@latest` pulled Next.js 16, which has framework-level
breaking changes vs. Next 14/15 (Turbopack default, fully-async `params` /
`searchParams` / `cookies()` / `headers()`, `middleware` renamed to `proxy`,
`next lint` removed in favor of the ESLint CLI, etc. — see
`frontend/node_modules/next/dist/docs/01-app/02-guides/upgrading/version-16.md`
for the full list). None of the removed/changed APIs are in use yet at this
scaffold stage; flag this if a future session reaches for something
version-14/15-shaped (e.g. sync `params` access) when building out dynamic
routes in Weeks 3-6.

## Routes (scaffolded, empty/skeletal per Weeks 1-2 scope)

| Route | Purpose | Status |
|---|---|---|
| `/` | Landing page, CTA into the flow | Static, done |
| `/brand-input` | Brand-input flow | Skeleton form, non-functional (no state/handlers) |
| `/dashboard` | Ranked recommendation dashboard | Skeleton list, one illustrative placeholder card |
| `/monitoring` | Monitoring & alerts | Skeleton list, one illustrative placeholder alert |
| `/explainability` | Network-graph explainability | Text placeholder only — lowest priority per plan, build after recommendation engine + fusion layer are stable |

Real data wiring (mock data in Weeks 5-6, preliminary real API in Week 9-10,
full fusion-output wiring in Weeks 14-15) and the Docker deployment skeleton
(Weeks 3-4) are explicitly **not** part of this scaffold.

## 1. Brand-input flow (`/brand-input`)

Fields, per PROJECT_PLAN.md Section 1 (region/demographic are proxy signals,
since real third-party audience analytics aren't available):

- **Product / Category** — free text (e.g. "Running shoes — fitness")
- **Budget** — numeric, INR
- **Target Region (proxy)** — free text; will eventually map to bio text /
  comment language / hashtags / posting-timezone signals, not a real
  audience-geo field
- **Target Demographic (proxy)** — free text; same caveat as above

Expected request shape (`src/types/index.ts` → `BrandInputRequest`):

```ts
{
  product_category: string;
  budget_inr: number;
  region_proxy: string;
  demographic_proxy: string;
}
```

## 2. Results dashboard (`/dashboard`)

Ranked list of influencer cards. Each card shows, per PROJECT_PLAN.md
Section 4 (Fusion Layer):

- Rank + name + cross-platform handles
- **Overall score** (0-100) + **confidence bounds** (e.g. bootstrapped/ensemble
  variance range)
- **Score breakdown**, matching the fusion formula
  `final_score = w1*spillover + w2*sentiment_risk + w3*feature_score`:
  - Spillover score (GAIL branch)
  - Sentiment/risk score (Temporal branch, incl. sentiment propagation)
  - Feature score (creator metadata/content features)
- **Risk-flag badge slot** — empty for now; populated once the sentiment
  propagation branch (Weeks 14-17) produces risk flags

Expected response shape (`src/types/index.ts` → `InfluencerRecommendation`):

```ts
{
  influencer_id: string;
  name: string;
  platform_handles: { youtube?: string; instagram?: string; reddit?: string };
  overall_score: number; // 0-100
  confidence_interval: [number, number];
  score_breakdown: {
    spillover_score: number;
    sentiment_risk_score: number;
    feature_score: number;
  };
  risk_flags: { type: string; severity: "low" | "medium" | "high"; message: string }[];
}
```

## 3. Monitoring & alerts (`/monitoring`)

Per PROJECT_PLAN.md Section 5: risk flags and sentiment alerts driven by the
Temporal branch's sentiment-propagation output — a controversy detected for
one creator should surface as a risk flag for their closely-connected
collaborators too, not just for themselves. Each alert card shows severity,
influencer, description, and (if propagated) which collaborator the risk
originated from.

Expected shape (`src/types/index.ts` → `MonitoringAlert`):

```ts
{
  alert_id: string;
  influencer_id: string;
  influencer_name: string;
  alert_type: string;
  severity: "low" | "medium" | "high";
  detected_at: string; // ISO timestamp
  description: string;
  propagated_from_influencer_id?: string;
}
```

## 4. Explainability (`/explainability`)

Placeholder only for now. Eventually: network visualization of
influencer/brand connections + causal insights (e.g. posting-time/lag effects
from the Granger causality step). Per plan, this is the layer most likely to
flex if the timeline tightens — build after the recommendation engine and
fusion layer are stable (~Weeks 18-19).

## Open questions for Track C

- None yet — no `API_CONTRACTS.md` to check against. Re-visit this section
  once it's published.
