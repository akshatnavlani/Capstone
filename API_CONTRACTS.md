# API Contracts — Fusion + Backend (Track C)

Owner: Track C (Fusion+Backend). Updated whenever the contract changes — treat
edits to this file as high-signal for Tracks A/B/D, since there's no live
channel between sessions, only git.

**Status as of 2026-08-26 (Review 1 close — P1.6 wired, `65ec502`):** all endpoints below are live
(FastAPI + SQLModel, `backend/`). Full OpenAPI/Swagger UI is auto-generated at
`/docs` when the server is running (`GET /openapi.json` for the raw spec).

Base URL (local dev): `http://127.0.0.1:8000`. Basic auth now exists — see
the **Auth** section below — off by default, opt-in via `API_KEY`. CORS is
now configured — see the incident below before assuming any prior "verified
end-to-end" claim covered real browser behavior.

## ⚠️ Incident (2026-08-10): no CORS middleware existed at all, since Weeks 1-2

Found by Track D's first real browser test of the product. **Every prior
"verified end-to-end" check across every track (mine included) used curl,
which does not enforce or even send `Origin`/CORS the way a real browser
does** — so this was invisible for 8 weeks despite blocking all real
browser use of the API. Fixed by adding `CORSMiddleware` in `main.py`,
allowing `http://localhost:3000`/`http://127.0.0.1:3000` (Track D's `next
dev` origins) by default — extend via `CORS_ALLOW_ORIGINS` (comma-separated)
in `.env` once a deployed frontend origin exists. `allow_credentials=False`
since auth here is an explicit `X-API-Key` header, not a cookie.

Verified server-side via curl (checking the actual `Access-Control-Allow-*`
response headers, which is what determines whether a real browser accepts
the response): allowed origin (`http://localhost:3000`) gets
`access-control-allow-origin` back on both simple requests and preflight
`OPTIONS`; a disallowed origin (`http://evil.example.com`) does not,
confirming the allowlist is actually enforced, not a wildcard. Checked
uniformly across `/health`, `/recommendations`, `POST /ingestion/creators`,
`POST /alerts`, and `GET /alerts`.

**CONFIRMED by Track D in a real browser** (first non-curl verification
this project has had) — the fix works. Closed.

## Phase 1I (2026-08-22) — Reddit precision failure found and corrected, 8 new computable-pair candidates found

Prompted by the orchestrator's `CAPSTONE_NEXT_STEPS.md` commit `7d38be8`:
Reddit had grown to 2,748 posts (from 681), YouTube to 1,594 videos (from
1,227), a duplicate "Athletics" creator was merged (260→259), and two posts
were corrected from misattribution (`kingjames`→nike, `keralablasters`→
astermedcity). Four tasks: re-run the multi-platform labeler at the new
scale; investigate the queued brand-co-authorship gap; reconcile against
Track A's corrections; flag any new graph-connected sponsored creator.

**Task 1 — force-relabel at ~4x scale.** All three platforms' `is_sponsored
IS NULL` backlog (392 Instagram / 367 YouTube / 2,067 Reddit rows — content
scraped since Phase 1H, never checked) was processed via
`POST /labeling/run?force=true`. Raw results: YouTube 2→3, Instagram
32→59, **Reddit 0→4** — Reddit's first-ever raw hits.

**⚠️ Manually verified every new hit before accepting any of them, and
found a real precision failure.** Read the full text (not just the regex
match) for all 4 new Reddit hits and the 1 new Instagram
`"in partnership with"` hit:

| Post | Platform | Pattern matched | What it actually is |
|---|---|---|---|
| `1cgr2bd` | Reddit | "sponsored by" | Cricket-forum post: "*This round is sponsored by Surrey Cricket Club*" — a tournament-round sponsor, not the poster's own paid disclosure |
| `1nf3x1g` | Reddit | "in partnership with" | News article on auto-rickshaw harassment — a journalistic byline convention, no relation to the linked creators at all |
| `1tctfzh` | Reddit | "in partnership with" | League-launch article: "*developed in partnership with the Sports Asian Network*" — describes a league's commercial partner, not the linked creator's disclosure |
| `1tzx6d5` | Reddit | "sponsored by" | IPL season-awards community thread — no genuine disclosure context |
| `DbfCc7HAMBh` | Instagram | "In partnership with" | KKR team account CSR post: "*In partnership with the Meer Foundation... Shahoshi Rani initiative*" — a charity partnership, not a paid brand promotion |

**All 5 are false positives, all found via the same two patterns**
(`"sponsored by"`, `"in partnership with"`) — genuine on Instagram's caption
convention where they usually accompany a hashtag/native label too, but
these two patterns describe **third-party organizational relationships**
in Reddit's community/news register and in team CSR copy, not the
creator's own commercial disclosure. Reverted all 5 to
`is_sponsored=false, sponsorship_raw_matches=null` — same precision-first
treatment as the Kohli/Agilitas call, no code changed (data-only
correction on individually-verified false positives).

**Final, corrected counts: YouTube 3, Instagram 58, Reddit 0.** Reddit's
real yield is confirmed genuinely zero at 4x scale, not assumed — this is a
stronger result than "0 hits," since it rules out the two riskiest patterns
specifically rather than leaving them untested. YouTube's 3rd event:
`Prajakta Koli`, `SW_Oj3UzZ40`, `#ad` on a lip-balm review — clean,
unambiguous hashtag disclosure. Detection-method breakdown across the 58
real Instagram events: 45 native `has_paid_partnership_label`, 25
`#ad`/`#Ad`/`#AD` (some overlap with native), 0 remaining
"sponsored by"/"in partnership with" hits after the correction.

**Task 2 — brand-co-authorship investigation: no real gap found, no
detection signal added.** Checked `information_schema.columns` directly —
there is no post-level co-author field on `instagram_posts`,
`youtube_videos`, or `reddit_posts`; the only queryable co-author proxy is
`creator_related_accounts` (creator-level, not post-level) cross-referenced
against `brands.instagram_handle`/`brands.name`. Only 2 of 19 brand rows
have an `instagram_handle` populated, so this proxy is structurally narrow.
It surfaced exactly 3 candidate rows (`duroflexworld`, `oakleymeta` on
Virat Kohli; `reliancejewels` on Pratibha Ranta). Checked each: `oakleymeta`
is already `is_sponsored=true` with `brand_id` set (no gap); `duroflexworld`
and `reliancejewels` are **stale `creator_related_accounts` residue** from
posts already reattributed away from the creator to the brand itself
(`creator_id=null`) in an earlier round — not a live gap. **Conclusion: the
brand-co-authorship gap is not measurable with the current schema and
appears to be zero among what little can be checked. Did not build a new
detection signal** — nothing concrete existed to build against, and
guessing would violate the same "don't inflate on weak signal" discipline
as Task 1.

**Task 3 — reconciliation against Track A's corrections: clean.** Both
misattributed posts (`kingjames`→nike, `keralablasters`→astermedcity) are
`creator_id=null, is_sponsored=false, brand_id=null` in the live DB —
confirmed directly, neither leaks into any event or pair count on this
side. `/feature-store/edges/collaborations` returns 340 raw edges / 170
distinct pairs against a live `creators` count of 259 (exactly one
`%athletics%`-name row) — matches the orchestrator's post-merge figures
exactly, no residual duplicate-driven inflation.

**Task 4 — 8 newly-sponsored creators are already graph-connected, not
previously part of the 52-pair baseline.** Cross-checked all 17 distinct
sponsored creators (excluding null-`creator_id` rows) against
`creator_related_accounts`: 14 are graph-connected. `mrbeast`/`CarryMinati`,
`Cristiano Ronaldo`, `Virat Kohli`, and `Kerala Blasters` were already
known/counted (their sponsorship events predate this round, and
`keralablasters`'s graph connection via `mumbaicityfc`/`chennaiyinfc`
appeared between Phase 1H and now via Track A's bulk promotion, not this
round's work). But **8 names never seen in any prior Track C round are
both newly sponsored — fetched 2026-08-17 through 08-21, i.e. content that
was still `is_sponsored IS NULL` before this round's relabel — and already
resolved into the graph**:

- **`Prajakta Koli` ↔ `Taaruk Raina`** — direct mutual edge, both newly
  sponsored (Prajakta Koli: 1 IG + 1 YT; Taaruk Raina: 4 IG, all native
  `has_paid_partnership_label`)
- **`karanjohar` ↔ `Bhuvan Bam` ↔ `Pratibha Ranta` ↔ `Gurfateh Singh
  Pirzada`** — mutually connected 4-way cluster, all four newly sponsored
- **`Sania Mirza`** — connected to `karanjohar`, newly sponsored

**This is real signal the orchestrator's 52-pair canonical count
(2026-08-21) has not seen**, since it predates this round's relabel of the
previously-null backlog. Flagging explicitly per this round's instruction
rather than folding it into the aggregate event count — **recommend a
fresh `pair_count.py` run before Track B trains.**

**Sponsorship-edges reconciliation**: 10 → **16**, reconciles exactly
against `is_sponsored=true AND brand_id IS NOT NULL AND creator_id IS NOT
NULL` (2 Instagram rows have `brand_id` but `creator_id=null` — the
already-corrected misattributed posts, correctly excluded from the count).

**Verification discipline**: reused existing `.venv`/`.env` (pooler DSN
still valid), no ephemeral scripts left in the repo, labeling regex/router
code unchanged (only data corrected on individually-verified false
positives), 49/49 tests still pass, working tree clean.

## P1.6 — Real Spillover Wiring (2026-08-26) — GAIL checkpoint c6488a6, honest small-N CI

Prompted by `CAPSTONE_NEXT_STEPS.md:778-795` (effective N=10, propensity saturates 1.000) and `HANDOFF.md:3` (no checkpoint → flat 0.5). Track B landed `c6488a6` on `origin/track-b-ml-core`: `ml/inference.py` (`load_predict`/`load_predict_batch`/`IsolatedCreatorError`) + `models/gail_checkpoint.pt` (prod model trained once on all 54 pairs, normalized propensity, 259 nodes). Track C vendored `backend/app/gail/` + `backend/models/gail_checkpoint.pt` (3.7M) and added `backend/app/spillover.py` wrapper that **never crashes**: checkpoint missing / `IsolatedCreatorError` / `KeyError` / `torch` missing → `basis="placeholder"`/`"isolated"` with `0.5` and wide CI.

**Contract change (breaking, Track D must read `spillover_basis`):**

`spillover_basis: "trained" | "inferred" | "placeholder" | "isolated"` added to `FusionScoreResponse` and `InfluencerRecommendation` (`backend/app/schemas.py`). `POST /scores/compute` now accepts `spillover_score` as optional — if omitted, auto-resolves via GAIL (real if available, else placeholder). `GET /scores/{id}` recomputes live spillover (not stale DB row) so basis/CI reflect current checkpoint. `POST /recommendations` batch-resolves via `get_spillover_batch` (single GAT forward, cached) and writes honest `spillover_basis` per row; `isolated` (degree 0 on both `collaborates_with` + `co_occurs_with`) → `placeholder` (0.5), never `inferred`.

**Confidence — honest small-N (`backend/app/fusion.py:57`, `backend/app/spillover.py`):**

- `trained`: `hw = t_{0.975,df} * sqrt(mse_trained) * sqrt(1+1/N)` with `N=10, df=8, t=2.306, mse=1.84 → hw≈3.28` on spillover 0-1 scale; `min_hw 0.15`.
- `inferred`: `hw = base_hw *1.6, min 0.25 → ≈5.25` (wider).
- `placeholder`/`isolated`: same wide `0.25` min.
- Final CI on `0-100`: `margin = hw *100 * w1` (`w1=0.4` only; `w2` variance not modeled because Temporal `0% built` `CAPSTONE_NEXT_STEPS.md:822`). Clamped `[0,100]`. So even `trained` spans ~±13pts, `inferred` ~±21pts on `final_score` — deliberately wide, not fake precision, reflecting `CAPSTONE_NEXT_STEPS.md:795` (propensity 1.000) and `787` (N=10). Documented as comment in `fusion.py` and here.

**Weights — only `w1` real:** `backend/app/config.py` stays `0.4/0.3/0.3`. Only `w1` (spillover) is now backed by GAIL; `w2` (`sentiment_risk_score`) remains `0.5` placeholder — documented, not recalibrated as if all real.

**Live verification (pooler `CAPSTONE_NEXT_STEPS.md:440`):** `pytest 49` still pass (lazy GAIL import — no torch needed), plus live `GET /health`, `/feature-store/edges/sponsorships`, and `POST /recommendations` showing 3 rows with full JSON (see HANDOFF.md Task 4). See `backend/migrations/0003_add_fusion_spillover_basis.sql` for `fusionscore.spillover_basis`.

## Phase 1H (2026-08-18) — YouTube's first real signal, confirmed not an unbuilt capability

Prompted by `CAPSTONE_NEXT_STEPS.md` §1a (added this round), which flagged
that all 32 known sponsorship events were Instagram-only and asked whether
that's a real finding or just YouTube/Reddit never having been checked at
scale (YouTube alone grew ~10→39 covered creators / 1,227 videos since the
labeler last ran against it).

**Task 1 — does real multi-platform detection logic exist, verified by
reading code, not inferred from the zero count.** `app/routers/labeling.py`
calls the same `detect_sponsorship()` against all three platforms:
`youtube_videos.title/description`, `instagram_posts.caption`,
`reddit_posts.title/body` — confirmed by reading the router directly, all
three branches present since Weeks 7-8, nothing Instagram-only about the
core function. The regex pattern list in `app/labeling.py` (`#ad`,
`"sponsored by"`, `"in partnership with"`, `"brought to you by"`, etc.) is
generic disclosure-convention text, not Instagram-specific — hashtags read
naturally on Instagram but the phrase patterns apply equally to YouTube
descriptions or Reddit bodies. The only Instagram-specific logic is the
`has_paid_partnership_label` native-signal override, which is correctly
scoped to Instagram since that's an Instagram-only platform feature, not a
gap. **Conclusion: the "32 events, Instagram-only" result really was zero
real signal at the old, much-smaller YouTube/Reddit scale — not an
unbuilt/Instagram-only capability.** No code changes were made or needed
for Task 1.

**Task 2 — force-relabel, all three platforms.** `POST
/labeling/run?force=true` against 1,227 YouTube / 1,419 Instagram / 681
Reddit (YouTube and Reddit both grew substantially since the last labeling
pass; Instagram unchanged). Results:

| Platform | Before | After | Detection |
|---|---|---|---|
| YouTube | 0 | **2** | both via `"brought to you by"` in the video description (plain regex, no native-signal equivalent exists for YouTube) |
| Instagram | 32 | 32 (unchanged, no new rows) | — |
| Reddit | 0 | 0 | no hits |

Both new YouTube events are on `keralablasters` (a team account,
`creator_id=462094a7-a09d-43e5-b457-bb06c9de2229`), published 2026-05-16
and 2026-05-18. Neither has `brand_id`. **The yield looks structurally
different by platform, as expected**: Instagram's is dominated by the
native paid-partnership signal (17 of 32 events caught only that way, none
of which YouTube/Reddit have an equivalent for), while YouTube's hit came
from an explicit phrase, and Reddit produced nothing at all — consistent
with Reddit posts being informal/conversational text rather than
disclosure-convention-bearing marketing copy.

**Task 3 — checked immediately whether either new event lands on an
already-graph-connected creator, not buried in the aggregate.**
`keralablasters` has **zero rows anywhere in `creator_related_accounts`**
— confirmed two ways: filtering the live
`/feature-store/edges/collaborations` response for this creator_id (0
matches), and a direct raw query against `creator_related_accounts` for
rows where this creator_id is the source (0 rows) — it isn't even a
dangling/unresolved handle referenced by someone else. **No new
computable-pair candidate this round.** Real new signal, but currently an
isolated node in the graph. Flagged in `HANDOFF.md` for a quick recheck
next round rather than a full relabel, since Track A's ongoing discovery
work could connect it without any Track C action.

**Task 4 — sponsorship-edges reconciliation.** `GET /feature-store/edges/
sponsorships`: **10 → 10** (checked before and after Task 2 — unchanged,
since neither new YouTube event has `brand_id`). Reconciled exactly against
`SELECT count(*) FROM (youtube_videos UNION instagram_posts UNION
reddit_posts) WHERE is_sponsored=true AND brand_id IS NOT NULL` = 10. Same
clean reconciliation as every prior round.

**§1a batch-readiness checklist**: "Track C has re-run its labeler across
the full YouTube/Reddit content pool" — **done this round**, flagged for
the orchestrator to check off in `CAPSTONE_NEXT_STEPS.md`. The "all 32
known sponsorship events are Instagram-only" framing in that same checklist
is now stale (34 events, 2 YouTube) — flagged alongside it. Computable
training pairs did not grow this round (still the single mrbeast↔
CarryMinati pair from Phase 1G) — still well below the 20-pair sufficiency
bar.

**Verification discipline**: reused existing `.venv` and `.env` DATABASE_URL
pooler fix (both still valid), no ephemeral scripts left in the repo, no
resolver/model/labeling code changed this round (verification + relabel
only — per this round's explicit "don't build new detection patterns"
instruction), 49/49 tests still pass, working tree clean, merge from `main`
(commit `dbc79c5`) pushed alongside this update.

## Phase 1G re-verification (2026-08-17) — first computable training pair, sparsity finding retired

Prompted by the orchestrator's `CAPSTONE_NEXT_STEPS.md` rewrite (commit
`c71e533`), which retired the Phase 1F "structurally sparse, 10 pairs, 2.4%"
finding directly below. **Read that retraction before trusting anything in
the "Phase 1F" section further down this file** — it's kept for the record,
not because it's still current.

**⚠️ Correction, stated first: the collaboration graph is NOT structurally
sparse.** The Phase 1F finding was real *of the unpromoted 63-creator graph
at the time*, but was a snapshot mistaken for a ceiling. The user reviewed
the full 258-candidate sheet backlog and bulk-promoted them — zero new
scraping, just converting existing dangling `creator_related_accounts` rows
into resolved pairs by giving their endpoints `creators` rows. Resolve rate:
**2.4% → 31%** (161 distinct pairs, up from 10). Independently re-derived
this round via the identical handle-resolution script used every prior
round — matches the orchestrator's figure exactly. **Any doc, including this
one further down, or memory citing "10 pairs" is now stale — always
re-verify against the live DB before citing it.**

**Live-state self-check.** `creators`=259, `creator_related_accounts`=668
rows, `instagram_posts`=1,419, `has_paid_partnership_label` true=24 — all
matched the round's briefing exactly. Confirmed the milestone post
`Db5rzczsSV5` (`mrbeast`) directly: `has_paid_partnership_label=true`,
`is_sponsored` was `NULL` (not the labeled-`false` case), caption
`"...#oldnavypartner"` — a hashtag pattern the existing regex list
(`#ad`/`#sponsored`/`#spon`/`#paidpartnership`/etc.) does not match, making
this a genuine test of the native-signal-only path, not caption regex.

**Task 1 — force-relabel.** `POST /labeling/run?force=true` against 315
YouTube / 1,419 Instagram / 555 Reddit. **Events: 18 → 32, all Instagram**,
YouTube/Reddit still 0 (both grew in row count from Track A's ongoing
collection but produced no hits). Of the 32: **15 caught by caption-text
regex** (some also carrying the native marker), **17 caught only by
`has_paid_partnership_label`** — this round's native-only share (17/32,
53%) is notably higher than last round's (5/18, 28%), consistent with
Track A's newer posts increasingly using branded hashtags the regex list
was never built to catch, rather than explicit "#ad"-style tags.

