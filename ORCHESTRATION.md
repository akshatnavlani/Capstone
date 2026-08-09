# Ingestion Orchestration — Design (Track A)

Status as of 2026-08-09 (Weeks 5-6): **`orchestrator.py` is live and has actually
written real rows to the production Supabase DB** for all three platforms — this is
no longer a skeleton. Run history and real bugs found while getting it working are in
this file below; live row counts are in `DATA_COLLECTION_STATUS.md` Section 5.

This is the "Hermes agent or equivalent automation" from the original Capstone doc:
something that queues targets, calls the right scraper per platform, and merges
results into the DB.

## Scheduling: Windows Task Scheduler, not Hermes (decided 2026-08-10)

Investigated `C:\Users\Sonic\AppData\Local\hermes` directly once given permission to.
Findings: it has a `cronjob` tool, but the tool's own status output lists it under
"missing requirements" (not set up). More importantly, Hermes's core agent loop is
currently broken independent of anything in this project — running its CLI hits
`HTTP 403` from its own LLM provider backend (`chatgpt.com/backend-api/codex/`,
i.e. its configured API key/billing, not anything related to Capstone). Scheduling a
script that doesn't need an LLM at all (`orchestrator.py` is plain Python + subprocess
calls) through a chat-agent tool whose own auth is currently broken is fragile for no
benefit — so used **Windows Task Scheduler** instead: task `CapstoneDataIngestion`,
daily at 10:00 AM, running `scripts/ingestion/run_pipeline.ps1` (all three platforms
sequentially against `target_list.json`, logged to `scripts/ingestion/logs/`).

**Real constraint, not fully hands-off:** the Instagram/Reddit legs go through OpenCLI,
which needs Chrome open and logged in (`OPENCLI_PROFILE`) at run time — a scheduled
task can't launch/log-into Chrome itself. YouTube's official-API leg has no such
requirement. 10 AM was picked as a plausible time Chrome would already be open; this
is a real limitation of the design, not something Task Scheduler or Hermes could fix
either way, given OpenCLI's session model.

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

## Real bugs found and fixed getting the first real run working (2026-08-09)

Wiring the workers against actually-live data surfaced real bugs the design/skeleton
didn't predict — none of these showed up until real subprocess/DB calls ran:

1. **Data corruption: duplicate creator rows.** `get_or_create_creator` used
   `ON CONFLICT DO NOTHING` with no unique constraint on `youtube_handle`/
   `instagram_handle` to actually trigger it — every rerun silently inserted a new
   creator row for the same handle. A single real channel ('athleanx') ended up split
   across two `creator_id`s, with `youtube_channels` and `youtube_videos` pointing at
   different ones. Fixed: added partial unique indexes (migration
   `20260809020000_dedupe_creators.sql`, which also merges the duplicate this bug
   already created) and rewrote the upsert to conflict on the real constraint.
2. **`opencli` not found from Python's subprocess.** `subprocess.run(["opencli", ...])`
   failed with `FileNotFoundError` — Windows `CreateProcess` (no `shell=True`) can't
   resolve a bare command name to the npm-installed `opencli.cmd` shim the way a shell
   does. Fixed with `shutil.which("opencli")` to get the real resolvable path.
3. **Console/subprocess encoding crash on real comment text.** `subprocess.run(text=True)`
   defaults to the OS locale encoding (cp1252 on this machine) to decode child
   stdout — crashed on real emoji in extracted comments (`'charmap' codec can't decode
   byte 0x8d`). Fixed with explicit `encoding="utf-8", errors="replace"`.
4. **Wrong assumed YAML shape for `instagram profile`.** Wrote the parser assuming
   `field`/`value` rows (that's `reddit subreddit-info`'s shape, not Instagram's) —
   `instagram profile` returns a 1-item list of a flat dict instead. `KeyError: 'field'`
   on the first real run; different OpenCLI commands use different output shapes, this
   doesn't generalize.
5. **Instagram's post-grid lazy-load timing is genuinely inconsistent**, not just
   "sometimes needs a scroll" — re-ran the same account (`kingjames`) twice in a row
   and got different scroll counts needed. A fixed 1-scroll fallback wasn't enough;
   padded to a 5-attempt retry loop with scroll+wait between attempts.
6. **Reddit's `read` output has no comment-ID field at all** (checked the raw JSON
   directly) — only `author`/`score`/`text`/`type`. Used a content hash
   (`sha1(post_id:author:text)`) as a stable synthetic `comment_id`, idempotent across
   reruns of the same comment. Also had to filter out `"[+N more replies]"`-style
   placeholder rows (empty `author`) that aren't real comments.
