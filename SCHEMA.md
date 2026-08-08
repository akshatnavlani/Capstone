# Data Layer Schema — Track A (Data/Infra)

Status as of 2026-08-08: **finalized for Weeks 1-2, DDL committed**, DB provisioning
in progress. Build API contracts / graph-loading code against this file. If anything
here changes later, this file will be updated and re-pushed to `track-a-data-infra` —
diff it before assuming it's stale.

- DDL: `supabase/migrations/20260808163402_init_schema.sql`
- Target DB: Supabase (managed Postgres). Connection details go in `.env` (see
  `.env.example`), never committed.

## Design

One seed table (`creators`) + per-platform profile/content tables, all keyed to
`creators.creator_id` (uuid). This matches the original doc's Table 1/2/3/4/5 design
and PROJECT_PLAN.md Section 1 — that section confirmed the original design was sound
and should be kept.

```
creators (seed)
  ├─ creator_related_accounts   (non-owned related handles: team/fan/collab pages)
  ├─ youtube_channels  ──< youtube_videos ──< youtube_comments
  ├─ instagram_profiles ──< instagram_posts ──< instagram_comments
  └─ reddit_profiles    ──< reddit_posts    ──< reddit_comments
```

### `creators`
| column | type | notes |
|---|---|---|
| `creator_id` | uuid PK | = the "unique_id" from the original doc |
| `name` | text | |
| `category` | text | `athlete \| team \| league \| fitness_influencer \| lifestyle_influencer \| other` |
| `youtube_handle` / `instagram_handle` | text | official handle, nullable |
| `reddit_handles` | text[] | often plural (personal + team/fan subreddits, e.g. r/nba, r/lebron) |

**No `prior_endorsements` column.** Per PROJECT_PLAN.md Section 1, historical
partnership data is *derived*, not manually compiled — see `creator_sponsorship_events`
view below. Don't add a manual endorsements field; query the view instead.

### Per-platform tables
Each platform has a profile-level table (`*_profiles`/`*_channels`) and a content-level
table (`*_posts`/`*_videos`), both carrying a nullable `creator_id` FK back to the seed
table (nullable because e.g. a Reddit commenter or fan account isn't always the creator
themselves). Content tables carry:
- `is_sponsored boolean` — **nullable, not yet populated.** This is the disclosure-tag
  label (`#ad`, `#sponsored`, etc.) and per Section 1 is the **sole source of GAIL
  treatment labels** — precision-critical. Track A stores raw scraped text; the
  labeling pipeline itself is Track C's Weeks 7-8 deliverable (per the timeline table).
  Don't build your own separate labeling logic against raw text — wait for
  `is_sponsored` to be populated, or coordinate with Track C if you need it sooner.
- `sponsorship_raw_matches jsonb` — matched disclosure phrases, kept for auditing the
  labeler's precision (this is why it's flagged load-bearing in the plan).
- `is_bot_flagged boolean` / `bot_score real` on profile tables — nullable, populated by
  Track B's heuristic bot-detection module (Weeks 7-8 per timeline). Track A supplies
  the raw signals it needs: `follower_count`/`following_count` ratio, `account_created_at`
  (YouTube/Reddit only — Instagram doesn't expose this via scraping), posting frequency
  (derivable from `posted_at`/`published_at` timestamps).
- Raw text is stored as scraped (`caption`, `title`, `body`, `description`). No
  scrubbing/normalization happens in this DB — that's Track C's Edge Preprocessing
  pipeline (Weeks 7-8), operating downstream on this raw data.

### `creator_sponsorship_events` (view)
`UNION ALL` across `youtube_videos` / `instagram_posts` / `reddit_posts` where
`is_sponsored = true`. This *is* the "Historical Data - Partnerships/Collaborations"
Layer-1 source from the HLD — query this view, don't expect a separate table.

## Known open items / things that will change

- **Region/demographic proxy signals** (Section 1: bio text, comment language,
  hashtags, posting timezones) are captured via existing raw columns
  (`bio`, `hashtags`, `posted_at`) — no dedicated derived columns yet. If Track B/C
  need a precomputed region signal, that's a downstream feature-store concern, not a
  raw-ingestion-table concern; flag if you disagree.
- **Brand name extraction** from sponsorship text (e.g. "which brand sponsored this
  post") is NOT in scope for this schema — `sponsorship_raw_matches` only stores the
  matched disclosure phrase, not a parsed/normalized brand entity. If GAIL needs brand
  nodes with names (not just a binary treatment flag), that requires either a NER step
  downstream or a schema extension — tell me if you need this and I'll add it.
- **QA/data-completeness tracking** (flagging gaps against the 1k/entity floor) is a
  Weeks 7-8 Track A deliverable, not built yet.
- Table/column names may still shift slightly once real scraped payloads (YouTube API
  JSON, agent-reach/OpenCLI output shapes) are seen in Weeks 3-4 — treat this as
  stable-but-not-frozen.

## Cross-track check (2026-08-08) — 2 unresolved mismatches, flagging rather than silently deciding

Checked `origin/track-b-ml-core:GRAPH_SCHEMA.md`, `origin/track-c-fusion-backend:API_CONTRACTS.md`,
`origin/track-d-frontend-app:WIREFRAMES.md` via `git fetch`. All three now exist. Two real
disagreements found — **not resolved unilaterally here, need explicit confirmation:**

### 1. Who computes `is_sponsored`? (Track A vs. Track C)

`API_CONTRACTS.md` states Track C's current assumption: **Track A computes `is_sponsored`
upstream and sends it pre-labeled** via the ingestion endpoints.

This schema does the opposite: `is_sponsored` is stored **nullable/unpopulated** by Track A.
My reading is based on PROJECT_PLAN.md Section 6's weekly timeline, row "7-8", **Track C's own
column**, which reads: *"Text scrubbing + temporal normalization + sponsorship labeling
pipeline."* That literally assigns the disclosure-tag labeling step to Track C, not Track A.

**This needs to be settled before Week 7-8**, or the labeling step risks falling through the
cracks (both tracks think the other owns it) — it's flagged in PROJECT_PLAN.md Section 1 as
precision-critical (sole source of GAIL's treatment labels), so an ownership gap here is a real
risk, not a paperwork detail. Recommend: whichever track ends up owning it, `sponsorship_raw_matches`
(matched disclosure phrases) stays on Track A's ingestion tables either way, so the labeler
(wherever it runs) has an audit trail.

### 2. Brand-side data — not in Track A's current scope

`GRAPH_SCHEMA.md` flags that Track B's `brand` graph node assumes a feature vector (BERT
embedding of "brand product/marketing copy" + `budget_tier` + industry category) that **no
Track A table currently supplies** — PROJECT_PLAN.md Section 1 (Data Collection) only scopes
creator-side YouTube/Instagram/Reddit scraping and never mentions collecting brand profile data.

Two options, not yet decided:
- **(a) No new scraping** — Track B derives brand node identity/features from the brand-name
  text already implicit in `sponsorship_raw_matches` on creator posts (Track B does its own
  BERT embedding of that extracted text). Stays within Track A's current scope; brand node
  features would be sparser (no follower counts, no official bio).
- **(b) Track A adds brand-handle scraping** (a real scope addition — brand social profiles
  aren't in PROJECT_PLAN.md today) to give Track B's brand nodes actual profile-level features.

Leaning toward (a) as the lower-risk default given the timeline, but this affects Track B's
model design, not just data plumbing — needs Track B/user sign-off, not a Track A unilateral
call.