**Task 2 — the mrbeast/Old Navy post, confirmed explicitly, not buried in
the aggregate.** Post-relabel: `Db5rzczsSV5` → `is_sponsored=True`,
`sponsorship_raw_matches=['native:paid_partnership_label']` (regex found
nothing — confirms the native signal did the work, exactly as predicted).
`brand_id` is still `NULL` — queried `brands` directly, no "Old Navy" row
exists yet (10 brand rows total: Agilitas, Airtel, Amazon Prime, BGMI,
Cadbury, Esports World Cup, Milton, oakleymeta, optimumnutri, Visit Dubai —
no Old Navy). Grepped this entire backend for brand-extraction logic and
found none — `brand_id` only ever appears as a field reference
(`models.py`/`feature_store.py`/`schemas.py`), never assigned from text
anywhere in Track C's code. **Brand extraction is entirely Track A's
ownership** (`scripts/ingestion/`, per the track-ownership table), not
something to build here.

Separately confirmed the graph-connection half of the claim, live: queried
`creators` for `mrbeast` (`2b23aa86-...`) and `CarryMinati`
(`c086bf2e-...`), then filtered the live `/feature-store/edges/
collaborations` response for that exact pair — **found, weight 2.0, both
directions.** The neighbor-straddle condition (CarryMinati's dated posts on
both sides of 2026-08-12) was independently verified by the orchestrator
this round and was explicitly out of scope to re-check here.

