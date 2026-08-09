# Data Layer Schema — Track A (Data/Infra)

Status as of 2026-08-09: **live on Supabase Postgres, 12 tables + 1 view, verified
column-by-column against the migration files** (see "Adversarial self-check" below).
Build API contracts / graph-loading code against this file. If anything here changes
later, this file will be updated and re-pushed to `track-a-data-infra` — diff it
before assuming it's stale.

- DDL: `supabase/migrations/` (applied in filename order: `20260808163402_init_schema.sql`,
  `20260809000000_fix_missing_reddit_indexes.sql`, `20260809010000_add_brands.sql`,
  `20260809020000_dedupe_creators.sql`)
- **`creators.youtube_handle`/`instagram_handle` now have real unique partial
  indexes** (added in the dedupe migration) — found via a real bug where the
  ingestion orchestrator's `ON CONFLICT DO NOTHING` had no matching constraint and
  silently created duplicate creator rows on every rerun. See `ORCHESTRATION.md` for
  the full bug list from wiring the orchestrator for real.
- **`reddit_comments.comment_id` is a synthetic content-hash, not a real Reddit ID** —
  `opencli reddit read` exposes no comment-ID field at all (checked the raw JSON).
  `sha1(post_id:author:text)` stands in, idempotent across reruns of the same comment
  but not a real externally-meaningful identifier if you need to cross-reference
  against Reddit directly.
- DB: Supabase (managed Postgres), project provisioned 2026-08-08. Connection details
  go in `.env` (see `.env.example` for the required keys), never committed — ask the
  user directly for real credentials if you need them, they aren't in git or memory.

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
Layer-1 source from the HLD — query this view, don't expect a separate table. Now
also carries `brand_id` (see "Brand data" below), for Track B's `(brand, sponsors,
creator)` graph edge.

### `brands` (added 2026-08-09 — see "Brand data" below)
Seed table analogous to `creators`, but deliberately populated only from names
extracted out of sponsorship-disclosure text already collected on creator content
rows — not an independent brand-discovery crawl. `youtube_videos.brand_id` /
`instagram_posts.brand_id` / `reddit_posts.brand_id` (all nullable) link a sponsored
content row to the brand it names.

## Known open items / things that will change

- **Region/demographic proxy signals** (Section 1: bio text, comment language,
  hashtags, posting timezones) are captured via existing raw columns
  (`bio`, `hashtags`, `posted_at`) — no dedicated derived columns yet. If Track B/C
  need a precomputed region signal, that's a downstream feature-store concern, not a
  raw-ingestion-table concern; flag if you disagree.
- **QA/data-completeness tracking** (flagging gaps against the 1k/entity floor) is a
  Weeks 7-8 Track A deliverable, not built yet.

## Adversarial self-check (2026-08-09)

Actively re-verified rather than trusting the Weeks 1-2 summary. Findings:

- **DB drift check:** dumped every live column (name/type/nullable/default) from
  `information_schema.columns` and diffed against the migration file by hand — exact
  match, no drift, before any fixes were applied.
- **Real bug found and fixed:** `reddit_profiles.creator_id`, `reddit_posts.author_username`,
  and `reddit_comments.author_username` are FK columns that had **no index** —
  inconsistent with `youtube_channels.creator_id` / `instagram_profiles.creator_id`,
  which do. Fixed in `20260809000000_fix_missing_reddit_indexes.sql` and verified live
  via `pg_indexes`. Cheap to catch now (0 rows in the DB); would've been a real
  performance problem once `ON DELETE SET NULL` had to scan populated Reddit tables.
- **Real bug found and fixed in new code:** the first draft of `brand_extraction.py`'s
  regex over-captured brand names (matched "Nike for this drop" instead of "Nike")
  because of a greedy character class. Caught by the module's own `__main__` self-test
  before this was ever wired into the orchestrator. Fixed by switching to a
  consecutive-capitalized-words heuristic.
- **agent-reach doctor re-run:** identical status to Weeks 1-2 (Instagram/Reddit still
  blocked on the Chrome extension, YouTube still yt-dlp-only) — no drift, but also no
  progress since the blockers are still open.
- **Throughput estimate re-derivation — see `DATA_COLLECTION_STATUS.md` "Adversarial
  re-check" section for the full writeup.** Short version: the ~2-3s/call figure the
  Weeks 1-2 estimate leaned on turned out to be documented by agent-reach specifically
  for Xiaohongshu, not Instagram or Reddit — those platforms' docs only say "back off
  on 429," no concrete number. A real YouTube pilot (the one platform not blocked) also
  showed comment yield per video varies by roughly an order of magnitude between a
  team/brand account and a personal creator account, which the original flat
  "30-50 calls/entity" assumption didn't account for. Net effect: less confidence in
  the 1,500-2,500 figure than the Weeks 1-2 doc implied, not more.
- Table/column names may still shift slightly once real scraped payloads (YouTube API
  JSON, agent-reach/OpenCLI output shapes) are seen in Weeks 3-4 — treat this as
  stable-but-not-frozen.

## Cross-track check (updated 2026-08-09)

### 1. Who computes `is_sponsored`? — RESOLVED, Track A's design confirmed correct

User confirmed 2026-08-09: PROJECT_PLAN.md Section 6's timeline row 7-8 does assign the
sponsorship labeling pipeline to Track C, as read here. Track C has been told directly to
fix `API_CONTRACTS.md` to match this schema. **Note:** re-checked `origin/track-c-fusion-backend:API_CONTRACTS.md`
on 2026-08-09 and it still says "Track A sends it pre-computed" as of that commit — Track C's
fix hasn't landed on their branch yet. Not a Track A action item; just noting it's not
actually closed on their side yet, re-check before assuming it's fixed.

### 2. Brand-side data — RESOLVED, real scope addition (2026-08-09)

User decided GAIL needs real brand features, not text-derived approximations only. Added:
`brands` table + `brand_id` FK on all three platform content tables + brand extraction
module (`scripts/ingestion/brand_extraction.py`). **Deliberately bounded**, per explicit
instruction: brands are identified ONLY from names/mentions found in sponsorship-disclosure
text already being collected from creators (see `brand_extraction.py`'s regex-based lead
extraction) — this is NOT an open-ended brand-discovery crawl. Once a brand name is
identified this way, Track A scrapes that brand's own official account(s) on the same
platform(s) for basic profile data (category, follower count, post count, verification).

**Important scope distinction, to avoid a third cross-track mismatch:** `brand_extraction.py`'s
regex matching is a coarse "lead generation" pass to decide which brand accounts to go scrape
— it is explicitly NOT the precision-validated `is_sponsored` classifier from item 1 above
(that's still Track C's Weeks 7-8 job). Don't treat a populated `brand_id` as proof
`is_sponsored` has been reliably set for that row — check `is_sponsored` itself.

**Status as of 2026-08-09: schema + extraction logic built and unit-tested (see
`scripts/ingestion/brand_extraction.py`'s `__main__` self-test — caught and fixed a real
over-capture bug in the first draft regex). NOT yet run against real data** — there is no
real scraped content in the DB yet (Instagram/Reddit still blocked on the OpenCLI Chrome
extension; YouTube Data API key not yet provided — see `DATA_COLLECTION_STATUS.md`). This
will run for real once the orchestrator starts landing real captions/titles/bodies.

Flagged for Track B: `brands` now exists with real columns (not the placeholder BERT-of-marketing-copy
vector from `GRAPH_SCHEMA.md`) — re-check `GRAPH_SCHEMA.md`'s brand feature vector assumption
against the actual `brands` table shape above once real rows start landing.
