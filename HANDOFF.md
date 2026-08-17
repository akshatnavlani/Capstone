# Handoff — Track C (Fusion + Backend)

**Read this first, before memory, before re-deriving anything from git log.**
This is the canonical "start here" doc for a fresh session on this track.
Memory (`C:\Users\Sonic\.claude\projects\D--Capstone\memory\`) has the
detailed week-by-week history if you need it, but this file is the
current-state summary — trust it over stale memory entries if they disagree.

Last updated: 2026-08-18, a session prompted directly by the orchestrator's
`CAPSTONE_NEXT_STEPS.md` (repo root on `main`, commit `dbc79c5`) —
**read that file first**, it supersedes memory and this file's own history
when they disagree, per its own stated rule. `API_CONTRACTS.md` at repo root
is the living API contract doc — read that too before touching any endpoint
shape.

**This round's headline: the labeler was already checking YouTube and
Reddit — it wasn't Instagram-only code — and running it at real scale (YT
grew ~10→39 covered creators / 1,227 videos since last check) found
YouTube's first-ever 2 real sponsorship events.** Verified before assuming
anything: `app/routers/labeling.py` calls the same `detect_sponsorship()`
against `youtube_videos.title/description` and `reddit_posts.title/body` as
it does against Instagram captions — confirmed by reading the code, not
inferred from "0 events" being ambiguous. The patterns themselves
(`#ad`, "sponsored by", "in partnership with", "brought to you by", etc.)
are generic disclosure conventions, not Instagram-specific. **The "32
events, Instagram-only" result from every prior round really was 0
real YouTube/Reddit signal at old scale, not an unbuilt capability** — this
round's force-relabel against the grown dataset is what changed that.

Force-relabeled all three platforms (1,227 YouTube / 1,419 Instagram / 681
Reddit): **YouTube 0 → 2** (both on `keralablasters`, via "brought to you
by" in the description — a team account, not previously graph-checked),
**Reddit stayed 0**, Instagram unchanged at 32 (no new Instagram rows since
last round). Checked immediately whether either new YouTube event lands on
an already-graph-connected creator, per this round's explicit ask:
**`keralablasters` has zero rows anywhere in `creator_related_accounts`**
(not even an unresolved/dangling one) — confirmed both via the live
`/feature-store/edges/collaborations` endpoint and a direct raw-table
query. **No new computable-pair candidate this round** — real new signal,
but currently isolated in the graph. Sponsorship-edges endpoint held at
**10** (neither new event has `brand_id`), reconciling exactly. See
`API_CONTRACTS.md`'s "Phase 1H" section for full detail.

**§1a batch-readiness checklist, updated this round**: "Track C has
re-run its labeler across the full YouTube/Reddit content pool" — **DONE**,
mark it checked in the shared doc. It surfaced real (if still isolated)
signal, so the "all 32 events are Instagram-only" framing in §1a is now
stale too — flag that for the orchestrator alongside the checkbox.
Computable training pairs remain at the prior count (this round found no
new one) — still well below the 20-pair sufficiency bar.

**Note:** `PROJECT_PLAN.md` Section 1's breadth-over-depth revision (noted
last round as unmerged into this branch) is superseded by
`CAPSTONE_NEXT_STEPS.md`, which is now the actively-maintained cross-track
source of truth — check that file's own "last verified" date each session
rather than assuming this note is current.

## Current state (one paragraph)

A FastAPI + SQLModel backend (`backend/`) is live and connected to the real
shared Supabase Postgres instance (259 real creators, 3,327 real content rows
as of last check — 1,227 YouTube / 1,419 Instagram / 681 Reddit, YouTube and
Reddit grown sharply via Track A's Phase 1G/1H discovery work — YouTube
coverage 10→39 creators, Reddit content 555→681 rows). Full API
surface exists and is tested: `/health`, `/recommendations` (real
budget/region/demographic/product_category/platform_preference filtering,
not a stub), `/ingestion/*` (8 endpoints, secondary/manual write path —
**Track A's real orchestrator writes directly to Postgres and bypasses
these entirely**, see gotcha #2 below), `/scores/*` (Fusion Layer formula,
weights still placeholder pending real GAIL/Temporal output), `/alerts`
(with a `propagated_from_creator_id` field pre-added for Sentiment
Propagation), `/feature-store/*` (real transformation pipeline Track B
actively consumes — creators [259], collaboration edges [322 directed =
**161 distinct pairs**, real, up from 10 after bulk promotion], co-occurrence
edges [0, expected-empty], sponsorship edges [**10**, reconciles exactly
against the raw DB]), `/labeling/run` (real disclosure-tag `is_sponsored`
classifier, reading Instagram's native `has_paid_partnership_label`,
precision-validated against real scraped text). CORS is configured and
confirmed working by Track D in a real browser. Basic auth (`API_KEY` env
var) exists, off by default. 49 tests pass (`backend/tests/`, `pytest`).
Migrations for Track C's own tables live in `backend/migrations/` with a
README explaining why (see gotcha #1). Working tree is clean and fully
pushed as of this handoff.

**Sponsorship events: 34 total (32 Instagram, 2 YouTube, 0 Reddit)** —
YouTube's first-ever real signal, found this round by force-relabeling at
the new 1,227-video scale (was checked at only ~315 videos / ~10 covered
creators before). Both YouTube events are on `keralablasters` (a team
account), caught via "brought to you by" in the video description — plain
caption-regex detection, no native-signal equivalent exists for YouTube.
Checked immediately whether `keralablasters` is graph-connected: **it has
zero rows anywhere in `creator_related_accounts`**, not even unresolved —
confirmed via both the live endpoint and a raw-table query. **No new
computable-pair candidate this round.** `/feature-store/edges/sponsorships`
holds at **10** — neither YouTube event has `brand_id`, and it still
reconciles exactly against the raw `is_sponsored=true AND brand_id IS NOT
NULL` count. 24 of 34 events total still lack `brand_id`, including the
milestone `mrbeast` post below — routine lag behind Track A's brand
extraction, not a regression.

**The project's first fully-computable GAIL training pair is now real —
confirmed, not assumed.** `mrbeast`'s `Db5rzczsSV5` (`#oldnavypartner`,
native-label-only detection, posted 2026-08-12) is `is_sponsored=true`
after this round's relabel, `mrbeast` is graph-connected to `CarryMinati`
via a real resolved collaboration edge (verified live, weight 2.0 both
directions), and CarryMinati has dated posts on both sides of the event
(orchestrator-verified, not re-checked here). `brand_id` is NULL on this
post — no "Old Navy" brand row exists yet and brand extraction is entirely
Track A's code, not Track C's (confirmed via grep, no such logic exists in
this backend) — so this event won't appear in
`/feature-store/edges/sponsorships` until Track A extracts it, but that
does **not** block the computable-pair claim itself.

**⚠️ RETIRED finding, corrected this round: the collaboration graph is NOT
structurally sparse.** Last round's "10 pairs, 2.4% resolve rate, confirmed
structural property" claim (both here and in memory) was a real snapshot of
an *unpromoted* graph, mistaken for a ceiling. The user reviewed the full
258-candidate sheet backlog and bulk-promoted them; **zero new scraping**
converted previously-dangling `creator_related_accounts` rows into real
pairs. Current: **161 distinct pairs** (668 rows total, 322 resolved rows
before dedup), independently reproduced this round via the same
handle-resolution logic used every prior round, matching the orchestrator's
figure exactly. The `/feature-store/edges/collaborations` endpoint needed
no code change — it recomputes from live DB state on every call, so it
already reflected the new reality the moment promotion landed. **Still
report 322 as 161 relationships, not 322** — 2 directed edges per pair,
unchanged convention.

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
  close.** 34 real `is_sponsored=true` posts exist (32 Instagram + 2
  YouTube, new this round), only 10 have a `brand_id`. Includes the
  `mrbeast`/Old Navy milestone post — worth checking first next round since
  it's the highest-value single post to get a brand_id, not just routine
  lag.
- **`keralablasters`'s 2 new YouTube sponsorship events are real but
  isolated — worth watching, not acting on.** Zero graph connections at
  all (not even unresolved). If Track A's discovery work ever links this
  team account to a player creator via `creator_related_accounts`, it
  becomes an instant new computable-pair candidate — re-check
  `/feature-store/edges/collaborations` for this creator_id
  (`462094a7-a09d-43e5-b457-bb06c9de2229`) next round rather than assuming
  it's still isolated.
- **~~Collaboration graph sparsity~~ — RETIRED, do not cite "10 pairs" or
  "2.4%" again.** Now 161 distinct pairs (668 rows) after bulk promotion of
  the sheet backlog. If any future doc/memory still says 10, it's stale —
  re-verify against the live DB, don't trust the cached figure.
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

1. **Re-check `brand_id` on `Db5rzczsSV5` (mrbeast/Old Navy) specifically,
   not just the aggregate.** This is the project's first computable
   training pair — once Track A extracts "Old Navy" into `brands` and
   backfills this post, it becomes visible to
   `/feature-store/edges/sponsorships` too. Check this post by name before
   trusting an aggregate `brand_id` count next round.
2. **Re-check whether `keralablasters` (YouTube's first 2 sponsorship
   events) has gained any collaboration-graph connection.** Currently zero
   rows in `creator_related_accounts` at all. If Track A's YouTube/roster
   discovery work ever connects it to a player creator, that's an instant
   new computable-pair candidate — worth a quick check even outside a full
   relabel round.
3. **Re-run `POST /labeling/run?force=true` periodically** as Track A's
   dataset keeps growing — routine maintenance, now genuinely multi-
   platform. Just ran this round: 18 → 34 real sponsorship events (32
   Instagram unchanged + 2 new YouTube). Didn't re-run the broader recall
   scan this round (no code changed) — worth re-running once YouTube/Reddit
   volume grows further, since this round's YouTube hit came from a
   platform-agnostic phrase ("brought to you by"), suggesting other
   platform-specific disclosure conventions may still be unaudited.
4. **Check `origin/track-b-ml-core:GRAPH_SCHEMA.md` fresh** for whether
   Track B has started training on the confirmed-real mrbeast/CarryMinati
   computable pair — if so, the "real Fusion Layer" work unblocks.
5. **Check `origin/track-a-data-infra:SCHEMA.md`** for any new
   `reputation_score`-adjacent column before assuming that gap is still
   open — this project's state changes fast, re-verify don't assume.
6. If genuinely idle with schedule slack: start on API hardening (rate
   limiting, more complete input validation) — `CAPSTONE_NEXT_STEPS.md`
   Phase 5 assigns this to Track C (with D), buildable ahead of schedule
   like Track B did with their regularization terms early on.
7. **Before ending any future session**: re-run the fresh-checkout
   verification (disposable `git worktree add --detach` off
   `origin/track-c-fusion-backend`, fresh venv, `pip install -r
   requirements.txt`, import + `pytest`) and update this file if state
   changed meaningfully — this is now the established discipline for this
   track, don't skip it.
