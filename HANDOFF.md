# Handoff — Track C (Fusion + Backend)

**⚠️ 2026-08-22 (second round today) — Fusion Layer wiring PAUSED, real
blocker found, decision deferred to the user.** Prompted by P1.6 being
marked "unblocked" (Track B trained on real data, `a4b3bed`) — task was to
wire real `spillover_score` into `/scores`/`/recommendations`, replacing
the flat 0.5 placeholder, distinguishing trained vs. inductive-inferred
values with real (wide) confidence bounds. **Before writing any code,
checked whether an actual loadable model exists — it doesn't.** Read
`ml/gail_model.py`, `ml/training.py`, and the round-3 script
(`scripts/train_holdout_round3.py`) in full, then grepped the whole
`track-b-ml-core` branch for `torch.save`/checkpoints/`.pt`/`.pth`/any
serving or inference entrypoint: **zero hits.** Every training run in
Track B's repo trains fresh in-memory, prints metrics, and discards the
weights — the round-3 LOO-CV script trains **10 separate throwaway models**
(one per held-out fold) purely to estimate generalization error; none of
them is "the" model a serving layer could load. "Track B trained on real
data" is accurate as a **validation/methodology finding**, but there is no
deployable model artifact — that's a different, more consequential fact
than the task's framing assumed.

Surfaced this to the user with two real options before proceeding (rather
than silently picking one, since it's a scope/ownership call, not a coding
one): **(A)** Track C trains a single production model itself, at startup,
using Track B's unmodified `ml/` classes as a library (real inference
ships this round, but Track C ends up running the actual training job,
crossing the Track B/C ownership line functionally, and there's no
versioned checkpoint — it retrains from scratch on every restart); or
**(B)** report the gap and leave `spillover_score` on the honest
placeholder until Track B (or a future round) produces an actual
checkpoint or scoring script Track C can load. **User's call: report
findings and solutions, continue the actual wiring decision/implementation
later — no code changed this round.** `spillover_score` stays the flat 0.5
placeholder for now. Nothing in Tasks 1-4 (real inference wiring,
confidence bounds, fusion-weight documentation, end-to-end verification)
was implemented — this entry exists so the next session doesn't have to
re-discover the missing-checkpoint finding from scratch.

