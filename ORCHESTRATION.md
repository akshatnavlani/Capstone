# Ingestion Orchestration — Design (Track A)

Status as of 2026-08-09: **design + skeleton; all three platforms now confirmed
reachable with real commands and real latency numbers** (`DATA_COLLECTION_STATUS.md`
Section 4) — both OpenCLI blockers are closed (real Chrome, not Arc — see that doc's
Section 2). The worker/rate-limiter shape below is validated against real pilot calls,
not just designed on paper. Wiring the actual `# TODO`s in `orchestrator.py` against
these now-proven commands is the next concrete step, still open as of this writing.

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
  minimum-interval gate — real measured OpenCLI-via-Chrome latency is 5.1-8.6s/call
  (avg 6.68s across 5 real pilot calls, see `DATA_COLLECTION_STATUS.md` Section 4b),
  meaningfully slower than the ~2-3s/call the Weeks 1-2 design assumed. Gate should be
  tuned around the real number, not the borrowed one.
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

## Real command reference (confirmed working 2026-08-09)

For filling in `orchestrator.py`'s `# TODO`s — these are the actual commands used in
the pilot, not documentation guesses. All OpenCLI calls need `OPENCLI_PROFILE` set
(see `.env`) or `--profile <id>` as a global flag (before the subcommand).

- Reddit profile-equivalent: `opencli reddit subreddit-info <name> -f yaml`
- Reddit post listing: `opencli reddit subreddit <name> -f yaml`
- Reddit post + comments (bundled in one call): `opencli reddit read <post_id> -f yaml`
  — truncates past ~68-90 comments on high-engagement posts ("[+N more]"); full
  retrieval needs pagination, not yet implemented.
- Instagram profile: `opencli instagram profile <username> -f yaml`
- Instagram post listing: `opencli instagram user <username> --limit N -f yaml` —
  returns captions + like/comment counts, no comment text and no post URLs.
- Instagram post URLs (needed for the comment pipeline below, not returned by `user`):
  `opencli browser <session> open <profile_url>` then
  `opencli browser <session> find --css 'a[href*="/reel/"], a[href*="/p/"]'`.
- Instagram comments (see "Instagram comment extraction" below for the full pipeline):
  `opencli browser <session> open <post_url>` then `opencli browser <session> extract`,
  parsed with `scripts/ingestion/instagram_comment_extract.py`.
- YouTube: use the real Data API (`YOUTUBE_API_KEY` in `.env`, verified working) as
  primary; yt-dlp commands from `DATA_COLLECTION_STATUS.md` Section 4a as supplement.

## Instagram comment extraction (added 2026-08-09)

OpenCLI has no dedicated comment-reading command for Instagram. Per the user's
instruction to try OpenCLI first and fall back to Apify only if that failed: it didn't
fail. `opencli browser <session> extract` on an opened post page renders the comment
section into the page's markdown (author, text, like count, and a permalink containing
a real comment ID) — `scripts/ingestion/instagram_comment_extract.py::parse_comments()`
parses it. Validated against 2 real posts of different types (30 comments total,
including multi-paragraph text and emoji) — see `DATA_COLLECTION_STATUS.md` Section 4b
for the full validation writeup and known caveats (initial-render truncation on
high-engagement posts, not yet load-tested at volume). Apify was never actually used.

This adds a 4th call per Instagram post to the worker's per-entity cost (listing →
find post URLs → open post → extract), on top of the 1 `user`-listing call — see
`DATA_COLLECTION_STATUS.md` Section 4c for the revised reachable-entities estimate now
that this exists.

## What's NOT built yet (intentionally — Weeks 3-4 scope, still open as of 2026-08-09)

- The actual response-parsing code behind each `# TODO` in `orchestrator.py` — the
  commands above are confirmed working and their real output shape has been seen
  (YAML for OpenCLI, JSON for the Data API and yt-dlp), but nothing parses it into
  the DB schema yet.
- The brand-account scraping worker described above (extraction logic exists; the
  worker that acts on its output doesn't yet).
- The target-queue population logic (how `creators` rows get created in the first
  place — manual seed list vs. discovery scraping).
- Reddit `read` pagination past the ~68-90 comment truncation point, and equivalent
  pagination for Instagram's `browser extract` comment truncation.
- Wiring `instagram_comment_extract.py` into the actual `InstagramWorker` — the parser
  exists and is tested against saved output, but the worker doesn't call the
  open→extract→parse sequence yet.
- Retry/backoff tuning against sustained real-world rate-limit behavior — the pilot was
  a handful of calls with manual 3s gaps, not a sustained multi-hour run, so CAPTCHA/ban
  thresholds are still unknown in practice.

## Skeleton

See `scripts/ingestion/orchestrator.py` — a runnable skeleton with the worker/rate-limiter
shape above, `# TODO` markers where platform-specific calls go, and DB upsert stubs
against the schema in `SCHEMA.md`. Wired to a live DB now (`DATABASE_URL` is set in
`.env`, Supabase is provisioned and verified) but the platform-call TODOs are still
unfilled, and nothing is scheduled anywhere yet.
