# Ingestion Orchestration — Design (Track A)

Status as of 2026-08-09: **design + skeleton, still not wired to real platform calls**.
YouTube got a real pilot (see `DATA_COLLECTION_STATUS.md` Section 4a) confirming the
worker/rate-limiter shape works mechanically, but Instagram/Reddit workers remain
untestable — both still blocked on the OpenCLI Chrome extension (same doc, Section 2/3).
Full wiring is still Weeks 3-4 scope, now further along for YouTube than IG/Reddit.

This is the "Hermes agent or equivalent automation" from the original Capstone doc:
something that queues targets, calls the right scraper per platform, and merges
results into the DB. It does not have to be the specific `hermes-agent` app already
installed on this machine (`C:\Users\Sonic\AppData\Local\hermes`) — that looks like a
general personal-agent tool unrelated to this project, and I'm not wiring into it
without you asking, since it's your own environment. The design below is a standalone
script that could later be scheduled by anything (cron, that Hermes app, n8n, etc.).

## Design

```
             ┌─────────────┐
             │  creators   │  target queue (rows needing a scrape pass)
             └──────┬──────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
  YouTube worker  IG worker   Reddit worker      one worker per platform,
  (Data API,      (OpenCLI,   (OpenCLI or         each enforcing ITS OWN
   no session      single      rdt-cli, single     rate limit — see below
   bottleneck)     session)    session)
        │            │            │
        └────────────┴────────────┘
                     ▼
              upsert into DB
        (youtube_*/instagram_*/reddit_* tables,
         keyed on platform-native IDs — safe to
         re-run, re-scraping just updates metrics)
```

Key decisions:
- **One worker per platform, not one worker per creator.** Since IG/Reddit throughput
  is capped by a single logged-in session (see `DATA_COLLECTION_STATUS.md` Section 4),
  running many creator-level workers in parallel against the same platform doesn't help
  — they'd all serialize on the same rate limit anyway, and parallel attempts risk
  triggering CAPTCHA/bans faster. YouTube's worker *can* be parallelized more freely
  since it's quota-based, not session-based, but there's no evidence yet that YouTube
  needs it given the target influencer count.
- **Rate limiting lives in the worker, not the caller.** Each platform worker holds a
  minimum-interval gate (~2-3s between OpenCLI calls, tunable) so nothing upstream has
  to reason about it.
- **Upsert on natural platform IDs** (`video_id`, `post_id`, `comment_id`, etc.), so
  re-running a scrape pass is idempotent — a later pass just refreshes metrics
  (view/like/comment counts change over time, which is useful data itself, not just
  noise, but that's a v2 concern — first pass just upserts current values).
- **Checkpointing:** each worker tracks `fetched_at` per row already; a "gap-filling"
  pass (Weeks 9-10 per the timeline) is just "re-run for creators whose most recent
  content's `fetched_at` is stale."
- **Failure handling:** log and skip on a single creator/call failure, don't let one
  bad handle kill the whole batch. Retry transient errors (network, 429) with backoff;
  don't retry auth/not-found errors.

## Brand-name extraction step (added 2026-08-09)

New pipeline step, inserted between fetch and upsert for the three content workers:
after a post/video's caption/title/body text is fetched, run
`scripts/ingestion/brand_extraction.py::extract_brand_mentions()` on it. If it returns
a candidate, upsert a `brands` row (or match an existing one by name) and set the
content row's `brand_id`. This is a coarse lead-generation regex, not the real
`is_sponsored` classifier — see `SCHEMA.md` "Brand-side data" for the scope boundary
between this and Track C's Weeks 7-8 labeling pipeline. Built and unit-tested (caught
a real over-capture bug in the first draft — see `SCHEMA.md`'s adversarial self-check
section), not yet run against real content since there's no real content in the DB yet.

Once a brand is identified, a fourth worker type (not yet written) scrapes that
specific brand's official account(s) for `brands.category/follower_count/post_count` —
same per-platform backends as the creator workers, same session-rate-limit
considerations apply. Bounded by construction: this worker only ever runs against
brand names the extraction step actually found, never an open-ended brand search.

## What's NOT built yet (intentionally — Weeks 3-4 scope, still open as of 2026-08-09)

- Actual platform-call logic (the real `opencli instagram user X --limit 12` /
  YouTube Data API calls and response parsing) — still blocked on Instagram/Reddit
  session access and the YouTube API key (`DATA_COLLECTION_STATUS.md` Section 3).
  yt-dlp-based YouTube calls ARE validated now (Section 4a of that doc).
- The brand-account scraping worker described above (extraction logic exists; the
  worker that acts on its output doesn't yet).
- The target-queue population logic (how `creators` rows get created in the first
  place — manual seed list vs. discovery scraping).
- Retry/backoff tuning against real observed rate-limit behavior — still can't be done
  for IG/Reddit without a live session; YouTube's yt-dlp latency numbers from the pilot
  (1.2-8.5s/call depending on call type) are a starting point for that worker's gate.

## Skeleton

See `scripts/ingestion/orchestrator.py` — a runnable skeleton with the worker/rate-limiter
shape above, `# TODO` markers where platform-specific calls go, and DB upsert stubs
against the schema in `SCHEMA.md`. Wired to a live DB now (`DATABASE_URL` is set in
`.env`, Supabase is provisioned and verified) but the platform-call TODOs are still
unfilled, and nothing is scheduled anywhere yet.