**Read this first, before memory, before re-deriving anything from git log.**
This is the canonical "start here" doc for a fresh session on this track.
Memory (`C:\Users\Sonic\.claude\projects\D--Capstone\memory\`) has the
detailed week-by-week history if you need it, but this file is the
current-state summary — trust it over stale memory entries if they disagree.

Last updated: 2026-08-22, a session prompted directly by the orchestrator's
`CAPSTONE_NEXT_STEPS.md` (repo root on `main`, commit `7d38be8`) —
**read that file first**, it supersedes memory and this file's own history
when they disagree, per its own stated rule. `API_CONTRACTS.md` at repo root
is the living API contract doc — read that too before touching any endpoint
shape.

**This round's headline: force-relabeling at the new scale (Reddit
2,748/YouTube 1,594, both roughly 4x Phase 1H's numbers) surfaced real new
signal on all three platforms — but also a genuine precision failure on
Reddit and a large batch of new computable-pair candidates.** All 2,067 new
Reddit rows and most of the 392 new Instagram / 367 new YouTube rows were
still `is_sponsored IS NULL` (never checked before — Track A's upsert never
touches that column). Force-relabel results: **YouTube 2→3, Instagram
32→59 (before correction), Reddit 0→4 (before correction).**

**⚠️ Manually verified every new hit before accepting it, per this round's
explicit "don't inflate `is_sponsored` on weak signal" instruction — found
and reverted 5 confirmed false positives.** All 4 new Reddit hits and 1 new
Instagram hit matched on `"sponsored by"` / `"in partnership with"`, but
reading the full text showed every one describes a **third-party
organizational relationship** (a cricket club sponsoring a tournament
round, a news article's "in partnership with" byline, a league's commercial
partner, a team's CSR/charity initiative) — not the creator's own paid
promotion. **Reddit's yield was 4/4 false positive; Instagram's one new
`"in partnership with"` hit was also false positive** (a KKR charity post).
Both patterns are structurally risky off Instagram's caption convention —
reverted all 5 to `is_sponsored=false`, same precision-first treatment as
the historical Kohli/Agilitas call. **Final real counts: YouTube 3,
Instagram 58, Reddit 0** — Reddit's real yield is still genuinely zero, now
confirmed rather than assumed; the earlier "4" was an artifact of pattern
mismatch, not real signal. Detection-method breakdown for the 58 Instagram
events: 45 native `has_paid_partnership_label`, 25 `#ad`/`#Ad`/`#AD` hashtag
matches (some overlap with native). No code changed — this was a data-only
correction on confirmed-false rows, not a regex change.

**Task 2 (brand-co-authorship investigation, queued from before): gap is
not measurable given the current schema, no signal added.** There is no
post-level co-author column anywhere in the DB (checked `information_schema`
directly) — the only proxy is matching `creator_related_accounts` handles
against `brands.name`/`instagram_handle`, and only 2 of 19 brand rows even
have an `instagram_handle` populated. That proxy surfaced exactly 3
candidate rows; checking each individually: 1 (oakleymeta↔Kohli) is already
correctly `is_sponsored=true` with `brand_id` set, and the other 2
(duroflexworld, reliancejewels) are **stale `creator_related_accounts`
residue from posts already reattributed away from the creator** (both now
sit at `creator_id=null`, correctly excluded). Zero real unlabeled gap found
with the data available — did not build a new detection signal, since there
was nothing concrete to build against.

**Task 3 — misattribution reconciliation confirmed clean.** The two posts
Track A corrected this round (`kingjames`→nike misattribution,
`keralablasters`→astermedcity misattribution) are both `creator_id: null`,
`is_sponsored=false`, `brand_id: null` in the live DB — neither leaks into
any event/pair count on this side. `/feature-store/edges/collaborations`
reflects **259 creators / 340 raw edges / 170 distinct pairs** cleanly
post-merge (raw `creators` table also confirms 259, exactly one
`%athletics%`-name row — the duplicate is genuinely gone, not just renamed).

**Task 4 — the number that matters most: at least 8 newly-sponsored
creators are already graph-connected, forming real new pair candidates,
not previously part of the known 34-event/1-pair baseline.** Cross-checked
every currently-sponsored creator against `creator_related_accounts`: 14 of
17 distinct sponsored creators (excluding null-`creator_id` rows) are
graph-connected. Of those, **`mrbeast`/`CarryMinati`, `Cristiano Ronaldo`,
`Virat Kohli`, and `Kerala Blasters` were already known/counted** (the
orchestrator's 52-pair figure predates this round's relabel). But **8 names
never seen in any prior Track C round are both newly sponsored (fetched
2026-08-17 through 08-21, i.e. content that was still null before today)
and already resolved into the graph**, including a directly mutually-
connected pair: **Prajakta Koli ↔ Taaruk Raina** (both newly sponsored,
directly connected to each other), plus a dense 4-way cluster **karanjohar
↔ Bhuvan Bam ↔ Pratibha Ranta ↔ Gurfateh Singh Pirzada** (all four mutually
connected, all four newly sponsored) and **Sania Mirza** (connected to
`karanjohar`). This is new signal the orchestrator's 52-pair canonical
count has not yet seen — flagging explicitly rather than burying it in the
aggregate, per this round's instruction.

**§1a / P0.4 note for the orchestrator:** the 52-pair figure (2026-08-21)
was computed before this round's relabel converted a large batch of
previously-null rows to real sponsorship events. **This likely raises the
computable-pair count further** — worth a fresh canonical `pair_count.py`
run before Track B trains, rather than assuming 52 still holds.

**Note:** `PROJECT_PLAN.md` Section 1's breadth-over-depth revision (noted
several rounds ago as unmerged into this branch) is superseded by
`CAPSTONE_NEXT_STEPS.md`, which is now the actively-maintained cross-track
source of truth — check that file's own "last verified" date each session
rather than assuming this note is current.

## Current state (one paragraph)

