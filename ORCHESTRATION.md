# Ingestion Orchestration — Design (Track A)

Status: **design + skeleton only**, per the Weeks 1-2 objective. Full automation is a
Weeks 3-4 deliverable, built once real scraping starts and we've seen actual
agent-reach/OpenCLI/YouTube API output shapes (Section 4 of `DATA_COLLECTION_STATUS.md`
notes the throughput numbers are still unvalidated — the orchestrator's rate limiter
will need tuning against real numbers, not the estimates below).

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

## What's NOT built yet (intentionally — Weeks 3-4 scope)

- Actual platform-call logic (the real `opencli instagram user X --limit 12` /
  `yt-dlp`/YouTube Data API calls and response parsing) — depends on real output
  shapes I haven't seen live data for yet.
- The target-queue population logic (how `creators` rows get created in the first
  place — manual seed list vs. discovery scraping).
- Retry/backoff tuning against real observed rate-limit behavior.

## Skeleton

See `scripts/ingestion/orchestrator.py` — a runnable skeleton with the worker/rate-limiter
shape above, `# TODO` markers where platform-specific calls go, and DB upsert stubs
against the schema in `SCHEMA.md`. Not wired to a live DB yet (needs `DATABASE_URL` in
`.env` once Supabase is provisioned) and not scheduled anywhere.
