# Handoff — Track C (Fusion + Backend)

**Read this first, before memory, before re-deriving anything from git log.**
This is the canonical "start here" doc for a fresh session on this track.
Memory (`C:\Users\Sonic\.claude\projects\D--Capstone\memory\`) has the
detailed week-by-week history if you need it, but this file is the
current-state summary — trust it over stale memory entries if they disagree.

Last updated: 2026-08-10, end of a session spanning (compressed, not literal
calendar weeks) Weeks 1-2 through Weeks 14-16 of the 26-week plan.
`API_CONTRACTS.md` at repo root is the living API contract doc — read that
too before touching any endpoint shape.

**Note for the next session:** `PROJECT_PLAN.md` Section 1 was revised on
`main` (2026-08-10) but that revision has not been merged into this branch
yet — the copy in this worktree is still the pre-revision version. The
real change: data collection pivoted from ~15 deep creators to
breadth-over-depth (~1,000 curated creators, 200-400 datapoints/entity),
adding team/league accounts specifically to attack the zero-collaboration-
edges blocker, via a new identify→curate→deepen Google-Sheets workflow.
Nothing for Track C to build off this directly yet, but expect creator/
content volume growth patterns to look different once Track A acts on it.

## Current state (one paragraph)

A FastAPI + SQLModel backend (`backend/`) is live and connected to the real
shared Supabase Postgres instance (16 real creators, 695 real content rows
as of last check — 252 YouTube / 97 Instagram / 346 Reddit, grown from 422
via Track A's background scheduled collection since the last round). Full API
surface exists and is tested: `/health`, `/recommendations` (real
budget/region/demographic/product_category/platform_preference filtering,
not a stub), `/ingestion/*` (8 endpoints, secondary/manual write path —
**Track A's real orchestrator writes directly to Postgres and bypasses
these entirely**, see gotcha #2 below), `/scores/*` (Fusion Layer formula,
weights still placeholder pending real GAIL/Temporal output), `/alerts`
(with a `propagated_from_creator_id` field pre-added for Sentiment
Propagation), `/feature-store/*` (real transformation pipeline Track B
actively consumes — creators, collaboration edges, co-occurrence edges,
sponsorship edges), `/labeling/run` (real disclosure-tag `is_sponsored`
classifier, precision-validated against real scraped text, not just
synthetic). CORS is configured and **confirmed working by Track D in an
actual browser** (not just curl) — this was a real 8-week-invisible gap,
fixed. Basic auth (`API_KEY` env var) exists, off by default. 48 tests
pass (`backend/tests/`, `pytest`). Migrations for Track C's own tables
live in `backend/migrations/` with a README explaining why (see gotcha #1).
Working tree is clean and fully pushed as of this handoff.

**What's explicitly still placeholder/not real:** `spillover_score` /
`sentiment_risk_score` / `creator_feature_score` in the fusion formula are
always caller-supplied or a flat 0.5 default — no real GAIL or Temporal
branch output exists yet to wire in (that's Track B's Weeks 11-15+ work).
Fusion weights are uncalibrated defaults. `reputation_score` has no real
source anywhere in the system.

## Open items

- **Kohli/Agilitas `is_sponsored` edge case — still blocked on Track A,
  re-checked directly against the live DB this round (2026-08-10 Weeks
  14-16), no change.** Both the original post and its sibling post are
  still stored at exactly 100 chars, `fetched_at` still 2026-08-09 —
  Instagram has not been re-scraped since Track A's caption-fix commit.
  Currently labeled `is_sponsored=false` with the reasoning documented in
  `API_CONTRACTS.md` (search "Kohli/Agilitas"). **Action once Track A
  re-scrapes Instagram (check for `fetched_at` timestamps past their fix
  commit before assuming): call `POST /labeling/run?force=true`** to
  re-examine every Instagram row against corrected text.
- **`reputation_score` — blocked, no owner.** No table in Track A's schema
  has a source column for this, and none of their recent work has added
  one. Track B's `ml/schema.py` expects it in the creator feature vector.
  Needs either a new Track A column or an explicit team decision on a
  derivation formula (a sentiment-based proxy is plausible now that Track
  A's Reddit data is reliably relevant, but building that sentiment
  analysis is Track B's Temporal-branch job, not Track C's — don't build
  it here unilaterally).
- **`co_occurs_with` edges — not blocked, currently empty, will self-heal.**
  Track A purged the noisy Reddit data these were built from. No Track C
  action needed; the feature store recomputes from live DB state on every
  request (nothing cached), so real edges will reappear automatically once
  Track A's new two-mode Reddit collection produces genuine co-occurrences.
  Don't be alarmed if `/feature-store/edges/co-occurrence` returns `[]` —
  check the row counts in `reddit_post_creators` before assuming a bug.
- **Weeks 14-15 Fusion Layer "real" implementation — blocked on Track B.**
  Per PROJECT_PLAN.md Section 6, this is nominally the next milestone, but
  it requires real `spillover_score`/`sentiment_risk_score` values from
  Track B's GAIL/Temporal branches, which don't exist yet (Track B's own
  memory: still 0 real edges/sponsorships as of this session). Check
  `origin/track-b-ml-core:GRAPH_SCHEMA.md` fresh before assuming this is
  still blocked — it may have landed.
- **`@app.on_event("startup")` deprecation warning — not started, low
  priority.** FastAPI wants lifespan handlers instead. Cosmetic, not
  broken, just noted so it doesn't surprise a future session.
- **`backend/.env` recurring disappearance — not a real gap, just an
  environment quirk.** Has gone missing between sessions multiple times in
  this shared multi-session environment (not corruption — content is fine
  when present). If missing, just recreate it from the credential you
  already have from earlier conversation turns; never ask the user to
  re-share it, and never write it to memory or git.

## Non-obvious lessons (the stuff not visible from reading the code)

1. **`SQLModel.metadata.create_all()` only creates missing tables — it
   never alters existing ones.** This caused a real live-production 500:
   a column was added to a SQLModel class whose table already existed in
   Supabase, and the column silently never reached the real table. Any
   future schema change to an *existing* Track-C-owned table
   (`fusionscore`, `riskalert`) needs a hand-written SQL file in
   `backend/migrations/` (see that folder's README) — editing `models.py`
   alone is not enough once a table already exists in production.
2. **Track A's real orchestrator bypasses `/ingestion/*` entirely** — it
   writes straight to the shared Postgres via `DATABASE_URL`. The
   ingestion endpoints in this backend are a secondary/manual write path
   (useful for testing, seeding), not the actual data pipeline. Don't
   assume traffic flows through them when debugging data issues.
3. **Track A's upsert never touches `is_sponsored`/`sponsorship_raw_matches`
   — those are Track C's columns.** So once a row is labeled, it's frozen
   even if Track A later corrects the underlying text (e.g. a truncation
   bug fix). This is exactly why `POST /labeling/run?force=true` exists —
   default mode only processes still-null rows and will never re-examine
   an already-labeled row on its own.
4. **Testing gotchas that cost real time this session**: a plain
   `create_engine("sqlite:///:memory:")` gives each new connection its own
   *separate* empty database — use `poolclass=StaticPool` when a test
   needs to share state across multiple `Session()`/`TestClient` calls.
   Separately, `with TestClient(app) as c:` triggers the app's startup
   event (`init_db()`), which uses the *real* configured-by-`.env` engine,
   not any test override — a "unit test" was silently touching the real
   production Supabase DB until this was caught (tell-tale sign: the test
   ran noticeably slower than it should have).
5. **Precision-first policy for the labeling pipeline is deliberate, not
   timid**: ambiguous or incomplete data defaults to `is_sponsored=false`
   rather than guessing `true`. A false positive poisons a real GAIL
   training label; a false negative is just absent signal. Don't "fix" a
   low sponsored-count by loosening the regex patterns — that's the wrong
   direction to optimize in for this specific pipeline.

## Exact next steps (in priority order)

1. **Re-check whether Track A has re-scraped Instagram content** (fresh
   `fetched_at` timestamps past their caption-fix commit — still
   2026-08-09 as of this round, still not re-scraped). If yes: run
   `POST /labeling/run?force=true`, re-evaluate the Kohli/Agilitas case
   with real text, update `API_CONTRACTS.md`'s documented decision either
   way.
2. **Re-run `POST /labeling/run` (default mode is fine) periodically** as
   Track A's dataset keeps growing — this is now routine maintenance, not
   a one-off task. Check row counts first (`SELECT COUNT(*) FROM
   youtube_videos/instagram_posts/reddit_posts WHERE is_sponsored IS
   NULL`) to see if it's worth running. Just ran this round: 273 newly-
   landed rows (133 YouTube, 140 Reddit) labeled, still 0 sponsored, all
   695 real content rows now non-null. Did the broader keyword recall scan
   too (sponsor/partner/collab/affiliate/#ad) — no new near-miss pattern,
   all hits fell under already-tested cases.
3. **Check `origin/track-b-ml-core:GRAPH_SCHEMA.md` fresh** for whether
   real `spillover_score`/`sentiment_risk_score` output exists yet — if
   so, Weeks 14-15's "real Fusion Layer" work unblocks.
4. **Check `origin/track-a-data-infra:SCHEMA.md`** for any new
   `reputation_score`-adjacent column before assuming that gap is still
   open — this project's state changes fast, re-verify don't assume.
5. If genuinely idle with schedule slack: start on API hardening (rate
   limiting, more complete input validation) — PROJECT_PLAN.md Section 6
   assigns this to Track C around Weeks 16-17, buildable ahead of schedule
   like Track B did with their regularization terms in Weeks 3-4.
6. **Before ending any future session**: re-run the fresh-checkout
   verification (disposable `git worktree add --detach` off
   `origin/track-c-fusion-backend`, fresh venv, `pip install -r
   requirements.txt`, import + `pytest`) and update this file if state
   changed meaningfully — this is now the established discipline for this
   track, don't skip it.
