# Frontend Wireframes & API Field Expectations (Track D)

Status: Weeks 7-8 deliverable. See `PROJECT_PLAN.md` Section 5 (Application
Layer) for the feature list this implements.

**Cross-track note (2026-08-09/10, re-checked a third time):** re-verified
against `origin/track-c-fusion-backend` commit `ec9833d` (Weeks 5-6).
`BrandRecommendationRequest`/`InfluencerRecommendation` are **unchanged**
since the Round 2 break below. `AlertResponse`/`AlertCreate` gained
`propagated_from_creator_id` (nullable uuid) — this is now **committed**,
not the uncommitted WIP flagged last round — reconciled below (Round 3).
Track C's actual disclosure-tag (`is_sponsored`) labeling pipeline has
**not shipped yet** as of this check (still flagged "still open" in their
own Weeks 5-6 notes) — nothing to reconcile there yet, and it likely won't
change `/recommendations`' response shape even once it ships, since
`is_sponsored` is an ingestion-side field, not part of
`InfluencerRecommendation`. Always
`git fetch origin && git show origin/track-c-fusion-backend:backend/app/schemas.py`
fresh before trusting any field name here — this is the third time in three
sessions the contract has moved.

**Live data note:** as of this session, Track A's real scraped data has
started landing in the shared Supabase DB (confirmed via
`GET /feature-store/creators` and a real `/recommendations` query —
real creators now include `athleanx`, `kingjames`, `lebron`). `is_mock_data`
can now be `true` for two different reasons: no `Creator` rows at all
(falls back to the 3 named mock creators), or real creators exist but at
least one has no stored `FusionScore` yet (falls back to placeholder
0.5/0.5/0.5 per-creator) — both still correctly surfaced by the existing
`is_mock_data` banner, no UI change needed for this.

## Tech stack decision

Next.js (App Router, v16) + TypeScript + Tailwind CSS v4, scaffolded via
`create-next-app` into `frontend/`. No change since Weeks 1-2.

## Routes

| Route | Purpose | Status |
|---|---|---|
| `/` | Landing page, CTA into the flow | Static |
| `/brand-input` | Brand-input flow | Wired — real form (client component), `POST /recommendations` on submit, result handed to `/dashboard` and `/explainability` via `sessionStorage` |
| `/dashboard` | Ranked recommendation dashboard | Wired — reads the stored `/recommendations` response, shows `is_mock_data` banner, `estimated_cost`, cross-references `GET /alerts` for per-creator risk badges |
| `/monitoring` | Monitoring & alerts | Wired — `GET /alerts` on mount, renders severity/reason/source/creator. See "Monitoring — resolved is currently dead" below for why no resolve UI was added |
| `/explainability` | Score-breakdown explainability | **New this round** — shows the real weighted fusion formula per influencer (data already flowing via `/recommendations`), plus a note that the network-graph/causal-insights view is still blocked on Track B's graph data |

Docker deployment skeleton done (`frontend/Dockerfile`, `.dockerignore`,
`next.config.ts` → `output: "standalone"`) — see "Docker" section below.
**Docker build/run itself still not verified — no Docker CLI in this
environment, asked the user about this again this round.**

## 1. Brand-input flow (`/brand-input`)

Unchanged from Weeks 3-4. Real request shape sent to
`POST {NEXT_PUBLIC_API_BASE_URL}/recommendations`
(`src/types/index.ts` → `BrandRecommendationRequest`):

```ts
{
  product_category: string;
  budget: number; // INR, must be > 0 and finite (NaN/Infinity rejected with 422)
  target_region?: string;
  target_demographic?: string;
  platform_preference?: ("youtube" | "instagram" | "reddit")[]; // not exposed in the UI yet
  max_results?: number; // not exposed in the UI yet
}
```

## 2. Results dashboard (`/dashboard`)

Ranked list of influencer cards, populated from `BrandRecommendationResponse.results`.
**Filtering is now real** (was a pure echo-stub through Weeks 1-2): budget is
a hard filter via a placeholder cost heuristic (`estimated_cost`, now shown
in the UI); region/demographic are soft filters (only exclude on a
*confirmed* text mismatch, missing data never excludes); `product_category`/
`platform_preference` remain unfiltered, still open on Track C's side.

Current real response shape (`src/types/index.ts`, matches
`backend/app/schemas.py` exactly as of 2026-08-09):