7. **No follower-floor enforcement.** A guessed Instagram handle (`whitneysimmons`,
   intended to be the fitness influencer) resolved to an unrelated real account with
   460 followers — below PROJECT_PLAN.md's 5k-follower scope floor. Cleaned up
   manually; the orchestrator doesn't check this automatically yet — real gap, not
   fixed, see open items.

## What's NOT built yet

- **Follower-floor enforcement** (bug #7 above) — nothing currently stops an
  out-of-scope (or misidentified) account from being ingested.
- **Handle verification before ingestion** — handles are currently supplied on faith
  (a guess from training knowledge, in the one case that went wrong); `opencli
  instagram search` exists and could verify/disambiguate before fetching, not wired in.
- The brand-account scraping worker (extraction logic exists and runs on every
  fetched caption/title/description; the worker that would scrape an *identified*
  brand's own profile doesn't exist yet).
- The target-queue population logic beyond `--handles` on the CLI (how `creators` rows
  get created at real scale — manual seed list vs. discovery scraping).
- Reddit `read` pagination past truncation, and Instagram `browser extract`'s
  initial-render truncation (scoped, not solved — see `DATA_COLLECTION_STATUS.md`).
- Retry/backoff tuning against sustained real-world rate-limit behavior — real runs so
  far are small batches (5-10 items), not sustained multi-hour operation; CAPTCHA/ban
  thresholds are still unknown in practice.
- Real brand-mention hits: 0 so far across all real entities tried (`athleanx`,
  `kingjames`, `r/lebron`) — the extraction module itself is unit-tested and correct
  (caught and fixed a real over-capture bug earlier), but explicit disclosure phrasing
  ("sponsored by X", "#ad") hasn't actually appeared in the real captions/descriptions
  sampled so far. Not yet proven against a real positive case — worth deliberately
  seeking one out (verified via `instagram search` first, not guessed) before trusting
  the brands pipeline is validated end-to-end.

## Running it

```
python scripts/ingestion/orchestrator.py --platform youtube --handles athleanx
python scripts/ingestion/orchestrator.py --platform instagram --handles kingjames
python scripts/ingestion/orchestrator.py --platform reddit --handles lebron
```
Real run so far (2026-08-09): 3 creators, 10 YouTube videos + 200 comments, 5 Instagram
posts + 71 comments, 6 Reddit posts + 135 comments — all live in Supabase. See
`DATA_COLLECTION_STATUS.md` Section 5 for the up-to-date table.

## Per-platform sub-agents are NOT a safe parallel axis for browser platforms (2026-08-11)

**Real incident, not theoretical.** Weeks 9-10 dispatched one sub-agent per platform
(YouTube/Instagram/Reddit) concurrently. Result:

- YouTube: clean (119 videos, 2,746 comments) — it uses the official Data API, no browser.
- Instagram: 4 of 9 creators succeeded.
- Reddit: **0 of 8 creators succeeded** — every one failed with
  `TypeError: Failed to fetch` from the OpenCLI browser bridge.

The interleaved log timeline shows why. Reddit's entire batch collapsed inside a
22-second window (21:14:46 → 21:15:08) *while the Instagram run was actively driving
the same browser*; Instagram then recovered and kept succeeding at 21:15:39, 21:17:31,
21:19:07. Chrome never crashed (12 processes still alive afterward).

**Root cause: Instagram and Reddit are different *platforms* but share one
Chrome/OpenCLI session.** "One sub-agent per platform" looks like an independent axis
and isn't — the real axis is the *browser session*, and there is exactly one. This is
the same constraint as the long-standing "don't run multiple sub-agents against one
platform" rule, just one level up: it's not per-platform, it's per-session.

**Rule going forward:** YouTube may run concurrently with anything (own API, own quota).
**Instagram and Reddit must be serialized against each other.** `run_pipeline.ps1`
already does this correctly (sequential loop) — only the sub-agent dispatch path had
the flaw. Re-running Reddit alone afterward collected cleanly with zero fetch errors,
confirming contention rather than a Reddit-side problem.

### Secondary finding: the scroll-until-full change made Instagram more brittle

The Weeks 9-10 grid-scroll loop raises `no post links found after scrolling` when it
finds nothing, where the previous code silently took whatever the first screenful had.
Under browser contention that converted a degraded-but-partial result into a total
per-creator failure (5 of 9 Instagram creators). The hard failure is arguably more
honest than silently under-collecting, but it should degrade rather than abort —
worth revisiting.

### Third finding: Instagram grid stalls at ~12 links for most profiles

Even successful creators mostly yielded 12 posts against a cap of 40 ("12 links
found"); only `virat.kohli` reached the cap (48 links found). The stall-detector is
firing early on most profiles, so Instagram is under-yielding independently of the
contention issue. This — not the post cap — is now the binding constraint on Instagram
volume, and is the place a dedicated scraping backend (e.g. Apify, if it ever becomes
reachable) would genuinely help.
