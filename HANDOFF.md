# Handoff — Track C (Fusion + Backend)

**Read this first, before memory, before re-deriving anything from git log.**
This is the canonical "start here" doc for a fresh session on this track.
Memory (`C:\Users\Sonic\.claude\projects\D--Capstone\memory\`) has the
detailed week-by-week history if you need it, but this file is the
current-state summary — trust it over stale memory entries if they disagree.

Last updated: 2026-08-15, a session prompted directly by the orchestrator's
`CAPSTONE_NEXT_STEPS.md` (repo root on `main`, commit `aef6401`, Phase 1F) —
**read that file first**, it supersedes memory and this file's own history
when they disagree, per its own stated rule. `API_CONTRACTS.md` at repo root
is the living API contract doc — read that too before touching any endpoint
shape.

**This round: routine re-verification, no code changes.** Force-relabeled
against Track A's now-1,092-row Instagram table (267 new posts since last
round): sponsorship events **11 → 18**, 10 of 18 now have `brand_id` (was
9 of 11), `/feature-store/edges/sponsorships` moved **9 → 10**, exactly
matching the raw `is_sponsored=true AND brand_id IS NOT NULL` count — no
reconciliation gap. Also independently reproduced Track A's collaboration-
edge claim (505 rows / 15 resolved / **10 distinct pairs**) directly from
the live DB and confirmed the API emits 2 directed edges per pair (20
total), matching Track B's non-`ToUndirected()` graph convention. See
`API_CONTRACTS.md`'s "Phase 1F re-verification" section for full detail.
Also applied the `.env` DATABASE_URL pooler fix from
`CAPSTONE_NEXT_STEPS.md` §3.4b — this worktree's `.env` still had the old
IPv6-only direct host.

**Note:** `PROJECT_PLAN.md` Section 1's breadth-over-depth revision (noted
last round as unmerged into this branch) is superseded by
`CAPSTONE_NEXT_STEPS.md`, which is now the actively-maintained cross-track
source of truth — check that file's own "last verified" date each session
rather than assuming this note is current.

## Current state (one paragraph)

A FastAPI + SQLModel backend (`backend/`) is live and connected to the real
shared Supabase Postgres instance (63 real creators, 1,826 real content rows
as of last check — 299 YouTube / 1,092 Instagram / 435 Reddit, Instagram
grown sharply via Track A's Phase 1F scanning). Full API surface exists and
is tested: `/health`, `/recommendations` (real
budget/region/demographic/product_category/platform_preference filtering,
not a stub), `/ingestion/*` (8 endpoints, secondary/manual write path —
**Track A's real orchestrator writes directly to Postgres and bypasses
these entirely**, see gotcha #2 below), `/scores/*` (Fusion Layer formula,
weights still placeholder pending real GAIL/Temporal output), `/alerts`
(with a `propagated_from_creator_id` field pre-added for Sentiment
Propagation), `/feature-store/*` (real transformation pipeline Track B
actively consumes — creators [63], collaboration edges [20 directed = 10
distinct pairs, real], co-occurrence edges [0, expected-empty, structural
per Track A's Phase 1E finding], sponsorship edges [**10**, reconciles
exactly against the raw DB]), `/labeling/run` (real disclosure-tag
`is_sponsored` classifier, reading Instagram's native
`has_paid_partnership_label`, precision-validated against real scraped
text). CORS is configured and confirmed working by Track D in a real
browser. Basic auth (`API_KEY` env var) exists, off by default. 49 tests
pass (`backend/tests/`, `pytest`). Migrations for Track C's own tables
live in `backend/migrations/` with a README explaining why (see gotcha #1).
Working tree is clean and fully pushed as of this handoff.

**Sponsorship events: 18, all Instagram, 0 on YouTube/Reddit** (up from 11
last round, after force-relabeling the 267 Instagram posts Track A scanned
in Phase 1F). 13 of 18 caught by caption-text regex, 5 caught *only* by the
native `has_paid_partnership_label` signal. `/feature-store/edges/
sponsorships` returns **10** (was 1, then 9 once Track A's brand-extraction
fix landed on the original 11 — this round found it's still only 1 of the
**7 newly-surfaced** events, so 8 of 18 total events still lack `brand_id`).
This is expected lag, not a regression — flag again next round if it hasn't
moved once Track A re-runs brand extraction.

**Collaboration graph is confirmed genuinely sparse — a structural property
of the curated creator set, not a coverage or extraction gap.** Track A
tested this directly: scanning grew from 24→31 of 63 creators covered with
zero new resolved edges (only 2.2% of observed co-authors are creators in
our own set). Independently reproduced from the live DB this round: 505
`creator_related_accounts` rows → 15 resolved → **10 distinct pairs**
(5 of the 15 are reciprocal directions of a pair already counted). The
`/feature-store/edges/collaborations` endpoint correctly returns 20 edges
(2 directed edges per pair, matching Track B's non-`ToUndirected()` graph
convention) — **Track B: 20 is not 20 relationships, it's 10.** Don't
expect this number to grow from more Instagram coverage; the lever is the
"bridge queue" (handles referenced by 2+ creators) per Track A's
HANDOFF.md, which is a curation decision, not something to build around
here.

**What's explicitly still placeholder/not real:** `spillover_score` /
`sentiment_risk_score` / `creator_feature_score` in the fusion formula are
always caller-supplied or a flat 0.5 default — no real GAIL or Temporal
branch output exists yet to wire in (that's Track B's Weeks 11-15+ work).
Fusion weights are uncalibrated defaults. `reputation_score` has no real
source anywhere in the system.

## Open items

- **Kohli/Agilitas `is_sponsored` edge case — CLOSED 2026-08-14.**
  Instagram has since been re-scraped (all 5 related posts now full-length,
  `fetched_at` 2026-08-11/12); re-examined with `force=true` against real
  complete text. Call confirmed unchanged (`is_sponsored=false` — genuine
  co-founder relationship, no disclosure tag, `has_paid_partnership_label`
  also `False` on all 5). See `API_CONTRACTS.md`'s Kohli/Agilitas section
  for the closed writeup. No further action needed on this specific case.
- **Sponsorship edges lag sponsorship events — ongoing, Track A's to
  close.** 18 real `is_sponsored=true` posts exist, 10 have a `brand_id`
  (was 9/11 last round — Track A's fix caught up on the original 11 but
  not yet on the 7 newly-surfaced events). Re-check next session; this is
  routine lag from Instagram scanning outpacing brand extraction, not a
  new bug.
- **Collaboration graph sparsity — confirmed structural, not a bug, don't
  try to fix it here.** 10 distinct resolved pairs across 63 creators.
  Track A tested and disproved the "more coverage → more edges" hypothesis
  directly (Phase 1F). The only real lever is the sheet's bridge-queue
  curation, which is the user's call, not Track C's to build around.
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
6. **A new column another track adds to a shared table does not
   automatically reach Track C's code.** Track A added
   `has_paid_partnership_label` to the live `instagram_posts` table, but it
   sat there unread for at least one full round — `InstagramPost` (the
   SQLModel class) simply had no field for it, so the ORM never selected
   it, and `POST /labeling/run` never looked at it. Found only by directly
   diffing `information_schema.columns` against `app/models.py`, not by
   trusting either side's docs. When a cross-track doc says a new column
   exists, verify the *consuming* code reads it, not just that it's
   present in the DB.

## Exact next steps (in priority order)

1. **Re-check `brand_id` population on the 8 sponsorship posts still
   missing it.** This round found 10 of 18 `is_sponsored=true` Instagram
   posts have a `brand_id`, capping `/feature-store/edges/sponsorships` at
   10 even though 18 real events exist. That's Track A's brand-extraction
   step, not Track C's — check whether it's caught up before assuming this
   is still a gap.
2. **Re-run `POST /labeling/run?force=true` periodically** as Track A's
   dataset keeps growing — this is now routine maintenance. Just ran this
   round: 11 → 18 real sponsorship events (all Instagram, from 267 newly-
   scraped posts), 13 of 18 via caption regex, 5 via
   `has_paid_partnership_label` only. Didn't re-run the broader recall
   scan this round (no code changed, prior scan still holds) — worth
   re-running once the dataset grows meaningfully again.
3. **Check `origin/track-b-ml-core:GRAPH_SCHEMA.md` fresh** for whether
   real `spillover_score`/`sentiment_risk_score` output exists yet, and
   whether Track B has started training against the now-real 11-event
   `creator_sponsorship_events` view — if so, the "real Fusion Layer" work
   unblocks.
4. **Check `origin/track-a-data-infra:SCHEMA.md`** for any new
   `reputation_score`-adjacent column before assuming that gap is still
   open — this project's state changes fast, re-verify don't assume.
5. If genuinely idle with schedule slack: start on API hardening (rate
   limiting, more complete input validation) — `CAPSTONE_NEXT_STEPS.md`
   Phase 5 assigns this to Track C (with D), buildable ahead of schedule
   like Track B did with their regularization terms early on.
6. **Before ending any future session**: re-run the fresh-checkout
   verification (disposable `git worktree add --detach` off
   `origin/track-c-fusion-backend`, fresh venv, `pip install -r
   requirements.txt`, import + `pytest`) and update this file if state
   changed meaningfully — this is now the established discipline for this
   track, don't skip it.