```ts
interface InfluencerRecommendation {
  creator_id: string; // uuid — was creator_unique_id: string through Weeks 3-4, renamed same-day
  name: string;
  category: string | null;
  youtube_handle: string | null;
  instagram_handle: string | null;
  reddit_handles: string[]; // was reddit_handle: string | null through Weeks 3-4 — now an array
  final_score: number; // 0-100
  confidence_low: number;
  confidence_high: number;
  estimated_reach: number | null;
  estimated_cost: number | null; // new field, placeholder cost heuristic used for the budget filter
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

Risk badge: still **not** part of the recommendation object — computed
client-side by cross-referencing `GET /alerts`, grouped by `creator_id`.

**Real-browser-tested against diversified creator types (2026-08-10).**
Track A added 6 content creators (CarryMinati, Prajakta Koli/MostlySane,
Mumbiker Nikhil, Bhuvan Bam/BBKiVines, Technical Guruji, Guru Mann) this
round — all currently full stubs (`is_stub: true`, real content collection
hasn't landed for them yet). This surfaced a shape not seen in real data
before: `estimated_reach`/`estimated_cost` genuinely `null` (prior stubs
like LeBron/Cristiano always had real numbers derived from subscriber/
follower counts even while empty of content). The dashboard's existing
`estimated_cost != null` guard already handled this correctly — confirmed
live in the browser (the "est. cost" line cleanly disappears rather than
rendering `₹null`), not just re-read from the code. Zero console errors
across all 5 results and all 4 routes. No frontend changes were needed —
existing defensive code already covered this real shape.

Fetches `GET {NEXT_PUBLIC_API_BASE_URL}/alerts` on mount. Current shape:

```ts
interface AlertResponse {
  id: number;
  creator_id: string; // uuid
  severity: "low" | "medium" | "high"; // AlertCreate now enforces this as a strict Literal server-side; AlertResponse itself still types it as plain `str` on the read side, not tightened — assume the 3 values in practice
  reason: string;
  source: string; // e.g. "sentiment_propagation"
  propagated_from_creator_id: string | null; // new (Round 3, committed) — see below
  created_at: string;
  resolved: boolean;
}
```

**Monitoring — `resolved` is currently dead, no UI built around it:**
checked `backend/app/routers/alerts.py` directly — `POST /alerts`
(`AlertCreate`) has no `resolved` field, so every alert is created with
`resolved=False` and **there is no endpoint that can ever set it to
`True`**. `GET /alerts` defaults to `include_resolved=False` server-side
(confirmed in the router code, not just the docs). Given that, an
"include resolved" toggle in the UI would currently be inert — didn't build
one. Revisit if Track C ships a resolve endpoint.

**Propagation-source field: now real and wired in.** `propagated_from_creator_id`
(nullable uuid) landed as committed, pushed code in Track C's Weeks 5-6
work — the migration-drift 500 flagged last round is resolved (verified
live: `POST`/`GET /alerts` with the field both round-trip correctly against
the real Supabase DB). `MonitoringPage` now shows "propagated from
collaborator: {id}" whenever it's non-null. Per Track C's schema comment,
expect it to stay `null` in practice until their Weeks 14-15 Sentiment
Propagation work ships — the UI element exists and is tested, just not
populated by real alerts yet.

**Creator-name resolution added this round (2026-08-09/10).** `AlertResponse`
has no name field (only `creator_id`/`propagated_from_creator_id` uuids) —
previously flagged as an open ask, not built. With Track A's real data now
at 10 creators, this stopped being theoretical: the one real alert in the
live DB renders raw UUIDs with no way to tell who they refer to, and its
`propagated_from_creator_id` points at a creator that no longer exists in
the `creators` table (Track C's own Weeks 7-8 smoke-test data, not live
usage). Added a best-effort client-side resolve: `getCreators()` (new,
`GET /feature-store/creators`) builds a `creator_id → name` map on mount;
`resolveName()` falls back to the raw id when a lookup misses (covers both
a failed fetch and a genuinely orphaned reference like the smoke-test row
above — verified against the real DB, not just reasoned about). New
`CreatorSummary` type in `src/types/index.ts` is a minimal subset of
Track C's `CreatorFeatureRecord` (only `creator_id`/`name`), not a full
mirror, since that's all this feature needs.

## 4. Explainability (`/explainability`)

Fleshed out this round (was text-only through Weeks 3-4). Uses the same
`sessionStorage`-stored `/recommendations` result as the dashboard (shared
via `src/lib/useStoredRecommendationResult.ts`) to show, per influencer, the
weighted fusion formula spelled out: `final_score = (w1×spillover +
w2×sentiment_risk + w3×creator_feature) × 100 [+ risk_adjustment]`, using
the real `score_breakdown` weights/scores already flowing through the app.

One caveat documented in the component itself: the displayed risk-adjustment
figure is **back-derived** (`final_score - weightedSum`), not the
authoritative value — the real `risk_adjustment` field only exists on
`FusionScoreResponse` (`GET /scores/{creator_id}`), not on
`InfluencerRecommendation`, and the backend clamps `final_score` to
`[0, 100]`, so the derived figure would be wrong for any clamped result.
Didn't add a per-creator `GET /scores/{creator_id}` fetch to get the
authoritative value — N+1 fetches for a labeled-as-approximate number felt
like more complexity than the current data warranted; revisit if this
becomes misleading in practice (e.g. once real, non-mock scores start
clamping).

Network-graph visualization + Granger-causality posting-time insights are
still not built — genuinely blocked on Track B's GAIL branch/graph data,
which per the timeline doesn't start until weeks 11-13. Said so explicitly
in the UI rather than a bare "coming soon."

**Checked this round (2026-08-09/10) whether even a minimal version was
buildable now, given real creator-node data exists.** Confirmed via
`GET /feature-store/edges/collaborations` against the live DB: still `[]`,
zero real collaboration edges. This isn't just "still zero as of the last
check" — grepped Track A's pipeline directly and confirmed **no code writes
`CreatorRelatedAccount` rows with `relation_type='frequent_collaborator'`
anywhere**; the value only exists as a comment in the DB schema DDL. So this
is a two-level blocker, not one: even once Track B's GAIL branch starts
(weeks 11-13), there's no data source for it to consume unless Track A
separately builds collaboration-edge detection, which isn't scheduled or
started. Decided not to build a node-only "network graph" with real
creators but zero edges — a graph with no relationships would misrepresent
what the data actually shows, not a minimal-but-honest version of the real
feature. Kept the current explicit placeholder text as the honest option;
flagging the two-level blocker for Track A/B to be aware of rather than
building around it.

**Re-checked Weeks 11-13 (2026-08-10) — still correctly a placeholder, but
the underlying picture changed twice in one round.** Track C shipped
`GET /feature-store/edges/co-occurrence` this round using Track A's real
`reddit_post_creators` data — a genuinely different edge type from
`collaborates_with` (platform co-occurrence via shared community
subreddits, not detected "frequent collaborator" relationships), and per
Track C's own memory it was real and populated at the time they built it
(PV Sindhu/Saina Nehwal co-occurring on 5 real r/badminton posts). **Live
DB check this round: `[]`, zero rows.** Traced precisely rather than just
re-reporting zero: queried `reddit_post_creators` directly — 211 rows
total, **zero** posts with 2+ distinct creators. Track A's own Weeks 11-13
relevance-gating fix (correctly purging 88% of noisy Reddit links) removed
exactly the shared-subreddit overlaps that co-occurrence depends on as a
side effect of that correctness fix, not a new bug. `collaborates_with`
(frequent_collaborator) and `sponsorships` (is_sponsored=true) both still
`[]` too — the latter confirmed still correctly unresolved: the Kohli/
Agilitas post's caption is **still exactly 100 characters** in the live DB
despite Track A reporting the truncation fix as shipped (checked the row
directly, not the changelog — the code fix apparently hasn't been re-run
against already-stored rows yet). Net: still correctly a placeholder, for
three converging real reasons, not one static "still blocked."

## Docker

`frontend/Dockerfile` — 3-stage build (`deps` → `builder` → `runner`) on
`node:20-alpine`, using `next.config.ts`'s `output: "standalone"`.
`.dockerignore` excludes `node_modules`, `.next`, `.git`, `.env*`.

**Verified:** `next build` with `output: "standalone"` produces
`.next/standalone/server.js` correctly (re-checked this round, still true).
**Still not verified:** `docker build`/`docker run` themselves. User said
Docker Desktop was installed this round — checked directly (bash `docker
--version`, PowerShell `Get-Command`/`Test-Path` for the usual install
location, running-process check) and it is **not actually reachable from
this session**: not on PATH, no install directory found, no docker
process running. Flagged back to the user rather than assumed working —
third time this has been asked about, still genuinely blocked on this
session's environment, not on anyone forgetting to ask.

## Field-name mismatch history

Two separate rounds now — kept both so nobody assumes either the Weeks 1-2
or Weeks 3-4 version of this doc was ever fully accurate.

### Round 1 (Weeks 1-2 guess → Weeks 3-4 real contract, 2026-08-09)

| # | Weeks 1-2 guess | Weeks 3-4 real contract |
|---|---|---|
| 1 | `budget_inr` | `budget` |
| 2 | `region_proxy` | `target_region` (optional) |
| 3 | `demographic_proxy` | `target_demographic` (optional) |
| 4 | `platform_handles: {...}` nested object | flat `youtube_handle`/`instagram_handle`/`reddit_handle` |
| 5 | `risk_flags: RiskFlag[]` embedded per recommendation | doesn't exist there — separate `/alerts` resource |
| 6 | `overall_score`/`confidence_interval` tuple | `final_score`/`confidence_low`+`confidence_high` |
| 7 | `MonitoringAlert.influencer_name` | doesn't exist — only `creator_unique_id` |
| 8 | `MonitoringAlert.propagated_from_influencer_id` | doesn't exist — closest was `source` (mechanism, not source creator) |
| 9 | `alert_type` | `reason` + `source` |
| 10 | `feature_score` | `creator_feature_score` + 3 weight fields |

### Round 2 (Weeks 3-4 real contract → Weeks 5-6 real contract, same-day break, 2026-08-09)

Track C's Weeks 3-4 contract itself became stale hours later, once Track
A's real schema was published and Track C reconciled `creator_unique_id`
away:

| # | Weeks 3-4 (Track D built against this) | Weeks 5-6 real contract |
|---|---|---|
| 11 | `creator_unique_id: string` (everywhere: recommendations, alerts) | `creator_id: string` (uuid) |
| 12 | `reddit_handle: string \| null` | `reddit_handles: string[]` |
| 13 | *(no equivalent)* | `estimated_cost: number \| null` — new, now surfaced in the dashboard UI |
| 14 | `MonitoringAlert.propagated_from_influencer_id` — flagged open, not built | Still doesn't exist on the **committed** contract; **in-progress uncommitted** on Track C's live worktree as `propagated_from_creator_id`, currently causing a live-DB 500 for them (schema drift, their bug). Re-check once pushed. |

### Round 3 (Weeks 5-6 real contract → Weeks 7-8 real contract, 2026-08-09/10)

Not a break this time — `propagated_from_creator_id` (flagged as WIP in
Round 2) is now committed and wired in:

| # | Weeks 5-6 (Track D built against this) | Weeks 7-8 real contract |
|---|---|---|
| 15 | `AlertResponse` had no propagation field | `AlertResponse.propagated_from_creator_id: uuid \| null` — committed, live-tested (POST+GET round-trip verified against real Supabase), UI now surfaces it |

No open questions requiring Track D action right now.

### CORS blocker found via first real browser test (2026-08-09) — RESOLVED same day

**Track C's backend had no CORS middleware configured** (`backend/app/main.py`
had no `CORSMiddleware` import or `app.add_middleware(...)` call anywhere).
Every prior "verified" API integration in this project used `curl`, which
doesn't enforce CORS, so this never surfaced until an actual browser hit the
API for the first time this session (the `claude-in-chrome` browser tool
finally connected after a session restart — see track-d memory). Symptom:
the browser's `OPTIONS /recommendations` preflight got a bare `405 Method
Not Allowed` with no `Access-Control-Allow-Origin` header, so the real
`POST` never left the browser and `/brand-input` showed "Couldn't reach the
recommendation API." Same root cause blocked `GET /alerts` on `/monitoring`.
Left untouched at the time per this track's convention of not editing
another track's code unilaterally — flagged for Track C instead, high
priority given it blocked the whole product's browser-based usage.

**Fixed by Track C same day** (commit `71e7d85`, "Add CORS middleware --
no browser could call this API since Weeks 1-2"): standard
`app.add_middleware(CORSMiddleware, allow_origins=settings.cors_allow_origins_list,
allow_methods=["*"], allow_headers=["*"])`, origins configurable via
`cors_allow_origins` setting (defaults to `localhost:3000`/`127.0.0.1:3000`).
**Re-verified for real the same round**: full browser click-through
(`/brand-input` → fill form → submit → `/dashboard` renders real results →
`/explainability` → `/monitoring`) against the live Supabase DB, confirmed
via real preflight response headers (`access-control-allow-origin:
http://localhost:3000`) and zero browser console errors across all 4
routes. This is the first genuinely real (non-curl) end-to-end verification
this project has had.