A FastAPI + SQLModel backend (`backend/`) is live and connected to the real
shared Supabase Postgres instance (259 real creators, 6,153 real content rows
as of last check — 1,594 YouTube / 1,811 Instagram / 2,748 Reddit, all three
platforms grown sharply since Phase 1H via Track A's continued discovery
work — Reddit alone roughly 4x). Full API surface exists and is tested:
`/health`, `/recommendations` (real
budget/region/demographic/product_category/platform_preference filtering,
not a stub), `/ingestion/*` (8 endpoints, secondary/manual write path —
**Track A's real orchestrator writes directly to Postgres and bypasses
these entirely**, see gotcha #2 below), `/scores/*` (Fusion Layer formula,
weights still placeholder pending real GAIL/Temporal output), `/alerts`
(with a `propagated_from_creator_id` field pre-added for Sentiment
Propagation), `/feature-store/*` (real transformation pipeline Track B
actively consumes — creators [259], collaboration edges [340 directed =
**170 distinct pairs**, real, matches the orchestrator's own count exactly],
co-occurrence edges [0, expected-empty], sponsorship edges [**16**,
reconciles exactly against the raw DB]), `/labeling/run` (real disclosure-tag
`is_sponsored` classifier, reading Instagram's native
`has_paid_partnership_label`, precision-validated against real scraped
text). CORS is configured and confirmed working by Track D in a real
browser. Basic auth (`API_KEY` env var) exists, off by default. 49 tests
pass (`backend/tests/`, `pytest`). Migrations for Track C's own tables live
in `backend/migrations/` with a README explaining why (see gotcha #1).
Working tree is clean and fully pushed as of this handoff.

**Sponsorship events: 61 total (58 Instagram, 3 YouTube, 0 Reddit)** — up
from 34, after this round's force-relabel at the new ~4x scale and manual
correction of 5 confirmed false positives (4 Reddit, 1 Instagram — see
headline above). Instagram's 26 new real events came from previously-null
content Track A scraped since Phase 1H. YouTube gained a genuine 3rd event
(`Prajakta Koli`, `#ad`, lip-balm review — plain hashtag disclosure, not the
native-label path since that's Instagram-only). `keralablasters`'s 2
YouTube events (from Phase 1H) are unchanged. **`keralablasters` is now
graph-connected** (via `mumbaicityfc`/`chennaiyinfc` resolved edges — this
connection appeared between Phase 1H and now via Track A's bulk promotion
work, not from anything done this round; already reflected in the
orchestrator's P0.4 "Kerala Blasters↔Mumbai City FC" pair). `/feature-store/
edges/sponsorships` holds at **16** (up from 10) — reconciles exactly
against `is_sponsored=true AND brand_id IS NOT NULL AND creator_id IS NOT
NULL` (2 Instagram rows have `brand_id` but `creator_id=null` — the
already-corrected misattributed posts, correctly excluded). 45 of 61 events
still lack `brand_id`, including the milestone `mrbeast` post — routine lag
behind Track A's brand extraction, not a regression.

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
  close.** 61 real `is_sponsored=true` posts exist, only 16 have a
  `brand_id`. Includes the `mrbeast`/Old Navy milestone post — worth
  checking first next round since it's the highest-value single post to
  get a `brand_id`, not just routine lag.
- **8 newly-sponsored, already graph-connected creators found this
  round — highest priority for next round's pair recount.** Named
  explicitly in this round's headline above: `Prajakta Koli` ↔
  `Taaruk Raina` (direct mutual edge, both newly sponsored),
  `karanjohar`/`Bhuvan Bam`/`Pratibha Ranta`/`Gurfateh Singh Pirzada`
  (mutually connected 4-way cluster, all newly sponsored), `Sania Mirza`
  (connected to `karanjohar`). None of these were part of the orchestrator's
  52-pair count (computed 2026-08-21, before this round's relabel). Flag
  for the orchestrator to re-run `pair_count.py` before Track B trains.
- **`keralablasters` — no longer isolated, now graph-connected (via
  `mumbaicityfc`/`chennaiyinfc`).** Already reflected in the orchestrator's
  P0.4 "Kerala Blasters↔Mumbai City FC" pair — this connection appeared
  between Phase 1H and now via Track A's bulk promotion, not from this
  round's work. Its 2 YouTube sponsorship events (unchanged since Phase 1H)
  are therefore already a real computable pair, just not one this round
  discovered.
- **Reddit's disclosure-detection yield is genuinely still zero — now
  confirmed at ~4x scale, not just assumed.** This round's force-relabel
  found 4 candidate hits, but manual review showed all 4 are false
  positives (third-party sponsorship mentions in news/sports community
  text, not creator disclosure) — reverted to `is_sponsored=false`. Do not
  re-run Reddit through the same "sponsored by"/"in partnership with"
  patterns expecting different results without first tightening them
  (e.g. requiring the phrase adjacent to the post author's own voice) —
  that's a future precision-tuning task, not yet built.
- **~~Collaboration graph sparsity~~ — RETIRED, do not cite "10 pairs" or
  "2.4%" again.** Now 170 distinct pairs (873 rows) after bulk promotion of
  the sheet backlog and continued growth. If any future doc/memory still
  says 10 or 161, it's stale — re-verify against the live DB, don't trust
  the cached figure.
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

1. **Flag the 8 new sponsored+connected creators to the orchestrator for a
   fresh `pair_count.py` run before Track B trains.** Named above:
   `Prajakta Koli`/`Taaruk Raina` (direct pair), the `karanjohar` 4-way
   cluster, `Sania Mirza`. This is real signal the 52-pair figure
   (2026-08-21) predates.
2. **Re-check `brand_id` on `Db5rzczsSV5` (mrbeast/Old Navy) specifically,
   not just the aggregate.** Still NULL as of this round. Once Track A
   extracts "Old Navy" into `brands` and backfills this post, it becomes
   visible to `/feature-store/edges/sponsorships` too.
3. **Re-run `POST /labeling/run?force=true` periodically** as Track A's
   dataset keeps growing — routine maintenance, now genuinely multi-
   platform and precision-checked. This round: 34 → 61 real sponsorship
   events after reverting 5 confirmed false positives (see headline above).
   Manually spot-check any new hit that uses `"sponsored by"` or
   `"in partnership with"` before trusting it — both patterns have now
   produced confirmed false positives on Reddit (4/4) and Instagram (1/1),
   so treat future hits on those two patterns with suspicion until a
   precision fix is designed (not built yet — flagged, not actioned).
4. **Check `origin/track-b-ml-core:GRAPH_SCHEMA.md` fresh** for whether
   Track B has started training on the current pair set — if so, the "real
   Fusion Layer" work unblocks.
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