**⇒ Yes: the project's first fully-computable GAIL training pair
(treatment event + graph-connected neighbor + straddling neighbor data) is
now real**, confirmed independently across all three of Track C's own
checkable conditions. `brand_id` absence doesn't block this — P0.4's
computable-pair definition is graph-connection + straddling data, not brand
identification — but it does mean this specific event stays invisible to
`/feature-store/edges/sponsorships` until Track A extracts "Old Navy."

**Task 3 — collaboration-edges endpoint against the new 161-pair reality.**
`GET /feature-store/edges/collaborations` returns **322 edges**. Verified
programmatically these collapse to exactly **161 distinct undirected
pairs**, each still appearing in both directions — no code change was
needed since the endpoint recomputes from live DB state on every call, so
it already reflected the bulk promotion the moment it landed. **Report as
161 relationships, not 322** — same 2-directed-edges-per-pair convention as
before, just at 16x the count.

**Task 4 — sponsorship-edges reconciliation.** `GET /feature-store/edges/
sponsorships`: **10 → 10** (checked before and after Task 1's relabel — no
change, since none of the 14 newly-surfaced events got a `brand_id`).
Reconciled exactly against `SELECT count(*) FROM instagram_posts WHERE
is_sponsored=true AND brand_id IS NOT NULL` = 10. Zero divergence — the
same clean reconciliation as every prior round.

**Verification discipline**: reused existing `.venv` and the `.env` pooler
fix from last round (both still valid), no ephemeral scripts left in the
repo, no resolver/model code changed this round (verification + relabel
only), 49/49 tests still pass, working tree clean, merge from `main`
(commit `c71e533`) will be pushed with this update.

## Phase 1F re-verification (2026-08-15) — routine, no code changes

**⚠️ RETIRED 2026-08-17 — see the Phase 1G section above.** The "10 distinct
pairs, structurally sparse, 2.4%" claim throughout this section was real
*of the unpromoted graph at the time* but was superseded by bulk promotion,
not by new scraping. Kept below for the historical record only — do not
cite these figures as current.

Prompted by the orchestrator's `CAPSTONE_NEXT_STEPS.md` rewrite (commit
`aef6401`) after Track A's Phase 1F round scanned 267 more Instagram posts
(825 → 1,092) and disproved the "more coverage → more resolved edges"
hypothesis. This round's job: confirm the live numbers, not change code.

**Live-state self-check first.** Queried the DB directly before trusting the
doc: `creators`=63, `creator_related_accounts`=505 rows, `instagram_posts`
=1,092, `has_paid_partnership_label` true=12, `is_sponsored=true`=11 with
`brand_id`=9 (pre-relabel baseline) — every figure matched
`CAPSTONE_NEXT_STEPS.md` §3.2a exactly. One discrepancy from the round's own
briefing, not the doc: the 267 newly-scraped posts are stored with
`is_sponsored IS NULL` (691 rows), not a default `false` as described —
doesn't change anything since `force=true` reprocesses both, just noting it
because "verify before trusting" applies to task framing too, not only docs.
Also applied `CAPSTONE_NEXT_STEPS.md` §3.4b's DATABASE_URL pooler fix — this
worktree's `.env` still had the old IPv6-only direct host.

**Task 1 — force-relabel.** `POST /labeling/run?force=true` against
299 YouTube / 1,092 Instagram / 435 Reddit. **Events: 11 → 18, all
Instagram**, YouTube/Reddit still 0. Of the 18: **13 caught by caption-text
regex** (`#ad`/`#Ad`/`#AD`), **5 caught only by `has_paid_partnership_label`**
(no regex marker at all) — including `DUkDWOYiL8x`, still a 0-length caption,
the case a text-only labeler structurally cannot reach. `brand_id`: **10 of
18 set** (was 9 of 11 — Track A's brand-extraction fix caught up on the
original 11 but only 1 of the 7 newly-surfaced events got a `brand_id` this
round).

**Task 2 — sponsorship-edges endpoint.** `GET /feature-store/edges/
sponsorships`: **9 → 10** (checked before and after the relabel). Reconciled
exactly against the raw `SELECT count(*) FROM instagram_posts WHERE
is_sponsored=true AND brand_id IS NOT NULL` = 10. No divergence between the
endpoint and the DB this round — `build_sponsorship_edges()` is working as
documented, the gap is purely upstream (brand extraction lagging labeling).

**Task 3 — collaboration-edges endpoint, direction handling.** `GET
/feature-store/edges/collaborations` returns **20 edges**. Independently
reproduced the resolution logic directly against the live DB (not just
reading code): 505 `creator_related_accounts` rows → **15 resolved** → **10
distinct pairs** after deduping reciprocal directions with
`sorted((a,b))` — exactly matching Track A's "505/15/10" claim. Confirmed
from the API response itself that all 20 returned edges collapse to exactly
10 undirected pairs, each appearing in **both directions** (source→target
and target→source) — this is deliberate, not a double-count bug:
`build_collaboration_edges()`'s docstring states it matches Track B's
`ml/schema.py`, which does not apply `ToUndirected()` at load time. **Report
this as 10 relationships, not 20** — the edge count is 2x the pair count by
design.

**Task 4 — sparsity, stated plainly for Track B.** The collaboration graph
is genuinely, structurally sparse: **10 distinct pairs across 63 creators.**
Track A tested and disproved the "more Instagram coverage grows the graph"
hypothesis directly this phase — scanning went 24→31 of 63 creators covered
with **zero** new resolved edges, because only ~2.2% of observed co-authors
are creators in our own curated set (the set was curated for
recommendation-worthiness, not mutual collaboration). This is confirmed, not
suspected — Track B should build its first real graph expecting this shape
rather than discovering it mid-training and suspecting an upstream bug. The
only lever that has moved the count (7→10 pairs) is targeted promotion off
the sheet's "bridge queue," which is a curation decision reserved for the
user, not something Track C or B should try to route around.

