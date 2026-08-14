# Handoff — Track C (Fusion + Backend)

**Read this first, before memory, before re-deriving anything from git log.**
This is the canonical "start here" doc for a fresh session on this track.
Memory (`C:\Users\Sonic\.claude\projects\D--Capstone\memory\`) has the
detailed week-by-week history if you need it, but this file is the
current-state summary — trust it over stale memory entries if they disagree.

Last updated: 2026-08-14, a session prompted directly by the orchestrator's
`CAPSTONE_NEXT_STEPS.md` (repo root on `main`, commit `d98a068`) — **read
that file first**, it supersedes memory and this file's own history when
they disagree, per its own stated rule. `API_CONTRACTS.md` at repo root is
the living API contract doc — read that too before touching any endpoint
shape.

**This round's headline: the project's central open question is answered —
real sponsorship events now exist (0 → 11, all Instagram).** See
`API_CONTRACTS.md`'s "Post-Phase-1D update summary" for full detail. Short
version: `has_paid_partnership_label` (Track A's new schema addition) was
never wired into the labeler — fixed this round — and the caption-
truncation fix let 9 more events surface via the existing `#ad` regex.
Sponsorship *edges* (which need `brand_id`) lag badly behind events (1 of
11), a new Track-A-owned gap — flag this to the orchestrator/Track A.

**Note:** `PROJECT_PLAN.md` Section 1's breadth-over-depth revision (noted
last round as unmerged into this branch) is superseded by
`CAPSTONE_NEXT_STEPS.md`, which is now the actively-maintained cross-track
source of truth — check that file's own "last verified" date each session
rather than assuming this note is current.

## Current state (one paragraph)

A FastAPI + SQLModel backend (`backend/`) is live and connected to the real
shared Supabase Postgres instance (56 real creators, 1,135 real content rows
as of last check — 299 YouTube / 401 Instagram / 435 Reddit, grown sharply
via Track A's Phase 1D promote-to-DB + background collection). Full API
surface exists and is tested: `/health`, `/recommendations` (real
budget/region/demographic/product_category/platform_preference filtering,
not a stub), `/ingestion/*` (8 endpoints, secondary/manual write path —
**Track A's real orchestrator writes directly to Postgres and bypasses
these entirely**, see gotcha #2 below), `/scores/*` (Fusion Layer formula,
weights still placeholder pending real GAIL/Temporal output), `/alerts`
(with a `propagated_from_creator_id` field pre-added for Sentiment
Propagation), `/feature-store/*` (real transformation pipeline Track B
actively consumes — creators [56], collaboration edges [4, real],
co-occurrence edges [0, expected-empty], sponsorship edges [**1** — see
below, this is now the binding gap]), `/labeling/run` (real disclosure-tag
`is_sponsored` classifier, now also reading Instagram's native
`has_paid_partnership_label`, precision-validated against real scraped
text). CORS is configured and confirmed working by Track D in a real
browser. Basic auth (`API_KEY` env var) exists, off by default. 49 tests
pass (`backend/tests/`, `pytest`). Migrations for Track C's own tables
live in `backend/migrations/` with a README explaining why (see gotcha #1).
Working tree is clean and fully pushed as of this handoff.

**First real sponsorship events exist: 11, all Instagram, 0 on
YouTube/Reddit.** But sponsorship *edges* (what Track B's
`/feature-store/edges/sponsorships` actually returns) are stuck at **1**,
because `build_sponsorship_edges()` requires `brand_id IS NOT NULL` and
only 1 of the 11 newly-labeled posts has one — Track A's brand-extraction
step hasn't caught up to this round's labeling yet. This is now the real
bottleneck between Track C's work and Track B's first real training pair,
not disclosure detection.

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
- **Sponsorship edges lag sponsorship events — new gap, Track A's to
  close.** 11 real `is_sponsored=true` posts exist but only 1 has a
  `brand_id`, so `/feature-store/edges/sponsorships` returns 1, not 11.
  Re-check `brand_id` population on the other 10 next session — if Track
  A's brand extraction has caught up, no Track C action needed; if not,
  this is worth surfacing to the orchestrator again.
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

1. **Re-check `brand_id` population on the 11 real sponsorship posts.**
   This round found only 1 of 11 `is_sponsored=true` Instagram posts has a
   `brand_id`, capping `/feature-store/edges/sponsorships` at 1 real edge
   even though 11 real events exist. That's Track A's brand-extraction
   step, not Track C's — check whether it's caught up before assuming this
   is still a gap.
2. **Re-run `POST /labeling/run?force=true` periodically** as Track A's
   dataset keeps growing and existing captions keep getting corrected —
   this is now routine maintenance. Just ran this round: 0 → 11 real
   sponsorship events (all Instagram), incorporating the new
   `has_paid_partnership_label` signal (2 of 11 caught only by that
   signal). Did the broader keyword recall scan too — no new near-miss
   pattern beyond two YouTube videos that turned out to be explicit
   *non*-sponsorship disclosures (correctly excluded).
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