**Verification discipline**: existing `.venv` reused (still has all deps),
`.env` DATABASE_URL fixed as noted above, no ephemeral scripts left in the
repo, no code changes made this round (verification-only, per the round's
explicit "don't touch resolver behavior unless double-counting" instruction
— it isn't), 49/49 tests still pass, working tree clean, merge from `main`
(commit `aef6401`) pushed to `origin/track-c-fusion-backend`.

## Post-Phase-1D update summary (2026-08-14) — first real sponsorship events

**This is the round that answers the project's central open question: real
sponsorship events now exist in the data.** Prompted by the orchestrator's
`CAPSTONE_NEXT_STEPS.md` (commit `d98a068`) after Track A's Phase 1D caption
fix + `has_paid_partnership_label` schema addition. Every number below was
independently re-verified against the live DB via direct query, not taken
from the orchestrator's doc (which was itself already stale by the time this
round ran — see below).

- **Verified live state myself before trusting any doc.** `instagram_posts`
  had grown to 401 rows (372 non-null captions, 369 distinct) and
  `has_paid_partnership_label` to 4 true / 275 false / **122 NULL** — all
  higher than the orchestrator's same-day figures (401 vs 143, 4 vs 3, and a
  new 122-NULL gap the orchestrator hadn't seen), confirming Track A's
  background collection kept running between the orchestrator's snapshot and
  this session. `creator_related_accounts` was 192 rows, not 72.
- **Found `has_paid_partnership_label` was not wired into the labeler at
  all** — `InstagramPost` (`app/models.py`) had no field for it, and
  `POST /labeling/run` only ever called `detect_sponsorship(caption)`. Added
  the field to the model and updated `app/routers/labeling.py`: a post with
  `has_paid_partnership_label=True` is now unconditionally `is_sponsored=True`
  (audit trail gets a `"native:paid_partnership_label"` marker in
  `sponsorship_raw_matches`), independent of caption-regex outcome. Added
  `test_paid_partnership_label_forces_sponsored_even_without_caption_match`
  (real case: post `DUkDWOYiL8x`, `caption=None`, label=`True` — a
  caption-only labeler structurally cannot see this). 49/49 tests pass.
- **Ran `POST /labeling/run?force=true` against the full live dataset.**
  Before: 0 sponsorship events on every platform (Instagram/YouTube/Reddit
  all-false or all-null). **After: 11 real sponsorship events, all on
  Instagram** (`youtube_videos`: 299 checked, 0 sponsored; `instagram_posts`:
  401 checked, 11 sponsored; `reddit_posts`: 435 checked, 0 sponsored).
  - **9 of 11** caught by caption-text regex (`#ad`/`#Ad`/`#AD` variants —
    the caption fix landing means these are now visible past the old
    100-char truncation).
  - **2 of 11** caught *only* by `has_paid_partnership_label` — caption
    regex alone would have missed them. One (`DUkDWOYiL8x`) has no caption
    text at all. This is exactly the signal the orchestrator flagged as the
    highest-precision one available, now proven to add real recall a
    text-only labeler structurally cannot reach.
- **Broader adversarial recall scan re-run across all three platforms**
  (sponsor/partner/collab/affiliate/#ad/ambassador/discount code/promo
  code), not just the regex's own hits. Two YouTube results looked like real
  undisclosed brand deals on inspection (`WanderOn`-sponsored Ladakh vlogs)
  but their full descriptions explicitly read *"I want to be upfront about
  this, they never asked me for this shoutout"* — an explicit **non**-
  paid disclosure, correctly excluded. All other hits (sports "partner"
  terminology, "#Collaboration" hashtag on a tech unboxing with no `#ad`,
  third-person Reddit commentary) fell under already-covered near-miss
  patterns. No regex change made.
- **Kohli/Agilitas: the underlying blocker is now resolved — not still
  blocked, and not stale-re-asserted.** All 5 of the creator's `one8`/
  `Agilitas` posts are now stored at full length (140-443 chars,
  `fetched_at` 2026-08-11/12, well past Track A's caption-fix commit) —
  Instagram *has* been re-scraped since the last round's check. With real
  full text now available (`"2 years back I joined hands with Agilitas to
  build a dream - one8... it gives all of us at Agilitas immense
  courage..."`), and `has_paid_partnership_label=False` on all 5, the
  `is_sponsored=false` call stands — but now as a **confirmed decision
  against real complete text**, not a placeholder blocked on missing data.
  Recorded as resolved in the dedicated section below.
- **Verified edge resolution against real endpoint output, not just code
  reading.** `GET /feature-store/edges/collaborations` returns **4 edges**
  (2 resolved pairs × 2 directions) against 192 `creator_related_accounts`
  rows — independently reproduces Track A's own "2 resolve" report exactly.
  Read `build_collaboration_edges()` directly to confirm *why*: both
  endpoints of a row must already exist as `creators` rows with their own
  handle set, which is true for only 2 of the 192 rows today — consistent
  with Track A's explanation (resolution capped by Instagram coverage
  breadth, not the extraction mechanism).
- **New finding, not yet in any doc: sponsorship *events* (11) and
  sponsorship *edges* (1) have sharply diverged.**
  `GET /feature-store/edges/sponsorships` returns only **1** row, because
  `build_sponsorship_edges()` requires `brand_id IS NOT NULL` in addition to
  `is_sponsored=true` — and only 1 of the 11 newly-labeled posts has a
  `brand_id` resolved (`creator_id` is populated on all 11). This is Track
  A's brand-extraction step, not a Track C bug — `brands` is populated only
  from sponsorship-disclosure text (per `CAPSTONE_NEXT_STEPS.md` §3.3), and
  that extraction evidently hasn't run against this round's newly-labeled
  rows yet. **Flagging directly: Track B, consuming
  `/feature-store/edges/sponsorships` as documented, will see 1 usable
  training pair today, not 11**, until Track A's brand extraction catches
  up. The `creator_sponsorship_events` DB view shows the same split (11
  rows, 10 with `brand_id=NULL`).
- **Confirmed all 4 feature-store endpoints Track B consumes return real,
  non-empty data** (except co-occurrence, expected-empty, see below):
  `/feature-store/creators` → 56, `/edges/collaborations` → 4,
  `/edges/sponsorships` → 1 (see finding above), `/edges/co-occurrence` → 0
  (still genuinely empty — Track A's Reddit rework is still in progress per
  their own branch; not a regression, matches the documented open item).

## Weeks 14-16 update summary

- **Re-ran `POST /labeling/run`** (default mode) against the dataset's
  continued background growth (422 → 695 real content rows — 252 YouTube /
  97 Instagram / 346 Reddit — grown via Track A's scheduled Task
  Scheduler runs, independent of any git commit). 273 newly-landed rows
  labeled (133 YouTube, 140 Reddit; Instagram had 0 unlabeled — already
  fully labeled from last round). Still 0 hit any disclosure-tag pattern;
  all 695 rows now have a real non-null `is_sponsored`.
- **Re-ran the broader keyword recall scan** (sponsor/partner/collab/
  affiliate/#ad) against the newly-landed text specifically, not just the
  regex's own hits, per this project's standing precision-first practice.
  Found several real matches, checked each individually — all fall under
  patterns already covered by the existing 48-test suite (sports
  "partner" terminology, event-hosting "in collaboration with", third-
  person "X sponsored Y" in Reddit commentary about a creator rather than
  the creator's own disclosure). No new near-miss pattern found, no regex
  change needed.
- **Kohli/Agilitas: re-checked directly against the live DB, still
  blocked, no new finding.** Both the original post and its previously-
  identified "one8" sibling post are still stored at exactly 100
  characters (`fetched_at` still 2026-08-09, predating Track A's caption
  fix). Confirms the resolution below is unchanged — re-verified, not
  re-asserted. Concrete unblock path (`force=true` after Track A
  re-scrapes) still stands, still not yet actionable.

## Weeks 11-13 update summary

- **Re-ran `POST /labeling/run`** against the dataset's continued growth
  (97 → 422 real content rows, as Track A diversified the target list to
  15 creators including non-athlete YouTubers). 325 newly-landed rows
  labeled, still 0 hit any disclosure-tag pattern.
- **Added `force=True` query param to `POST /labeling/run`** — a real gap
  found this round: the default mode only processes `is_sponsored IS NULL`
  rows, but Track A's upsert never touches `is_sponsored`/
  `sponsorship_raw_matches` (that's Track C's column), so if Track A
  corrects a row's text *after* Track C already labeled it, the corrected
  text would never get re-examined under default mode — permanently stuck
  on a label computed against stale text. Concrete motivating case: the
  Kohli/Agilitas caption (see below).
- **Re-validated precision at the new scale with real near-misses**, not
  just a bigger version of the same check — scanned the full ~400-row
  dataset for anything containing sponsor/partner/collab/affiliate
  keywords, then checked each real hit against the actual patterns. Found
  and added 4 new tests from genuinely real text: "in collaboration with"
  (an event-hosting announcement) vs. "in partnership with", vague ongoing-
  relationship language ("a partnership that's...") vs. the literal
  disclosure phrase, "was my sponsor" (personal patronage, wrong direction)
  vs. "sponsored by", and "batting partner" (sports terminology) — all
  correctly produce no match. 48 tests total now, all passing.
- **`co_occurs_with` edges are empty again** — not a regression. Track A
  purged 88% of the Reddit data these edges were built from as topically-
  irrelevant noise (measured directly: 0 of 41 r/badminton posts credited
  to PV Sindhu actually mentioned her). Confirmed the feature store
  self-healed automatically — it recomputes from live DB state on every
  request rather than caching, so no code change was needed when the
  underlying (bad) signal disappeared. Real edges will return once Track
  A's new two-mode Reddit collection (verified-relevant only) produces
  genuine co-occurrences.
- **`reputation_score`**: still no source column anywhere in Track A's
  schema (re-checked their latest migration — adds `reddit_topic_subs`,
  not a metric). Track A's Reddit rework does make community discussion
  *about* a creator more reliably real now (verified-relevant, not noise),
  which is a prerequisite for a future sentiment-based reputation proxy —
  but building that sentiment analysis is Track B's Temporal branch/
  Sentiment Propagation deliverable (PROJECT_PLAN.md Section 3b), not
  something to invent unilaterally in the feature store. Flagged as an
  observation, not built.
- **Self-check**: with Track D's browser tool now working, checked for
  other curl-only-verified behaviors beyond the CORS fix itself. Tested
  three real candidates: trailing-slash redirects (307 responses do carry
  `Access-Control-Allow-Origin`, confirmed via curl), the custom NaN-
  sanitizing exception handler's responses, and 401 auth-failure responses
  — all three correctly carry CORS headers. No new gap found, but this
  doesn't prove nothing else exists; flagging as checked, not exhaustive.

## Kohli/Agilitas resolution (2026-08-10, **closed 2026-08-14**)

**Decision: `is_sponsored = false`, now confirmed against real complete
text, not a placeholder pending data.**

Originally left `false` because the only available text was truncated at
exactly 100 characters (a real `opencli instagram user` bug) — see the
history below. **Re-checked 2026-08-14**: Instagram has since been
re-scraped. All 5 of `virat.kohli`'s `one8`/Agilitas posts
(`DSKdvOwkQsw`, `DaDJji0DY_x`, `DZZ8lRptve1`, `DZHR_3_NcCr`, `DYuLMR3t180`)
are now stored at full length (140-443 chars, `fetched_at` 2026-08-11/12).
Full text confirms, in the creator's own words: *"2 years back I joined
hands with Agilitas to build a dream - one8... it gives all of us at
Agilitas immense courage..."* — a genuine co-founder/ownership
relationship, not a one-off paid disclosure. No `#ad`/`#sponsored`/
"paid partnership" phrase anywhere across all 5, and
`has_paid_partnership_label=False` on all 5 (Instagram's own native signal
agrees). Both independent signals now confirm `false` on real data — the
call is unchanged, but the blocker (missing/truncated text) is resolved,
not still open.

<details>
<summary>Original 2026-08-10 reasoning (for history)</summary>

Checked whether the full caption is available before deciding, per
instruction:
- Track A root-caused the truncation (a real bug: `opencli instagram user`
  truncates captions to exactly 100 chars) and fixed it in code
  (`origin/track-a-data-infra` commit "Reddit two-mode strategy,
  diversified target list, full-caption fix").
- The fix had not yet been applied to any existing row at that time —
  checked directly, the most recent `instagram_posts.fetched_at` across
  the entire table predated that fix commit.
- This was systemic, not a single post: a second real post from the same
  account describing the same "one8" brand relationship was also
  truncated at exactly 100 characters. Every Instagram caption in the DB
  at that time was fetched before the fix.

Given the full text was confirmed unavailable (not just unchecked), and
the visible truncated text in both posts read as describing an ongoing/
co-founded brand relationship rather than a one-off paid post — labeling
it `true` would have been a guess dressed as a finding. Per
PROJECT_PLAN.md Section 1's precision-first framing (a wrong positive
poisons a real training label; a missed positive is just absent signal),
the safer default held until real text existed. It now does, and confirms
the same call.

</details>

## Weeks 9-10 update summary

(Original Weeks 9-10 target -- cross-platform identity linking -- was
already done by Track A in Weeks 7-8 out of urgency, no Track C action
needed there. This round was the CORS fix above plus:)

- **New:** `GET /feature-store/edges/co-occurrence` — `co_occurs_with`
  edges, previously an open gap ("no signal exists"), now real. Track A
  added `reddit_post_creators` (a many-to-many junction: a Reddit post can
  relate to multiple creators, most commonly because
  `creators.reddit_handles` is often a shared community subreddit like
  r/badminton, not creator-exclusive) — confirmed live with real data, not
  just schema: PV Sindhu and Saina Nehwal co-occur on 5 real posts via
  r/badminton. `reputation_score` re-checked against Track A's latest work
  (creator-ID dedup, Reddit profile enrichment) — still no source column
  anywhere, still open, not force-fixed.
- Re-ran `POST /labeling/run` against the now-much-larger real dataset (97
  content rows, up from 21) — 76 newly-landed rows labeled, still 0 hit any
  disclosure-tag pattern. All 97 real content rows now have a real
  `true`/`false` `is_sponsored`, zero remaining `null`. **Not the same as
  "0 real sponsorships"** — see the flagged edge case below (a real
  Kohli/Agilitas post with a brand match but no disclosure-tag match, real
  caption truncated by Track A's scraper before any possible tag).
- Confirmed Track B is already consuming `/feature-store/*` directly and
  successfully (`ml/feature_extraction.py::RawCreatorRecord` mirrors
  `CreatorFeatureRecord` exactly, per their GRAPH_SCHEMA.md) — no contract
  drift found on their side.

## Weeks 7-8 update summary

- **New:** `POST /labeling/run` — the actual disclosure-tag (`is_sponsored`)
  labeling pipeline, see its own section below. Already run against the
  live DB: 21/21 real content rows labeled (0 false positives on real data).
- Text scrubbing (`app/text_processing.py::scrub_text`) now applied to the
  feature store's `raw_text` before staging it for Track B's BERT step —
  not a wire-shape change, just better content.
- **Fixed a real latent bug in `build_collaboration_edges`**, found while
  re-checking the feature store against live data per this round's
  instructions: ambiguous handles (the same handle claimed by 2+ creator
  rows — confirmed live, from Track A's pre-fix creator-dedup bug) were
  previously resolved to whichever creator got processed last while
  building the lookup map, silently and non-deterministically. Now treated
  as unresolvable instead. Wasn't yet causing a wrong result (
  `creator_related_accounts` was empty at the time), but would have the
  moment it wasn't.
- `reputation_score` / `co_occurs_with` gaps (flagged Weeks 5-6): re-checked
  against Track A's latest work (creator-ID dedup fix, Reddit profile
  enrichment) — neither is addressed by it. Still open, no new derivable
  signal found. Not force-fixed with an invented formula.

## ⚠️ Incident (2026-08-09): `POST /alerts` was returning 500 against the real DB

Fixed same-day, but flagging prominently since it may explain a live 500
Track D or anyone else hit. `RiskAlert.propagated_from_creator_id` was
added to `models.py` in the Weeks 5-6 commit, but `init_db()`'s
`create_all()` only creates tables that don't already exist — it silently
does **not** alter existing ones. Since `riskalert` already existed in the
live Supabase DB from Weeks 3-4, the new column never actually reached the
real table, even though the ORM model claimed it did. Every `POST /alerts`
against the real DB failed with `psycopg2.errors.UndefinedColumn` until
caught here. Confirmed via `information_schema.columns` before/after, plus
a real insert/delete round-trip. Fixed with a real migration
(`backend/migrations/0002_add_alerts_propagated_from.sql`, applied directly
against the live DB) instead of just editing the model again — see that
folder's README for the new rule this establishes: schema changes to an
*existing* Track C-owned table now require a hand-written migration file,
not just a `models.py` edit. Also diffed `fusionscore`'s live columns
against its model as a sanity check — no drift there.

## Weeks 5-6 update summary

- **New:** `GET /feature-store/creators`, `GET /feature-store/edges/collaborations`,
  `GET /feature-store/edges/sponsorships` — the DB → feature-store pipeline
  for Track B, see its own section below.
- **New:** `POST /ingestion/creators/related-accounts` — was missing an
  ingestion path even though the `Brand`/collaboration-edge logic needed to
  read it.
- **`product_category` / `platform_preference` filtering in
  `/recommendations` is now real** (was still-open as of the Weeks 3-4
  version of this doc).
- **`AlertResponse`/`AlertCreate` gained `propagated_from_creator_id`**
  (nullable uuid) — added ahead of the Weeks 14-15 Sentiment Propagation
  work landing, per Track D's flag that the freeform `source` string alone
  would force a second breaking change later.
- **Basic auth added**, opt-in via `API_KEY` env var, off by default.

---

## ⚠️ BREAKING CHANGE (2026-08-09) — read this if you read the Weeks 1-2 version

Two things changed from the version published 2026-08-08. **If Track A or
Track D built against the old version, re-check against this one:**

### 1. `creator_unique_id: str` → `creator_id: uuid.UUID`, everywhere

The Weeks 1-2 version invented a placeholder `unique_id: str` field before
Track A's real schema existed. Track A's actual, live `SCHEMA.md` uses
`creators.creator_id` (a Postgres `uuid`). Every endpoint below now uses
`creator_id` (UUID) instead of `creator_unique_id` (string) — this affects
`POST /recommendations` results, `POST /scores/compute`, `GET
/scores/{creator_id}`, `POST /alerts`, `GET /alerts`.

### 2. `is_sponsored` ownership — Track C's Weeks 1-2 assumption was wrong

The Weeks 1-2 version of this doc assumed **Track A pre-computes
`is_sponsored`** and sends it via ingestion. That was wrong. Per
PROJECT_PLAN.md Section 6, Weeks 7-8 explicitly assigns "sponsorship
labeling pipeline" to **Track C**, not Track A. Track A's real, live schema
confirms this: `is_sponsored` and `sponsorship_raw_matches` are **nullable,
unpopulated by design** on `youtube_videos` / `instagram_posts` /
`reddit_posts` — Track A stores raw scraped text only.

Fixed: every content-level ingestion schema below (`YouTubeVideoIngest`,
`InstagramPostIngest`, `RedditPostIngest`) now has `is_sponsored: Optional[bool]
= None` and `sponsorship_raw_matches: Optional[list[str]] = None`. The actual
disclosure-tag labeling logic itself is still a Weeks 7-8 deliverable — not
built yet — but the ingestion contract shape is now correct so Track A's
real Weeks 3-4 data lands without a schema mismatch.

### 3. (Not a break, but important) Track A's real pipeline bypasses `/ingestion/*` entirely

Discovered while reconciling schemas 2026-08-09: Track A's actual ingestion
orchestrator (`scripts/ingestion/orchestrator.py` on `track-a-data-infra`)
writes **directly to the shared Supabase Postgres DB** via `DATABASE_URL`,
not through this API. So `/ingestion/*` below is **not the primary
ingestion pipeline** — it's a secondary/manual write path (testing, other
tracks seeding data). The tables it writes to are the same tables Track A's
orchestrator writes to directly, so it stays useful, just not load-bearing
for the real Weeks 3-4 scraping pipeline the way Weeks 1-2 assumed.

---

## Note: `brands` table (added by Track A 2026-08-09, reconciled here same day)

Track A added a `brands` table + nullable `brand_id` FK on `youtube_videos`/
`instagram_posts`/`reddit_posts` (migration `20260809010000_add_brands.sql`,
bounded scope: populated only from brand names found in sponsorship-disclosure
text already on creator content, not an open crawl — see their SCHEMA.md).
Added a matching `Brand` model in `backend/app/models.py` so this stays in
sync. **Not yet exposed via `/ingestion/*` or used in `/recommendations`** —
Track A's orchestrator writes it directly like everything else (see breaking-
change note #3), and no Track C endpoint reads/writes it yet. Flag if Track B
or D need it surfaced through this API.

## Cross-track dependency flags

- **Track A (Data/Infra):** models in `backend/app/models.py` now mirror
  Track A's real `SCHEMA.md` + `supabase/migrations/20260808163402_init_schema.sql`
  as of 2026-08-09 (checked via `git show origin/track-a-data-infra:SCHEMA.md`).
  Re-diff if their schema changes — this repo doesn't auto-detect drift.
- **Track B (ML-Core):** `POST /scores/compute` expects `spillover_score`,
  `sentiment_risk_score`, `creator_feature_score` each as finite floats in
  `[0, 1]` (NaN/Infinity now explicitly rejected, see Validation section).
  Also flags an **open item from Track A's SCHEMA.md**: Track B's
  `GRAPH_SCHEMA.md` assumes brand-node features that no Track A table
  supplies — not a Track C concern directly, but worth knowing if you're
  coordinating with Track B.
- **Track D (Frontend+App):** build against the schemas below. `creator_id`
  is now a UUID string in JSON, not an arbitrary string — validate/parse
  accordingly. `POST /recommendations` responses include `is_mock_data`;
  check it before treating scores/results as real.

---

## Endpoints

### Health

`GET /health` → `{ status, db_connected, version }`

### Brand-input recommendation engine

`POST /recommendations`

Request:
```json
{
  "product_category": "fitness apparel",
  "budget": 50000,
  "target_region": "IN-south",
  "target_demographic": "18-24 fitness enthusiasts",
  "platform_preference": ["youtube", "instagram"],
  "max_results": 10
}
```
`budget` must be `> 0` and finite (NaN/Infinity rejected with 422).

Response: `{ query, results: [InfluencerRecommendation...], is_mock_data }`

`InfluencerRecommendation` (now with `spillover_basis`):
```json
{
  "creator_id": "758b86ea-266d-48dd-848e-564f47ad8275",
  "name": "TestCreator",
  "category": "fitness_influencer",
  "youtube_handle": "@testcreator",
  "instagram_handle": null,
  "reddit_handles": ["r/test"],
  "final_score": 60.0,
  "confidence_low": 52.0,
  "confidence_high": 68.0,
  "spillover_basis": "trained",
  "estimated_reach": 1000000,
  "estimated_cost": 500000.0,
  "score_breakdown": { "spillover_score": 0.61, "sentiment_risk_score": 0.5, "creator_feature_score": 0.5, "weight_spillover": 0.4, "weight_sentiment_risk": 0.3, "weight_creator_feature": 0.3 }
}
```
`spillover_basis` values: `trained` (is in GAIL labeled N=10 set, tighter but still wide `±13pts`), `inferred` (graph-connected, GAT inductive, `±21pts` wide), `placeholder` (checkpoint missing/fallback `0.5 ±10pts`), `isolated` (degree 0 → `placeholder` `0.5` never `inferred`, no crash). Track D must key on this, not just `final_score`. See P1.6 section for `hw` derivation.

**Filtering/ranking behavior (fully real as of 2026-08-09):**
- **Budget** — hard filter. `estimated_cost = max(youtube subscriber_count,
  instagram follower_count) * 0.5 INR` — a **placeholder rate**, no real
  rate-card data exists yet. Candidates with no reach data at all aren't
  excluded (cost unknown, not assumed zero or infinite).
- **`platform_preference`** — hard filter. Creator must have a handle on at
  least one requested platform. Unlike the soft filters below, "no handle
  on this platform" is a directly known fact, not missing data.
- **`target_region` / `target_demographic` / `product_category`** — soft
  filters. A creator is excluded only if we *have* text signal for them
  (`youtube_channels.country`/`.description`, `instagram_profiles.bio`, or
  — for `product_category` — the creator's own `category`) and it does
  **not** keyword-match. Creators with no signal data at all are kept — with
  scraping still ramping up, a hard requirement would return empty result
  sets for almost every query right now.
  - Matching is **keyword-overlap** (any word ≥3 chars in the query appears
    in the combined signal text), not whole-phrase substring — a
    whole-phrase requirement almost never matches real bio/description text.
  - **Gotcha found during regression testing:** if the query itself has no
    extractable keywords (e.g. a 1-2 char string), that must be treated as
    "can't judge" and skip the filter, not as a confirmed mismatch — an
    earlier draft of this logic conflated the two and wrongly excluded
    every creator with *any* signal whenever the query was too short to
    yield a keyword. Fixed before this landed; flagging so nobody
    reintroduces it while touching this code later.
- Ordering is always by `final_score` descending among eligible candidates.
- Falls back to 3 mock creators (FitWithPriya/GymBro/YogaGuru) when the
  `creators` table is empty; falls back to a placeholder 0.5/0.5/0.5 fusion
  score per-creator when no `FusionScore` row exists yet for them. Check
  `is_mock_data` in the response — it's `true` if either fallback applied.

### Ingestion (secondary/manual write path — see breaking-change note above)

Requires `X-API-Key` if `API_KEY` is configured (see "Auth" below).

- `POST /ingestion/creators` — list of `CreatorIngest`. Upserts by `creator_id`
  (generated server-side if omitted).
- `POST /ingestion/creators/related-accounts` — list of
  `CreatorRelatedAccountIngest`. Upserts by the table's real unique
  constraint `(creator_id, platform, handle)`. This is the source table for
  the feature store's `collaborates_with` edges (see below) — added
  Weeks 5-6, was missing before even though the edge logic needed it.
- `POST /ingestion/youtube/channels` — list of `YouTubeChannelIngest`. Upserts
  by `channel_id`.
- `POST /ingestion/youtube/videos` — list of `YouTubeVideoIngest`. Upserts by
  `video_id`. `is_sponsored`/`sponsorship_raw_matches` optional/nullable.
- `POST /ingestion/instagram/profiles` — list of `InstagramProfileIngest`.
  Upserts by `username`.
- `POST /ingestion/instagram/posts` — list of `InstagramPostIngest`. Upserts
  by `post_id`. `is_sponsored`/`sponsorship_raw_matches` optional/nullable.
- `POST /ingestion/reddit/profiles` — list of `RedditProfileIngest`. Upserts
  by `username`.
- `POST /ingestion/reddit/posts` — list of `RedditPostIngest`. Upserts by
  `post_id`. `is_sponsored`/`sponsorship_raw_matches` optional/nullable.

All eight return `{ received, created, updated }`. Full field lists in
`backend/app/schemas.py` — they mirror Track A's real table columns exactly
(see SCHEMA.md), so cross-reference there for anything not shown here.
**Reminder:** `InstagramProfileIngest`/`YouTubeChannelIngest`/etc. all accept
an optional `creator_id` — if you omit it, the row never links back to its
creator (`creator_id` stays null), which silently breaks anything that joins
on it (recommendation filtering, feature-store aggregation). Always pass it
when you have it.

### Feature store (DB → Track B's `ml/schema.py` input shape, new Weeks 5-6)

Read-only. Transforms Track A's raw tables into the shape Track B's GAIL
branch needs — see `backend/app/feature_store.py` for the full writeup,
this is a summary. **Does not compute CLIP/BERT embeddings** (that's Track
B's Weeks 9-10 deliverable, confirmed via their GRAPH_SCHEMA.md) — stages
the raw inputs those need instead.

- `GET /feature-store/creators` → list of `CreatorFeatureRecord`:
  `creator_id`, `name`, `category`, `category_one_hot` (order matches Track
  B's `ml/schema.py::CREATOR_CATEGORIES` exactly), `log_subscriber_count`,
  `engagement_rate` (both computed from real data when available),
  `reputation_score` (**always null** — see gap below), `raw_text` /
  `thumbnail_urls` (staged for Track B's embedding step), `is_stub` (true
  if there's nothing to embed yet).
- `GET /feature-store/edges/collaborations` → list of `CollaborationEdge`
  (`source_creator_id`, `target_creator_id`, `weight`). Both directions
  populated per Track B's `ml/schema.py` requirement. Resolved from
  `creator_related_accounts` rows with `relation_type = "frequent_collaborator"`
  — `handle` there is free text, not a FK, so resolution is a
  case-insensitive match against every creator's own handles (`@`/`u/`/`r/`
  stripped). Rows that don't resolve are silently skipped, not an error —
  expect this until many more creators are seeded. **Ambiguous handles**
  (the same handle claimed by 2+ creator rows) are also treated as
  unresolvable rather than arbitrarily picking one — confirmed live
  2026-08-09 that Track A's pre-fix creator-dedup bug left real duplicate
  rows in production (two rows both claiming reddit handle "lebron"); their
  fix (`origin/track-a-data-infra` "Fix cross-platform creator-ID syncing")
  stops new duplicates but doesn't retroactively merge existing ones.
- `GET /feature-store/edges/co-occurrence` → list of `CollaborationEdge`
  (same shape as `/edges/collaborations`, different source signal). Resolved
  from `reddit_post_creators` (Track A's many-to-many junction: a Reddit
  post can relate to multiple creators, most commonly because they share a
  community subreddit like r/badminton). Two creators linked to the same
  post → an edge, weighted by count of shared posts, both directions.
  **Currently empty against real data** — the code is real and was
  verified against real data when built (2026-08-10, PV Sindhu / Saina
  Nehwal co-occurring on 5 r/badminton posts), but Track A then purged 88%
  of that Reddit data as topically-irrelevant noise (measured: those posts
  didn't actually mention the creators they were credited to). Confirmed
  the feature store self-heals automatically (recomputes from live DB
  state every request, nothing cached) — real edges will return once
  Track A's new two-mode Reddit collection produces genuine co-occurrences.
- `GET /feature-store/edges/sponsorships` → list of `SponsorshipEdge`
  (`creator_id`, `brand_id`, `content_id`, `platform`). Populated once
  `is_sponsored` is set — see the labeling pipeline below. Currently empty
  against real data — none of the 97 real content rows matched a
  disclosure-tag pattern, though at least one (`brand_id`-linked, no
  disclosure-tag match) is a flagged open edge case, not a confirmed
  true-negative — see the labeling pipeline section.

**Remaining known gap, flagged not fabricated:**
- `reputation_score`: Track B's schema expects this in the creator metadata
  segment, but **no Track A table has a reputation_score source column
  anywhere** (re-checked against Track A's latest work as of 2026-08-10 —
  their creator-ID dedup fix, Reddit profile enrichment, and the new
  `reddit_post_creators` junction don't touch this). Open cross-track item
  — needs either a new Track A column or a defined derivation formula.

Unit-tested against synthetic data (`backend/tests/test_feature_store.py`,
11 tests) and verified end-to-end through the live HTTP API against real
scraped content — Track A's real target list has grown to 10 creators, 97
total content rows across all three platforms as of 2026-08-10.

### Labeling pipeline (`is_sponsored`, Weeks 7-8, extended Weeks 11-13)

`POST /labeling/run` (requires `X-API-Key` if configured) — default mode
scans every `youtube_videos`/`instagram_posts`/`reddit_posts` row where
`is_sponsored IS NULL`, sets it to a real `true`/`false` (not left null),
and records matched phrases in `sponsorship_raw_matches`. No trigger/webhook
wiring it automatically yet — invoke manually (or from a script) after
Track A lands new content.

`POST /labeling/run?force=true` reprocesses **every** row regardless of
current value — added Weeks 11-13. Needed because Track A's upsert never
touches `is_sponsored`/`sponsorship_raw_matches` (Track C's columns), so if
Track A corrects a row's source text after it was already labeled, the
default mode would never re-examine it (no longer null → permanently
skipped). Use this after Track A does a corrective re-scrape of
already-labeled content — see the Kohli/Agilitas resolution above for the
concrete case this was built for.

Response: `{ youtube_videos: {checked, labeled_sponsored}, instagram_posts: {...}, reddit_posts: {...} }`.

**Detection approach** (`backend/app/labeling.py`): regex-based, matching
PROJECT_PLAN.md Section 1's own framing — `#ad`, `#sponsored`, `#spon`,
`#paidpartnership`, "sponsored by", "paid partnership", "paid promotion",
"in partnership with", "brought to you by", plus common misspellings
("sponser"/"sponsered", "spon-con"/"spon con"). Every pattern requires a
real word boundary so it can't fire inside an unrelated longer word/hashtag.

**This is the sole source of GAIL's treatment labels (PROJECT_PLAN.md
Section 1), so precision is validated deliberately at every scale increase,
not just "it finds #ad" once** — `backend/tests/test_labeling.py` +
`test_labeling_router.py`, 26 tests, split across:
- Positive cases covering every convention above.
- **Decoys targeting the exact regex risks a naive substring match would
  fall into**: `#adventure`/`#adidas` (must not match `#ad`), "advice"
  (must not match standalone "ad"), "spontaneous" (must not match
  "spon-con"), a brand name mentioned with no disclosure language, a
  genuinely ambiguous "institutional partnership" phrasing (university
  affiliation, not a brand deal).
- **Real decoys pulled verbatim from live scraped content**, added across
  two rounds as the dataset grew: (Weeks 7-8, ATHLEAN-X) a 4600+ character
  self-promotional video description and a professional-credentials bio;
  (Weeks 11-13, found by scanning the ~400-row dataset for anything
  containing sponsor/partner/collab/affiliate keywords, not just checking
  obvious cases) "in collaboration with" (event-hosting, must not match "in
  partnership with"), vague ongoing-relationship language ("a partnership
  that's..."), "was my sponsor" (personal patronage, wrong direction vs.
  "sponsored by"), "batting partner" (sports terminology).
- **Force-relabel behavior** (`test_labeling_router.py`): default mode
  skips already-labeled rows even if their text changed; `force=true`
  reprocesses and picks up the new text.
- Run against all real content in the live DB, re-run as new content
  landed and the target list grew: **695/695 rows checked as of
  2026-08-10 Weeks 14-16 round (up from 422 the prior round), 0 labeled
  sponsored, 0 confirmed false positives.**

See the "Kohli/Agilitas resolution" section above for the one open
precision/recall edge case and the documented reasoning for leaving it
`false` rather than guessing.

Text scrubbing (`app/text_processing.py::scrub_text` — URLs, HTML tags,
`@mentions` removed, whitespace collapsed) and temporal normalization
(`normalize_to_utc` — naive timestamps assumed UTC, aware ones properly
converted) also added this round (PROJECT_PLAN.md Section 2). Scrubbing is
wired into the feature store's `raw_text` staging; normalization is a
utility available for any datetime handling, though Postgres `timestamptz`
columns already normalize to UTC internally for anything already in the DB.

### Fusion Layer score (Track B → this API, now with honest GAIL spillover)

`POST /scores/compute`
```json
{ "creator_id": "758b86ea-266d-48dd-848e-564f47ad8275", "spillover_score": 0.6, "sentiment_risk_score": 0.7, "creator_feature_score": 0.5 }
```
`spillover_score` is now **optional** — if omitted, server auto-resolves via `app/spillover.py:get_spillover` (GAIL `load_predict` if `models/gail_checkpoint.pt` present, else `0.5` placeholder). Caller-supplied `spillover_score` still accepted for backward compat (basis then `placeholder`). `sentiment_risk_score` / `creator_feature_score` still required but `sentiment_risk_score` should be `0.5` (placeholder, Temporal 0% built `CAPSTONE_NEXT_STEPS.md:822`). All three must be finite `0-1` if supplied (NaN/Infinity 422).

Response `FusionScoreResponse` now includes `spillover_basis: "trained"|"inferred"|"placeholder"|"isolated"` + `confidence_low/high` reflecting honest small-N CI (see P1.6 section). `GET /scores/{creator_id}` recomputes live spillover (not stale DB row) — use it to see current basis/CI; it never 404s with placeholder — if no stored row it computes on-the-fly with `0.5` for `sentiment/creator_feature`.

Formula (`backend/app/fusion.py`, PROJECT_PLAN Section 4): `final = (w1*spillover + w2*sentiment + w3*creator)*100 + risk_adj`; `w1=0.4 w2=0.3 w3=0.3` still placeholder/un-calibrated — **only `w1` is now real** (GAIL c6488a6), `w2` stays `0.5` documented placeholder, not recalibrated. Confidence: `margin = hw*100*w1` where `hw` from `spillover.py` (`trained≈3.28, inferred≈5.25` on spillover scale → `±13/±21pts` on `final`), else fallback `±8`. Risk: `-10` if `sentiment<0.3` (still placeholder heuristic).

### Monitoring / alerts

`POST /alerts` (requires `X-API-Key` if configured) — body:
```json
{ "creator_id": "...", "severity": "high", "reason": "...", "source": "sentiment_propagation", "propagated_from_creator_id": null }
```
**`severity` is a strict enum** (`"low" | "medium" | "high"`) — Weeks
1-2 accepted any string; found via adversarial testing that this let
`"catastrophic_meltdown"` through undetected. Default `source="sentiment_propagation"`.

**`propagated_from_creator_id`** (nullable uuid, new Weeks 5-6): if this
alert exists because risk propagated from *another* creator's controversy
(PROJECT_PLAN.md Section 3b/5), that creator's id — added ahead of the
Weeks 14-15 Sentiment Propagation work landing so the shape is right when
Track D builds against it now, instead of forcing a second breaking change
later. Expect this to stay `null` until then.

`GET /alerts?creator_id=...&include_resolved=false` → list of alerts, newest
first (no auth required). This is what Track D's monitoring/alerts UI should poll.

### Auth (new Weeks 5-6)

Basic shared-secret auth via `X-API-Key` header, **off by default**. Set
`API_KEY` in `backend/.env` to enable — once set, all `/ingestion/*`
endpoints, `POST /scores/compute`, and `POST /alerts` require a matching
header (401 otherwise). Every `GET` endpoint and `POST /recommendations`
never require it — deliberately, since brand users and Track D's dashboard
need to read without a shared secret. This is intentionally minimal (one
shared key, no per-track keys or roles) — flagged as missing twice before
this, closing the basic gap rather than over-building auth for a 4-person
thesis capstone backend.

---

## Validation fixes (2026-08-09, found via adversarial self-check)

- **Fixed a 500 crash:** any request with `NaN` in a float field that has a
  `gt`/`ge`/`le` bound (e.g. `budget`, the three score fields) crashed with
  an unhandled 500 instead of a clean 422. Cause: Starlette's default JSON
  encoder for error responses is strict (`allow_nan=False`), but FastAPI's
  default validation-error handler echoes the raw invalid input back in the
  error body — trying to serialize a raw `NaN` float there raised
  `ValueError: Out of range float values are not JSON compliant`, unhandled.
  Fixed with a custom `RequestValidationError` handler in `main.py` that
  sanitizes non-finite floats before serializing (applies globally, not
  just to the field that surfaced it).
- **Fixed silent data corruption:** `budget: Infinity` previously passed the
  `gt=0` check (mathematically true) and then got silently serialized back
  as `null` in the response echo (Pydantic's default `Infinity`→`null` JSON
  behavior) — the client would see `"budget": null` with no error, hiding
  that an absurd value was accepted. Fixed with `allow_inf_nan=False` on
  `budget` and the three fusion score fields — both now cleanly rejected
  with 422.
- **Fixed a real ranking bug** in `/recommendations` (not just a validation
  gap): the Weeks 1-2 loop gated the FusionScore lookup on a single shared
  `is_mock_data` flag, so once *any* real creator was found to have no
  stored score, every creator *after* it in the loop silently stopped
  getting its real score looked up too (even creators that did have one).
  Split into `using_mock_creators` (fixed per-request) and
  `any_score_missing` (per-creator) so this can't happen.
- **Fixed a local-dev crash:** Track A's real schema has three Postgres-only
  `text[]` array columns (`creators.reddit_handles`,
  `youtube_videos.tags`, `instagram_posts.hashtags`). Declaring these with
  the plain Postgres `ARRAY` type meant those tables couldn't be created (or
  queried) at all against the SQLite local-dev fallback — `/recommendations`
  would crash with `OperationalError: no such table` instead of falling
  through to its mock-data path. Fixed with
  `.with_variant(JSON(), "sqlite")` so the same model works against both.
- **Fixed a validation gap:** `alerts.severity` was a freeform `str`
  despite being documented as an enum — tightened to
  `Literal["low", "medium", "high"]`.

## What's real vs. placeholder (as of 2026-08-26, P1.6 wired)

| Piece | Status |
|---|---|
| FastAPI app, all routes, request/response validation | Real, working |
| CORS | Real, confirmed by Track D in an actual browser — see incident above |
| DB models matching Track A's live schema (incl. `brands`, `creator_related_accounts`, `reddit_post_creators`) | Real, working (re-diff if their schema changes) |
| DB (SQLite local fallback / real Supabase Postgres via `DATABASE_URL`) | Both real and verified — connected to the live Supabase instance, 16 real creators / 422 content rows as of 2026-08-10 |
| Track C-owned table migrations (`fusionscore`, `riskalert`) | Real, tracked in `backend/migrations/` after the incident — no longer relying on `create_all()` for schema evolution |
| Ingestion upsert logic (8 endpoints) | Real, working, but secondary path (see breaking-change note #3) |
| Fusion formula math | Real formula, placeholder weights/risk-threshold/confidence-margin |
| Recommendation budget/region/demographic/product_category/platform_preference filtering | Fully real (see above), heuristic-based (placeholder cost rate, keyword-overlap text match) |
| Feature-store pipeline (`/feature-store/*`) | Real for numeric/categorical/collaboration/sponsorship edge data; collaboration edges **170 distinct pairs (340 directed edges)** as of Phase 1I, up from 10 after bulk sheet-backlog promotion — the earlier "structurally sparse" finding is retired, see Phase 1G section; `co_occurs_with` real but currently empty (Track A purged the noisy signal it was built from, self-healed automatically, see Weeks 11-13 note); CLIP/BERT embeddings intentionally not computed here (Track B); `reputation_score` is the one remaining genuine gap |
| **Disclosure-tag (`is_sponsored`) labeling pipeline** | **Real, run against all live data, genuinely multi-platform (confirmed by code read, not assumption). Sponsorship events: 61 (58 Instagram + 3 YouTube), up from 34, after Phase 1I's force-relabel at ~4x scale and manual correction of 5 confirmed false positives (4 Reddit, 1 Instagram — see Phase 1I section). Reddit's real yield is confirmed genuinely zero, not assumed. First fully-computable GAIL training pair confirmed real (mrbeast→CarryMinati), see Phase 1G section; 8 additional newly-sponsored, already graph-connected creators found in Phase 1I, not yet reflected in the orchestrator's 52-pair count — see that section.** 6,153/6,153 real rows labeled (1,594 YouTube / 1,811 Instagram / 2,748 Reddit) via `force=true`, incorporating Instagram's native `has_paid_partnership_label` signal (45 of 58 Instagram events caught at least partly by that signal; YouTube/Reddit have no native-signal equivalent, caught via plain regex only). Sponsorship *edges* (`/feature-store/edges/sponsorships`=16) reconcile exactly against the raw `brand_id`+`creator_id`-populated count — 45 of 61 events still lack `brand_id` (incl. the mrbeast milestone post), routine lag behind Track A's brand extraction, see Phase 1G/1I sections. Kohli/Agilitas edge case closed 2026-08-14, not reopened — see Kohli/Agilitas section |
| Text scrubbing / temporal normalization | Real (`app/text_processing.py`), Section 2 |
| Spillover (`spillover_score`) | **Real via GAIL checkpoint `c6488a6`** (`backend/app/gail/`, `backend/models/gail_checkpoint.pt`, `backend/app/spillover.py`): `trained` (N=10 labeled nodes, `mse 1.84 → hw 3.28 → ±13pts final`), `inferred` (`hw 5.25 → ±21pts`, 1.6× wider), `isolated`/`placeholder` (`0.5 ±10pts`, never crash). Falls back to `0.5` if checkpoint/torch missing. See P1.6 section. |
| Sentiment-risk (`sentiment_risk_score`) | **Still placeholder `0.5`** — Temporal branch 0% built (`CAPSTONE_NEXT_STEPS.md:822`), `w2` not recalibrated; only `w1` real. |
| Creator-feature (`creator_feature_score`) | Still `0.5` placeholder — CLIP/BERT not in this track. |
| Auth | Basic (shared `API_KEY`), off by default — see Auth section |

## Running locally

```
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```
Visit `http://127.0.0.1:8000/docs` for interactive Swagger UI. No `.env`
needed for local dev — defaults to `sqlite:///./fusion_backend.db` and now
creates the full local schema (including Track A-mirrored tables) so
`/recommendations` etc. work end-to-end without a real DB. Copy
`.env.example` to `.env` and set `DATABASE_URL` to connect to the real
Supabase instance — get the connection string from the user directly (never
committed, never in memory).
