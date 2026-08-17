# CAPSTONE — NEXT STEPS & LIVING STATE

**Read this first, every session.** This is the orchestrator's single source of truth for where
the project actually is, what's broken, and what remains between here and the thesis. It
supersedes memory when they disagree — memory is a pointer, this is the record.

Last verified: **2026-08-11** (live DB queried directly, all four worktrees inspected).

---

## 0. How to use this file

- **Start of session:** read this top-to-bottom before proposing anything.
- **Verify before trusting:** every number here was live-checked at the date above, but data
  changes daily. Re-query before acting on a specific figure. See §3 for how.
- **Update it:** when a problem is fixed or a phase completes, edit this file and commit. Don't
  let it drift — a stale plan is worse than none.
- **Ownership:** this file is the orchestrator's. Tracks have their own `HANDOFF.md` in their
  worktrees; those are per-track detail, this is the cross-project view.

---

## 1. What this project is

Influencer–brand matching for sponsorship decisions. A brand states product, budget, and target
region/demographic; the system returns ranked creators with a 0–100 score and an ROI breakdown.

The research contribution is **GAIL (Graph-Adaptive Interference Learning)** — a GNN with
attention that learns *personalised spillover weights* (when a brand sponsors creator X, how
much does collaborator Y benefit?) instead of hand-crafted rules like `spillover = 1/distance`.
Built on established components (GAT via PyTorch Geometric, propensity scoring, doubly-robust
correction, Laplacian regularisation, Granger causality) — a rigorous *application* of known
causal-ML methods to a novel domain, not new theory. That framing is deliberate and defensible;
don't let it drift back toward claiming proofs.

**Architecture:** Dual framework — a GAIL branch (spillover) and a Cross-Platform Temporal
branch (lag detection, sentiment propagation) → combined by a Causal Inference layer →
Fusion Layer (weighted 0–100 score + risk adjustment) → Application Layer (recommendations,
alerts, explainability graph).

### Timeline & milestones (confirmed with the user on 2026-08-11)

| Milestone | When | Requirement |
|---|---|---|
| **Review 1** | late Aug – early Sep 2026 | **≥50% complete, with working examples** — ~2–4 weeks away |
| **Review 2** | late Oct – early Nov 2026 | **80–100% complete** — ~11–13 weeks away |
| **Final submission** | late Nov – early Dec 2026 | Complete, **security fixes done, deployable** — ~15–17 weeks away |

**Deliverables:** source-code repo + thesis paper are **compulsory**. A live demo earns **extra
credit**. **Public deployment is explicitly out of scope until after submission** — the bar for
submission is *deployable* (Docker + security), not *deployed*.

The user's stance: *"don't worry about the deadline, work on it as much as we can."* Take that as
permission to prioritise depth over schedule anxiety.

**Review 1 bar, set by the user 2026-08-11: a basic demo with ~100 creators is sufficient.**
139 candidates already exist on the sheet, so this is comfortably reachable *without* changing
how data collection works. Explicitly:

> **Do not rush or compromise data collection to hit an earlier demo.** The user's position:
> *"better the data, better the model, better the project."* Review 1 is a checkpoint, not the
> goal. Quality of process — relevance verification, honest edge counts, no padding — takes
> precedence over demo timing. If a choice arises between a denser demo and cleaner data, choose
> cleaner data.

### Review-readiness criteria (added 2026-08-16) — raw volume alone does NOT satisfy any of these

This session's central lesson: creator count and row counts are *necessary but not sufficient*.
The real bottleneck at every stage has turned out to be structural (does an edge resolve, does an
event have `brand_id`, does a connected neighbor have pre-event history) — not volume. Check the
structural criteria before declaring a milestone's data "ready," not just the headline counts.

**Review 1 — "basic dry run," the bar for THIS check-in:**
- [x] ~100 creators (259, well past the floor)
- [x] **At least one fully computable training pair** — a sponsorship event that is BOTH
      graph-connected to another creator AND has pre-event data on that neighbor. **DONE
      2026-08-17**: mrbeast↔CarryMinati, independently confirmed three ways — see P0.4. Ideally
      grow past 1 (3-5) before calling this fully comfortable; one real example de-risks the
      pipeline, it doesn't validate a model.
- [x] Real collaboration edges comfortably above the old 10 pairs — now 161, from bulk-promoting
      the reviewed sheet backlog, not from coverage. See the retired P0.2 finding above.
- [ ] At least one creator with comment volume (Reddit/IG/YT) sufficient to sanity-check a
      sentiment/reputation signal, even if the full pipeline isn't built yet.

**Review 2 — "GAIL trains for real, fusion produces real scores":**
- [ ] Sponsorship events: 300+ (established Phase 2 target)
- [ ] Real resolved edges: 500+ (established Phase 2 target)
- [ ] A meaningful count of *computable* training pairs (connected + straddling) — dozens at
      minimum; re-derive this target once Review 1's actual resolve-rate is known, don't assume
      it scales linearly with event count given the structural sparsity already observed.
- [ ] Brands with real scraped profile data, not just mention-extracted names
- [ ] Comment volume sufficient to compute a real per-creator sentiment signal across most of the
      creator set, not just the best-covered few

**Submission — "complete, deployable":**
- [ ] Dataset stabilized (no active collection actively invalidating demo state during evaluation)
- [ ] Data supports both branches (GAIL + Temporal) for the full creator set or an honestly-scoped
      subset, stated plainly in the thesis rather than silently narrowed
- [ ] Limitations section grounded in what was actually found this project (observational data,
      disclosure-based treatment labels, structural graph sparsity, India-skewed sample,
      engagement-per-rupee not true ROI) — not a generic boilerplate list

---

## 2. THE CENTRAL PROBLEM — **caption cause RESOLVED, edge cause pivoted** *(updated 2026-08-11 post-Phase-1A)*

GAIL trains on `(sponsored creator → neighbour engagement change)` pairs, so the effective
sample size is **sponsorship events**, not creator count. For weeks the team optimised creator
count, which was never the binding constraint.

### ✅ Cause 1 — captions: FIXED, and the hypothesis was half-wrong

**The real root cause was simpler than assumed: one cause, not two bugs.** `parse_caption()` was
wired in at commit `8b493d1` (2026-08-10 01:19), but all 97 rows were fetched 2026-08-08 →
2026-08-09 — *entirely before it*. The scraper was already correct; **nothing ever re-scraped the
stale rows.** The two visible signatures were real but downstream of that one cause:
- 49 NULL captions correlate perfectly with `media_type IS NULL` (listing-sourced rows, empty
  metadata dict ⇒ every field None)
- 48 rows clipped at exactly 100 (`opencli instagram user` truncates at exactly 100)

*(Doc correction: this file previously cited lengths "101, 104" from an orchestrator sample.
Track A's analysis found a hard ceiling of exactly 100. The discrepancy is unresolved and
immaterial — the substantive finding, that truncation was deleting end-of-caption disclosures,
is confirmed by both.)*

**Verified live after the fix:** 60 non-null captions, 60 distinct, max 1058 chars, avg 257,
35 rows >100 chars. 37 remain NULL — see the open decision below.

**THE SIGNAL IS REAL.** Genuine disclosures now visible that truncation had destroyed:
`mirzasaniar` "…Milton, a brand that's Made in India… **#ad**" · `virat.kohli` "…@oakleymeta AI
glasses… **#Ad**" · `virat.kohli` "…**#Ad** #VisitDubai" · `neeraj____chopra` "After two seasons
as Ambassador… Co-Owner @ubsathleticskidscup". **Every one sits at the END of its caption** —
exactly where the 100-char cut was landing. This is direct evidence that "0 sponsorships" was a
scraping artifact. ⇒ **Scenario C is NOT triggered.** Honest read: *signal exists in ~5% of
captions, now needs Track C to re-label* — not "confirmed zero on good captions."

### ⚠️ Cause 2 — edges: table populated, but the assumed MECHANISM largely failed

`creator_related_accounts` went 0 → 1 row (1 resolvable edge: `virat.kohli` →
`royalchallengers.bengaluru`), written correctly with `relation_type='frequent_collaborator'`.

**But the team→player mechanism doesn't work as assumed.** Across 6 promoted team accounts, only
2 distinct handles were @-tagged in captions at all, neither an existing creator. **IPL/ISL team
accounts caption with hashtags, not player tags.** The single real edge came from a *creator's*
caption, not a team post.

**Best unexploited lead:** Instagram's **collab co-author list** ("X and N others"), rendered in
the page markdown — a genuine, native collaboration fact rather than an inferred one. Track A
deliberately did not build it rather than ship a second unvalidated mechanism in one round.
Also worth checking: Instagram's **"tagged people"** on posts, which is separate from caption
@-mentions and may be where teams actually tag players.

### ✅ RESOLVED 2026-08-11 — the 37 NULL captions were COLLAB POSTS, not contamination

Track A settled this with three independent lines of evidence from real post pages. The decisive
one: on `virat.kohli`'s live grid, **5 of 7 NULL-caption posts were still present — a higher hit
rate than with-caption posts (19 of 33)**. Contamination would show the opposite (absent from the
grid). Also: 11 of 18 probed posts showed the stored creator's handle in the co-author header
block, and zero showed the pure-contamination signature.

⇒ **Keep them.** On a collab post the caption belongs to the primary author, so a parse anchored
to the stored creator correctly returns nothing. Recovering them took captions from 60 → 82
non-null (82/82 distinct, max 1142).

**Bonus finding, unprompted and important:** 3 posts carry Instagram's native **"Paid
partnership" label**, rendered on the page but entirely absent from caption text. **A
caption-only labeler structurally cannot see this** — and it's Instagram's own declaration, so
likely the highest-precision sponsorship signal available. `instagram_posts` has no column for
it ⇒ **the project's first genuine schema addition.** Split: Track A adds/populates a raw
observation column (`has_paid_partnership_label`), Track C reads it when computing `is_sponsored`.

### ⚠️ Instagram rate limit hit 2026-08-11 (HTTP 429)

Self-caused and the arithmetic is clear: ~9h discovery loop + 97-post caption backfill + 97-post
collab pass (~200 post-page fetches in a few hours) + pilot. Affects **any** handle including a
control. Categorically different from the intermittent `HTTP 400 - make sure you are logged in`
seen all session.

**Diagnostic from the user: they can browse Instagram normally, logged in as the same account in
the same browser.** ⇒ rate-based throttle on the automation's request pattern, not an
account-level block — the recoverable kind. Response: wait, probe with a *single* call, and
follow `agent-reach`'s documented limits (`.agents/skills/agent-reach/references/social.md`)
rather than an ad-hoc strategy.

**Consequence for planning:** Instagram is both the slowest platform *and* the only one carrying
caption/collab/paid-partnership signal. Deepening all 55 on Instagram is not feasible before
Review 1 — the binding constraint is the rate limit, not time. Agreed plan: **YouTube across all
55 now** (API-based, unlimited, descriptions never truncated — also the Scenario-D fallback),
**Reddit second** unattended over days (~7.7 min/creator), **Instagram last** on ~15–20
high-signal creators with a hard per-day request budget. Depth of signal beats breadth.

### 🔗 Co-author handling — curation, not auto-promotion *(decided 2026-08-11)*

The collab extractor works, but from a 10-post sample it surfaced **18 distinct real co-authors
and zero were existing creators**, so they resolve to nothing. Many are orgs/brands/politicians
(`commonwealthsport`, `globalboxingseries`, `naralokesh`) — bulk-promoting them would pollute the
creator set and re-import the #fitindia-collision problem.

**Decision:** discovered co-authors go to the **Google Sheet as candidates for user review**,
through the existing curation flow, with provenance in `notes` and signals in the new
`brand_signals` column. Approved → promoted → the edges light up.

**Key mechanic Track A initially missed:** relationship rows should be written **immediately**
even when the co-author isn't a creator yet. Track C's resolver matches handles *at resolution
time*, so an unresolvable row costs nothing, is silently skipped, and **auto-resolves the moment
the co-author is promoted** — no re-scrape needed. Since these facts cost rate-limited Instagram
fetches to obtain and are nearly free to store, write them all. Report **rows written and
resolved separately**; they will now differ, which is correct rather than a problem.

### 🔗 Possible link between the two gaps — worth checking early
The 37 still-NULL captions are posts on a creator's grid authored by *someone else* (e.g. on
`kingjames`: `sixers`, `ljfamfoundation`, `chrisjohnsonhoops`). Two very different explanations,
with opposite implications:
- **Instagram collab posts** — co-authored, legitimately appear on both grids ⇒ **these ARE the
  collaboration edges we're missing**, and the NULL captions are a symptom of a signal we want.
- **Scraper contamination** — suggested/unrelated posts wrongly attributed ⇒ **bad data that
  inflates a creator's content count and could cause false sponsorship attribution**, and should
  be removed.
Distinguishing these is high-value and cheap. Do it before deciding what to do with the 37 rows.

---

## 3. Verified reference data (re-check before relying on it)

### 3.1 How to query the live DB (orchestrator can do this directly)

```bash
K="<publishable key — see §3.4>"
curl -s "https://fhbgbtxdtfluzohxyivg.supabase.co/rest/v1/<table>?select=*&limit=5" -H "apikey: $K"
# row count:
curl -s ".../rest/v1/<table>?select=id" -H "apikey: $K" -H "Prefer: count=exact" -H "Range: 0-0" -D - -o /dev/null | grep -i content-range
```
No `psycopg2` in the orchestrator env; REST is the route. **Read-only in practice — never write.**

### 3.2c Live DB state — **Track A verified 2026-08-16, close of Phase 1G** (NEWEST — supersedes 3.2a/3.2b for creators + edges)

| Table | Rows | Note |
|---|---|---|
| `creators` | **259** | was 63. Bulk promotion of 258 accepted sheet rows: 196 new, 60 enriched, **0 duplicates/collisions** |
| `creator_related_accounts` | 505 rows / **157 resolved** / **152 DISTINCT PAIRS** | was 15 resolved / 10 pairs. **No new scraping** — the same 505 rows resolve now that the endpoints are creators |
| Resolve rate | **31%** | was 2.4% |
| Creator categories | athlete 95 · fitness_influencer 82 · lifestyle_influencer 38 · team 20 · other 15 · league 9 | 132 of 146 `other` sheet rows were misclassified and corrected |
| Sheet | 994 rows | 258 accepted / 230 rejected / 506 not-decided. `approval_status` untouched by agents |
| IG coverage | 31 of 259 creators | **228 creators now have no Instagram content** — deepening is the gap |

🚨 **THE "STRUCTURALLY SPARSE GRAPH" FINDING IS OBSOLETE — Tracks B and C must be told.**
Both recorded "10 pairs / 2.4% resolve rate, structurally sparse, not a coverage gap" as a
settled property. It was true *of the 63-creator set* and is now **152 pairs at 31%**. The
graph was never structurally sparse; its endpoints simply weren't creators yet. Track B in
particular planned its first training run around a 10-pair graph.

**What this round proves about the lever** (Phase 1F predicted it; this confirms it at scale):

| Action | Distinct pairs added |
|---|---|
| Covering 7 new creators (Phase 1F — 275 posts scraped) | **0** |
| Promoting 196 already-observed co-authors (this round — no scraping at all) | **+142** |

⚠️ **Brands found accepted on the sheet, excluded from promotion and flagged for the user:**
`sporting.beyond` ("Sporting Beyond Pvt Ltd", a company — **already in `creators`** from a
Phase 1E targeted promotion and carrying a live resolved edge, so it was left in place rather
than deleted) and `sportsclaus` (sports media company). Agents **cannot** auto-reject these:
`approval_status` is the user's column. The brand is instead recorded against the creator it
was seen on via `brand_signals`. Note `brand_signals` is **live on the sheet now** — §3.4
below still calls it "TO ADD", which is stale.

### 3.2a Live DB state — **Track A verified 2026-08-15, close of Phase 1F** (superseded by 3.2c for creators/edges)

| Table | Rows | Note |
|---|---|---|
| `creators` | **63** | +3, all targeted promotions naming the row each resolved |
| `creator_related_accounts` | **505 rows / 15 resolved / 10 DISTINCT PAIRS** | **report pairs.** 15 resolved rows include reciprocal directions of the same collaboration; deduplicate with `least(name)/greatest(name)` |
| `instagram_posts` | **1,092** | 31 of 63 creators covered (was 24). **120 unscanned** — a throttle stopped the scan |
| `instagram_comments` | **13,097** | +1,546 |
| `has_paid_partnership_label` true | **12** | +1; Track C's highest-precision sponsorship signal |
| `is_sponsored=true` / with `brand_id` | 11 / 9 | unchanged — Track C hasn't relabelled the new posts yet |
| `brands` | 10 | unchanged |
| Sheet | 488 rows / 131 accepted | grown by co-author candidate pushes |

**Pairs added this round: 7 → 10. All 3 from targeted promotion; 0 from covering 7 new
creators.** That is the second independent confirmation that coverage does not add graph
structure — see the P0.2 rewrite above.

### 3.2b Live DB state — **Track C verified 2026-08-15, Phase 1F re-labeling** (newest; supersedes 3.2a's labeling row)

| Table | Rows | Note |
|---|---|---|
| `creators` | 63 | unchanged this round |
| `creator_related_accounts` | 505 rows / 15 resolved / 10 distinct pairs | unchanged; independently reproduced a third time (Track A → orchestrator → Track C, all match). API returns 20 edges = 2 directed edges per pair, not 20 relationships — documented for Track B. |
| `instagram_posts` | 1,092 | unchanged this round |
| `is_sponsored=true` (all platforms) | **18** | +7, all Instagram, 0 YouTube/Reddit. Force-relabel (`?force=true`) caught the 267 posts Phase 1F scraped that a default run would have skipped (they default to `is_sponsored=false`, not null). 13 via caption regex, **5 via `has_paid_partnership_label` only** — including one post with a still-empty caption, the case text-only labeling structurally cannot reach. |
| `is_sponsored=true` with `brand_id` | **10 of 18** | was 9 of 11. `/feature-store/edges/sponsorships` reconciles exactly against this raw count — zero gap between endpoint and data. 8 of 18 still lack `brand_id` — Track A's brand extraction lagging one round behind labeling, expected/routine. |
| `brands` | 10 | unchanged |
| Sheet | 488 rows / 131 accepted | unchanged this round |

**Collaboration graph is now a confirmed structural property, stated for Track B's benefit before
it starts training: 10 real pairs across 63 creators, ~2.4% resolve rate.** Not a bug, not a
coverage gap — verified twice more this round (Track A's scan of 267 new posts added 0 pairs;
Track C reproduced the resolver's own logic directly against the DB and got the identical count).
Track B should expect a small, sparse, but genuinely real graph on its first training attempt.

### 3.2 ~~Live DB state — orchestrator-verified 2026-08-14 after Phase 1E~~ (SUPERSEDED by 3.2a)

| Table | Rows | Note |
|---|---|---|
| `creators` | **60** | +4, all targeted promotions that each immediately resolved a specific pending edge (see P0.2) |
| `creator_related_accounts` | **316** | **10 resolved** (independently re-derived by the orchestrator via handle cross-reference, matches Track A's own count exactly) |
| `instagram_posts` | **825** | 24 of 60 creators now have IG content (was 13). 359 of the 424 new posts were never scanned for co-authors — see throttle note below. |
| `is_sponsored=true` (Instagram) | **11** | unchanged this round — expected, the new posts weren't scanned |
| `is_sponsored=true` with `brand_id` set | **9 of 11** | was 1 of 11. Root cause: extractor only matched explicit phrases; the dominant real pattern is a branded hashtag/@mention, which had no rule at all. 2 left deliberately unlinked (ambiguous/empty caption) rather than guessed — correct call given this is the sole treatment-label source. |
| `brands` | 10 | +1 since the report was written (`optimumnutri`) — background movement, not an error |
| Reddit co-occurrence | **0, confirmed structural not a bug** | 435 `reddit_post_creators` rows = 435 distinct posts, perfect 1:1. 427 of 435 rows belong to 5 creators; 8 of 13 have exactly 1 row each. Each post is found via a single creator's search, so overlap can't occur without two creators being searched in the *same* subreddit. More per-creator scraping won't fix this — needs a shared-subreddit search strategy, a deliberate mechanism decision. |
| Sheet | — | 112 of 116 approved rows deliberately NOT promoted (would add creators without adding training pairs) — see the targeted-promotion rule below |

All figures re-verified directly via REST by the orchestrator, independent of Track A's own
report — every number matched exactly except the `brands` count noted above.

**⚠️ New standing rule — never approve brand/company accounts on the sheet.** Brands
(e.g. Milton, One8) reach the `brands` table automatically via disclosure-text extraction on
sponsored content — never via the creator-promotion path. Approving one as a creator would (a)
have no valid `category` value and (b) let it resolve into `creator_related_accounts` as a false
"collaboration" edge, corrupting the sponsorship/collaboration distinction GAIL depends on. The
targeted-promotion mechanic (below) does NOT filter brand vs. person — user review is currently
the only safeguard.

**⚠️ Targeted-promotion rule (in effect since Phase 1E):** do not bulk-promote approved sheet
rows. Promote a candidate ONLY if their handle already appears in an unresolved
`creator_related_accounts` row — i.e. promoting them immediately resolves a specific known edge.
Report which row each promotion resolved. This is deliberate: general creator growth doesn't
help Track B until it produces a training pair.

**⚠️ Instagram throttle — real finding, and a verification-method lesson.** Not a 429; it's a
network-layer `chrome-error://chromewebdata/` failure that a 429-keyed check doesn't catch. A
**single-request probe after stopping is not a valid clearance test** — Track A confirmed
recovery with 3 passing single checks, then sustained scanning re-tripped it in 4 posts (~45s).
Needs a real cooldown (hours, not minutes) before the next sustained scan. Recorded in Track A's
HANDOFF.md as a standing lesson, since the same flawed single-probe method was used on the
earlier 429 too. The consecutive-failure abort caught the re-trip in 48s instead of ~54 minutes —
keep that mechanism.

**~~Outstanding, highest priority for the next Track A round:~~ DONE 2026-08-15 — and the
answer was NO.** The 359 posts were scanned (0 failures, 70 min); the throttle had genuinely
cleared, verified by a **sustained 12-request test** rather than the single probe that misled
the previous round. Resolved edges did **not** grow super-linearly — they did not grow at all
(316 → 423 rows, RESOLVED 10 → 10). Track A's own prediction is now **disproven, not
untested**. See the P0.2 rewrite above; do not re-open this as an open question.

**⚠️ Process incident, 2026-08-14:** the orchestrator edited this file after Phase 1C but never
committed/pushed it — Track A's Phase 1D round pulled `origin/main` and correctly found no trace
of Phase 1C content (still at commit `70cab91`). Not a Track A bug. **Lesson: this file is
useless to the other three track sessions unless it's actually pushed, every time.**

**Instagram grid-stall — characterized, one real bug fixed, root cause still open.** Byte-identical
failure sequence reproduced across Aug 11/Aug 12 logs; ruled out (with evidence, not assumption):
positional degradation, rate-limiting/time-of-day, account size. Isolated to the browser-driven
grid path specifically (`opencli instagram user` never failed in 3 days; only `browser open` →
`find --css` returns nothing). **Fixed:** a real tab-lease leak — `process_creator`'s
no-post-links raise sat before its session close, leaking up to 8 sessions/tabs per bad run.
Fixed on that path + a deterministic-name backstop in `run_batch`'s except. **Not yet proven** to
be the actual cause of the stall (that's a hypothesis pending re-measurement) — the discriminating
test is queued: run a consistently-failing creator (`cristiano`) alone as the first call of a
fresh session. Aug 13's 5×30s timeouts are a separate bug, recorded separately, not conflated.

⚠️ **Incident 2026-08-11, resolved:** Track A's first backfill auto-detected each post's author
instead of anchoring on the known username. Instagram post pages render *suggested* posts, so it
frequently grabbed a different post's author and caption — writing wrong captions to ~33 of 97
rows. Caught via distinctive signature (94 rows carrying only 61 distinct captions; one post_id
reporting two different authors across runs). Cleared and rebuilt with anchored parsing plus a
URL assertion. **Verified clean: 60/60 distinct.** Root enabler, in Track A's own words: `extract`
returns a `url` field that was never checked against the requested post — a violation of this
project's own "verify data arrived, not that code ran" rule, *while fixing an instance of that
same rule*. Both a good catch and a standing warning.

### 3.3 Schema — 13 tables + 1 view. **No schema changes needed.**

Every table, FK and `brand_id` column the model needs already exists. The gap is population,
not design.

**`creators`** (seed table)
`creator_id uuid PK · name · category · youtube_handle · instagram_handle · reddit_handles text[] · notes · created_at · updated_at · reddit_topic_subs text[]`
- ⚠️ **`category` has a CHECK constraint** — only: `athlete, team, league, fitness_influencer,
  lifestyle_influencer, other`. Any invented value hard-fails the insert.
- ⚠️ **No `follower_count` column.** It lives on `instagram_profiles.follower_count`.
- `reddit_handles` = creator-SPECIFIC subs (safe to take feed broadly).
  `reddit_topic_subs` = general/topic subs (must be name-searched, never taken as a whole feed —
  taking them broadly produced ~3,000 rows of noise and an 88% purge).

**`creator_related_accounts`** (collaboration edge source)
`id · creator_id→creators · platform CHECK(youtube|instagram|reddit) · handle text · relation_type text · created_at · UNIQUE(creator_id, platform, handle)`
- ⚠️ **`relation_type` must be exactly `"frequent_collaborator"`** — Track C's
  `build_collaboration_edges()` filters on that literal string and silently ignores anything else.
- ⚠️ **Both endpoints must already exist as `creators` rows.** The resolver matches `handle`
  text against other creators' own handles and silently skips unresolvable rows. Promote players
  to `creators` *before* writing relationship rows, or you get zero edges with no error.
- ⚠️ Resolver drops **ambiguous handles** (2+ creators claiming the same one). Duplicate rows
  both claiming reddit handle `"lebron"` are **still live in prod** — those creators will
  silently yield no edges until merged.

**`brands`**
`brand_id uuid PK · name (UNIQUE) · category · youtube_handle · instagram_handle · reddit_handle · follower_count · post_count · is_verified · source (default 'sponsorship_mention') · fetched_at · created_at · updated_at`
- ⚠️ **Documented scope boundary:** populated ONLY from brand names extracted from
  sponsorship-disclosure text on creator content — explicitly *"not an independent brand-discovery
  crawl."* The `source` column exists for if that changes. If brand-anchored discovery is ever
  used, use a **distinct source value** (e.g. `'brand_account_discovery'`) and note it in
  SCHEMA.md — Track B needs to distinguish provenance, because crawled brands have real profile
  data while mention-extracted ones have only a name.
- ⚠️ **There is no creator↔brand table.** The relationship exists ONLY as `brand_id` on content
  rows (`youtube_videos`, `instagram_posts`, `reddit_posts`). A brand's own posts have nowhere to
  live (brands aren't creators). So brand-anchored discovery can only be a *creator-discovery*
  mechanism; sponsorship linkage must come from the creator's own content.

**Platform tables:** `youtube_channels/videos/comments`, `instagram_profiles/posts/comments`,
`reddit_profiles/posts/comments`, `reddit_post_creators` (junction).
- `instagram_profiles` PK is `username`, `creator_id` FK is **nullable** — it holds comment
  authors too. Don't clobber `creator_id=null` rows; they're deliberately lean.
- `is_sponsored` / `sponsorship_raw_matches` on content tables are **Track C's** to populate.
- `is_bot_flagged` / `bot_score` are **Track B's** to populate.

**View:** `creator_sponsorship_events` — UNION of `is_sponsored=true` rows across all three
platform tables, carrying `brand_id`. Track B builds sponsors/sponsored_by edges from this.

**Migrations (6, in `supabase/migrations/`):** `init_schema`, `fix_missing_reddit_indexes`,
`add_brands`, `dedupe_creators`, `reddit_post_creators_junction`, `reddit_topic_subs`.
Live DB agrees with them.

### 3.4 Google Sheet (curation surface)

<https://docs.google.com/spreadsheets/d/1UX9K3gQnh4roMgTi0cy3Sxm82kTLDkZI9w4jJELFVPQ/edit>

Columns: `name · approval_status · category · youtube_handle · instagram_handle ·
follower_count · reddit_handles · notes · reddit_topic_subs`
- **`approval_status`** is the user's column — values `accepted` / `rejected` / blank. **Agents
  must never write to it.** Anything not exactly `accepted`/`rejected` = unreviewed.
- **TO ADD: `brand_signals`** — brands tagged in bio, discount codes, paid-collab language.
  Free to capture (the bio is already read for the relevance check) and predicts which creators
  will actually yield sponsorship events. Track A adds this via its Sheets API access.
- ⚠️ Sheet has **no `creator_id`** — promote must match on handle.
- ⚠️ Sheet sometimes holds data the DB lacks (e.g. `athleanx` has an instagram_handle on the
  sheet, NULL in DB) ⇒ promote is an **upsert**, not insert-only.
- ⚠️ Known glitch: row `nisha_optimist` has its own username in `approval_status`.
- Current: 139 rows — **19 accepted, 4 rejected, ~116 unreviewed.**

### 3.4b ⚠️ `DATABASE_URL` CHANGED 2026-08-14 — affects all four tracks

If `psycopg2.connect()` starts failing with
`could not translate host name "db.fhbgbtxdtfluzohxyivg.supabase.co" to address`, **the
project is fine and the password is fine.** Supabase's *direct* connection host is
**IPv6-only** (AAAA record, no A record), and the dev machine lost its IPv6 route — a direct
IPv6 TCP connect returns `WinError 10051, network unreachable` while every other hostname
resolves normally.

**Fix — a one-line DSN swap to the IPv4 session-mode pooler** (note the `postgres.<ref>` user):

```
DATABASE_URL=postgresql://postgres.fhbgbtxdtfluzohxyivg:<pwd>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

Verified by Track A 2026-08-14 (`select count(*) from creators` → 60, matching the last
known-good figure). Applied to Track A's `.env`; **B, C and D must make the same change in
their own gitignored `.env` files** — this is per-worktree config, not something a commit
propagates. Keep the old direct line commented for when IPv6 returns.

Lesson worth keeping: "host not found" was neither a DNS outage nor a credentials problem —
the name resolved fine, just to an address family with no route. Check the DNS *record type*
before concluding a service is gone.

### 3.5 Environment / access

| Thing | Detail |
|---|---|
| Supabase project | `https://fhbgbtxdtfluzohxyivg.supabase.co` |
| Credentials | In each track's gitignored `.env`. Password was pasted in chat 2026-08-11 — **should be rotated.** |
| Repo | `github.com/akshatnavlani/Capstone`, `main` + 4 track branches |
| Worktrees | `D:\Capstone-worktrees\track-{a-data-infra, b-ml-core, c-fusion-backend, d-frontend-app}` |
| Apify | **Genuinely unavailable** — checked across 3 restart cycles. Stop re-checking. |
| Docker | Installed, verified working (non-standard path: `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe`) |
| claude-in-chrome | Works in Track D. Diagnostic use only — it competes with OpenCLI for the browser. |
| Scraping | YouTube = official Data API (no contention). Instagram + Reddit = OpenCLI browser automation. |

### 3.6 ⚠️ Parallelisation rule (confirmed by a real incident)

OpenCLI arbitrates browser access via **tab leases from one daemon per Chrome profile**.

| Combination | Safe? |
|---|---|
| YouTube ∥ anything | ✅ independent transport (plain HTTP API) |
| Instagram ∥ Reddit | ❌ **starved Reddit completely** (0 of 8 creators) |
| Any two OpenCLI platforms | ❌ same mechanism |
| Two sub-agents ∥ same platform | ❌ same session, same rate limit |

**Safe pattern:** one sub-agent for YouTube, one doing Instagram→Reddit *sequentially*.

---

## 4. Track ownership (verified in code — don't blur these)

| Layer | Owner | Where |
|---|---|---|
| Scraping, DB population, raw relationship data | **A** Data/Infra | `scripts/ingestion/orchestrator.py`, `supabase/migrations/` |
| Edge *resolution* (DB rows → weighted edge lists), disclosure labeling, feature store, fusion scoring, API | **C** Fusion+Backend | `backend/app/feature_store.py`, `labeling`, `fusion.py` |
| Graph *construction* (edge lists → PyG HeteroData), GAIL, bot detection, CLIP/BERT | **B** ML-Core | `ml/schema.py`, `ml/gail_model.py`, `ml/training.py` |
| UI, explainability graph, Docker, browser verification | **D** Frontend+App | `frontend/` |

**Track A does NOT build the graph.** It collects relationship *facts*. C resolves them into
edges. B builds the tensor and trains.

---

## 5. PROBLEMS — ranked, with fix ideas

### P0 — blocking the thesis's core claim

**✅ P0.1 Captions — DONE 2026-08-11.** Root cause was stale rows never re-scraped after the
parser fix landed, not two separate bugs. Backfilled; 60 distinct captions, real disclosures
recovered. See §2.

**✅ P0.2 — RETIRED 2026-08-16/17. The graph was never structurally sparse — its endpoints
just weren't creators yet.** Everything below (2026-08-15) was a real, correctly-verified
finding *of the 63-creator set at the time* — but it was a snapshot of an unpromoted graph,
not a structural ceiling, and the next round decisively disproved the "sparse" framing rather
than confirming it further.

**What actually happened:** the user reviewed the full sheet backlog (258 accepted, 230
rejected — every row actually looked at). Bulk-promoting those 258 candidates converted
**142 previously-dangling `creator_related_accounts` rows into real resolved pairs, using
zero new scraping** — the rows already existed, their endpoints just weren't `creators` yet.
Resolve rate: **2.4% → 31%** (157 resolved rows / 505 total, independently re-derived by the
orchestrator and matched exactly: 152 distinct pairs, up from 10). Compare: covering 7 new
creators the round before produced 0 new pairs. **Promotion, not coverage, is the lever —
confirmed decisively now, not just theorized.**

⚠️ **Tracks B and C both built on the old 10-pair figure as a settled structural fact** — Track
B specifically planned its first real training run around "expect a small, sparse graph."
That plan needs correcting directly, not just via this doc update — both tracks should be told
this explicitly before doing anything further with the collaboration graph.

**Real bug found in the same round, still unfixed in code (data-only patch applied so far):**
`collab_edges.py`'s co-author-push path hardcodes `category: "other"` for every handle it adds
to the sheet (no bio available at push time to classify on), and `discover_candidates.py`
applies one `--category` hint per whole run rather than per-account. 146 of 258 accepted rows
were sitting at `category=other` because of this — traced with hard evidence (144 of 146 carry
co-author provenance, the only 2 exceptions are pre-existing dead-handle rows). Fixed
*retroactively* for those 146 rows (132 corrected, 13 genuinely `other`, 1 excluded as a
brand) via a new bio-reading `sheets_sync.update_category()`. **The code paths that caused it
are unchanged** — any further co-author-push or discovery run will recreate this exact problem
until the underlying functions do per-account classification at write time, not after.

⇒ Coverage still retains independent value (datapoints, captions, sponsorship events for
Track C) — just isn't the graph-density lever. The remaining lever, now proven not just
theorized: continue surfacing dangling co-author handles (collab_edges.py, now the
highest-confidence discovery mechanism available — it finds people already observed
collaborating with a creator, not merely predicted to) and get them through user review. The
bridge-queue framing (only 13 of 398 dangling handles referenced by 2+ creators) is superseded
by this — promotion converted far more than 13 dangling rows once bulk-authorized. Original
bridge-queue text, kept for the record, follows:

*Superseded text follows, kept for the record:*

~~Do not fund another round of Instagram coverage expecting resolved edges to move.
Coverage retains independent value (datapoints, captions, sponsorship events for Track C),
just not this one. The graph-density lever is the bridge queue: only 13 of 398 dangling
handles are referenced by 2+ distinct creators, and those are the only promotions that link
two covered creators rather than adding a leaf. Detail and the ranked list with brand
exclusions are in Track A's HANDOFF.md §3 (Phase 1F).~~

~~Track B should plan for a sparse collaboration graph. 2.4% of edge rows resolve; this
is a structural property of the curated set, not a collection bug.~~

*Also superseded, from the round before that:*

**~~P0.2 Collaboration edges — mechanism now works, bottleneck is Instagram coverage, not
extraction~~** *(Track A → C → B)* Team→player tagging is confirmed dead (IPL/ISL accounts caption
with hashtags). Its replacement — Instagram's collab co-author list — works and produced 72 edge
rows, but only 2 resolve, because resolving requires BOTH co-authors to already be creators with
Instagram content, and only ~9-12 of 56 creators currently have any `instagram_posts` at all. The
real lever now is Instagram coverage breadth (getting more creators past the grid-stall and
scraped at all), not further edge-mechanism work. 67 co-author candidates are on the sheet
awaiting user review — promoting them will raise resolved count once they have Instagram content
of their own.

**✅ P0.3 Promote-to-DB — DONE 2026-08-11.** `creators` 16 → 55, upsert semantics correct
(`athleanx` gained the instagram_handle it had on the sheet but not the DB — exactly the case
insert-only would have missed), 0 duplicates, `approval_status` untouched.

**✅ P0.4 — RESOLVED 2026-08-17. The first fully-computable GAIL training pair is real,
independently confirmed three separate ways.** Not "should become real" — actually real, as of
Track C's Phase 1G relabel:

| Condition | Status |
|---|---|
| Treatment event correctly labeled | ✅ `Db5rzczsSV5` (mrbeast, 2026-08-12), `is_sponsored=true` via native `paid_partnership_label` signal (caption's `#oldnavypartner` hashtag isn't a pattern the regex labeler catches on its own — the native signal is exactly why it exists) |
| Real graph connection | ✅ mrbeast ↔ CarryMinati, resolved collaboration edge, both directions |
| Neighbor data straddles the event | ✅ CarryMinati: 11 dated posts before (through 2026-08-08), 1 after (2026-08-13) |

Verified independently three times: Track A found it and reported the raw numbers; the
orchestrator opened CarryMinati's live Instagram grid directly (via the accessibility tree, not
just a screenshot) specifically to rule out the pinned-post metadata bug Track A flagged the same
round, and found no pinned posts — the date data is trusted; Track C confirmed the label and the
edge from its own side independently. `brand_id` is still NULL on this post (no "Old Navy" row
exists in `brands` yet) — **this does not block the milestone**, since P0.4's actual definition
is graph-connection + straddling data, not brand identification. Brand linkage is Track A's
extraction to close when it gets to it, separately.

⇒ Track B is unblocked to attempt a real training run with an actual computable example, not a
placeholder target. One real pair is not enough to validate generalization — treat the first
real run as a pipeline-correctness check (does it run end-to-end on real data, no NaN/crash),
not a trained model. The collaboration graph is also no longer what it was — 161 distinct pairs,
not 10 (see the retired-finding note above) — so the graph Track B builds against now looks very
different from its first attempt.

*Superseded text follows, kept for the record:*

~~Sponsorship events — signal confirmed, labeling pending~~ *(Track C, now unblocked)*
~~Still 0 in the DB (`is_sponsored` is Track C's to populate) but ≥4 genuine disclosures are now
present in real captions. Track C's re-label is the immediate next step, and those 4 known
disclosures are a concrete validation target — if the labeler misses them, that's a labeler bug,
not an absence of signal.~~

**⚠️ P0.5 — RESCOPED 2026-08-18, more serious than previously recorded.** The user's own instinct
("YT/Reddit deepening feels incomplete") was correct and the orchestrator quantified it directly
against the live DB: of 259 creators, **257 (99.2%) have an Instagram handle, but only 11 (4.2%)
have a YouTube handle on file**, and only **10 creators (3.9%) have any YouTube content at all** —
the same small original set from early phases, untouched since bulk promotion grew the creator
set 63→259. Reddit has content for 13 creators (5.0%, mostly via the topic-sub name-search
mechanism, which doesn't strictly need a discovered handle) but the pattern is the same: the
240+ bulk-promoted creators have essentially never had YouTube or Reddit attempted at all.

This is primarily a **YouTube discovery gap**, not a deepening-capacity problem — almost nobody
has a handle to deepen in the first place. Fix: search for each handle-less creator's actual
YouTube channel (by name/known aliases) and populate `youtube_handle` before attempting any
video fetch. Once found, YouTube deepening is safe to run **in parallel with Instagram** (official
API, no shared browser resource — confirmed safe per §3.6). Reddit's topic-sub search needs to run
for the same 240+ creators, but must run **sequentially after Instagram**, same tab-lease
constraint as always.

**✅ Progress 2026-08-18** — YouTube: 45 auto-matched handles caught and audited before sticking
(3 successive verification-rule failures found and fixed: circular self-match, corroboration-only,
namesake collision); 9 genuine handles applied, 36 `needs_review`, 44 confirmed absent. 89 of 248
searched, quota-capped (100 units/search, 10k/day budget) — expected to span several more rounds.
Instagram: blocked on a sustained 429 (3 consecutive after ~3.5h) — real, not a false alarm from
`opencli doctor` misreading a disconnected daemon as a throttle (checked separately, cause
confirmed distinct). Reddit: root cause found, not just a symptom — bulk promotion set
`creators.name = instagram_handle` for **231 of 264 creators** (topic-sub search queries by
`name`, so a handle-shaped name returns 0 results — proven directly: `"rohitsharma45"` → 0
results, `"Rohit Sharma"` → 10). 13 real names already recovered at zero network cost from
`instagram_profiles.full_name` / `youtube_channels.title`. **Real-name backfill for the remaining
231 is now the actual blocker for all Reddit work**, not a Reddit-side problem — flagged as the
next Track A priority given it's foundational (also likely affects any other name-based matching,
not just Reddit).

**⚠️ Incomplete cleanup, found by the orchestrator, not self-reported.** A separate bug this
round (`--platform reddit --handles <ig_handle>` treating an Instagram handle as a subreddit) was
caught and the `reddit_handles` pollution was cleaned — but the bug's `get_or_create_creator`
path had already created 5 new, fully blank creator rows (name only, no platform handles at all:
`delhipremierleaguet20`, `karanaujla`, `ptushaofficial`, `gujarat_titans`, `ajinkyarahane` — all
created at the identical timestamp 2026-08-17 19:46:58, all bridge-queue-shaped names). These
were never deleted — `creators` is 264 live, not 259. Needs a real DELETE, not just a field
cleanup, next round.

### P1 — blocking scale or quality

**P1.1 Discovery ceiling** *(Track A, Phase 2)*
Tag pages return 3–8 links regardless of requested cap ⇒ hashtags max out ≈213 candidates ever.
Fix: follower-graph expansion as primary (similar-accounts suggestions first, then *following*
lists slowly — elevated ban risk), team-roster extraction, brand-anchored discovery, and finally
*actually test* multi-word keyword search (never tried; one generic single-word test was
over-generalised across 25 cycles).

**P1.2 No content-relevance verification** *(Track A)*
Candidates were judged on bio keywords + follower count only; the post grid was never opened.
Accounts with 2 domain posts and a "certified coach" bio passed as high-confidence. Fix: open the
grid, require a clear majority of recent posts to be domain-relevant, record the actual ratio.

**P1.3 Substring keyword-matching bug class** *(Track A)*
Bare `"mp"` matched "Madhya Pradesh" and silently dropped valid candidates for ~14 cycles. Audit
**all** keyword matching for word-boundary errors — assume more exist.

**P1.4 Businesses/brands misclassified as creators** *(Track A)*
Gym chains, clothing brands, booking services pass the keyword filter. Add explicit account-type
classification: individual / team-or-club (keep) / business-brand (exclude) / media (exclude).

**~~P1.5 Duplicate creator rows~~ — NOT A PROBLEM.** Track A checked: only one creator claims
`"lebron"`, and a sweep across all `reddit_handles` found zero duplicated handles. The earlier
dedup migration already resolved it; this doc's claim was stale. Left here as a record that it
was checked, not assumed.

**P1.6 Fusion layer has never received a real spillover score** *(B → C)*
The last unclosed integration seam. Track C's formula uses placeholder weights. Blocked until B
trains on real data.

### P2 — known gaps, not yet blocking

- **⚠️ `reputation_score` / sentiment analysis — reframed 2026-08-16, still unbuilt.** The user
  clarified the actual intent behind Reddit collection: Reddit's role was never meant to be
  primarily co-occurrence (graph edges) — its value is unfiltered public opinion per creator,
  which is what `reputation_score` and the Temporal branch's Sentiment Propagation component
  need. **Reality check, confirmed against the code**: Reddit's only realized use in the ML
  pipeline to date IS the co-occurrence junction — sentiment analysis is 0% built, not partially
  built. This isn't a wrong turn Track A took; the Temporal branch (of the original two-branch
  design) has simply had zero attention while all focus went to the GAIL branch's "do we have
  any signal at all" crisis. Not the low-Reddit-volume's cause, though — that's structural (most
  athletes lack a dedicated subreddit), unrelated to the co-occurrence mechanism.
  **Bigger opportunity, previously unnoticed:** 19,843 YouTube comments and 13,097 Instagram
  comments are sitting completely unused for anything, sentiment or otherwise — a larger raw-opinion
  pool than Reddit's 9,480. **Next step (Track B, Temporal branch, not yet started):** sentiment
  analysis over `reddit_posts`+`reddit_comments`+`instagram_comments`+`youtube_comments` text per
  creator, aggregated into `reputation_score` + a time-series signal for Sentiment Propagation.
  Doesn't block or compete with GAIL/graph work; can start now on whichever creators already have
  decent comment volume, doesn't need more scraping first.
- **Temporal engagement-delta computation not built** *(B)* — the largest unbuilt GAIL piece;
  needs real sponsorship timestamps to compute before/after deltas around.
- **~15-row reconciliation gap** between Track A's own tally (~124) and the live sheet (139).
- **Permanently-dead handles** burning retry time: `athleanx`, `technicalguruji`,
  `delhicapitals`, `punjabkingsipl`. Mark dead, stop retrying.
- **Cross-platform temporal branch** (lag detection, Granger causality, sentiment propagation)
  is specified but largely unbuilt.
- **HLD diagram shows Twitter** instead of Instagram — fix before submission.
- **No auth on most endpoints**; basic `X-API-Key` exists on writes only.

---

## 6. THE PLAN — current state → thesis

**Mapped to the three milestones:**

| Milestone | Phases that must land | The demo story it tells |
|---|---|---|
| **Review 1** (~2–4 wks) | Phase 1 complete + Phase 2 to **~100 creators** | "End-to-end pipeline works on real data: here are real creators, a real graph, real recommendations." Small-but-real beats large-but-broken. |
| **Review 2** (~11–13 wks) | Phases 2–4 complete | "GAIL trains on real data, fusion produces real scores, the app works." |
| **Submission** (~15–17 wks) | Phase 5 (deployable, not deployed) + Phase 6 | Repo + paper + security fixes + Docker. |

⚠️ **Review 1 is close and rewards examples over completeness.** Phase 1's outputs — the
interactive graph, a working recommendation flow on real data — *are* the Review 1 demo. Don't
defer them chasing scale. Equally: **~100 creators clears the Review 1 bar, so don't cut corners
on collection quality to exceed it.** See §1.

### PHASE 1B — Deepening before labeling *(sequencing decision, 2026-08-11)*

**Track C waits.** The orchestrator initially proposed running Track C immediately after the
caption fix; the user pushed back and was right. Recorded because the reasoning generalises:

- The question "does the treatment signal exist" was **already answered** by Track A finding four
  real disclosures manually — so Track C's re-label answers only the narrower "does the labeler
  catch them," which isn't urgent.
- Track C has found **new failure modes at every scale increase** (21 rows → 422 rows surfaced
  four real near-misses). Validating against 60 captions, then re-validating after deepening
  multiplies the data, makes the first pass mostly wasted.
- Deepening will introduce content shapes the current 60 captions don't represent — other media
  types, YouTube descriptions, Reddit bodies. **Edge cases found after Track C signs off are the
  expensive kind.**
- Deepening is the slow, session-bottlenecked, browser-bound step; labeling is a fast DB
  operation. **Slow-first is correct ordering.**
- We still have **no per-creator timings**, and every Phase 2 projection depends on them.

Order: A deepens (with a 5-creator pilot checkpoint for timings) → C labels once against
representative data → B builds the graph → D visualises.

### PHASE 1 — Validation *(now, days not weeks)*
**Question it answers:** does the pipeline produce the treatment signal GAIL needs?
Sequential relay, each step gated on the previous:

1. **A** — fix captions (P0.1) + backfill · build promote step (P0.3) · deepen the 19 approved ·
   write team→player rows (P0.2)
2. **C** — verify backfill landed (don't trust "done") · re-run labeling · report events
   before/after · verify resolvers return *resolved* edge counts
3. **B** — build the first real `HeteroData` · report real structure (degree distribution,
   isolated nodes, components) · GAT forward pass · inductive test on real topology · first real
   training attempt if events exist · **honest call on whether ~19 creators is sufficient**
4. **D** — build the interactive network graph on `/explainability` (honestly sparse if sparse)

**Exit criteria:** we know whether sponsorship events and edges materialise, and roughly how long
deepening one creator takes (needed to project feasibility).

### PHASE 2 — Scale data *(~3–4 weeks)*
- Resume discovery toward **1,000 sheet candidates** with the P1.1 mechanisms and P1.2/P1.3/P1.4
  quality fixes; add `brand_signals`.
- Batch flow: identify (cheap, sheet) → user curates async → **promote per 100 approved on the
  user's explicit signal** → deepen (IG ∥ YT concurrently, Reddit after IG releases the browser).
- Rejections trigger **automatic backfill** so the review pool never runs dry.
- Target **200–400 datapoints/creator** (revised down from 1,000 — breadth over depth).
- **Real success metrics — report every cycle alongside creator count:** sponsorship events
  (target 300+), real edges (target 500+), brands with real data. If creator count climbs while
  those stay flat, the loop is doing the wrong work.

### PHASE 3 — Train GAIL for real *(~2 weeks, B leads)*
- Build temporal engagement-delta computation (P2) — the training target.
- Fit the propensity model on real treated/untreated examples.
- Train GAIL end-to-end; apply causal regularisation; validate on held-out campaigns.
- Cross-platform temporal branch: lag detection + Granger causality on real timestamps.
- Report calibration honestly; **document identification assumptions (unconfoundedness, overlap)
  as acknowledged limitations, not solved problems.**

### PHASE 4 — Fusion + integration *(~1–2 weeks, C leads)*
- Close P1.6: wire real spillover scores into the fusion formula.
- Calibrate `w1/w2/w3` against held-out outcomes instead of placeholders.
- Confidence bounds from bootstrapped/ensemble variance.
- Sentiment propagation → risk flags in monitoring.

### PHASE 5 — Deployable + secure *(~1–2 weeks, D leads with C)*
Note the bar: **deployable, not deployed.** Public hosting is deliberately post-submission.
- Recommendation UI on real scores; explainability graph with real causal insights.
- Monitoring/alerts driven by real sentiment propagation.
- Dockerise the full stack; verify `docker build`/`run` actually works; smoke-test in a browser.
- **Security pass — explicitly required for submission:** auth beyond the write-only
  `X-API-Key`, no credentials in the repo or in chat history, rotate the Supabase password
  (it was pasted into chat 2026-08-11), review RLS/anon-key exposure on Supabase, dependency
  audit. Budget real time for this; it's a submission gate, not polish.

### PHASE 6 — Thesis writeup *(~2 weeks, reserve it — compulsory deliverable)*
- Methodology, results, and a genuinely honest limitations section: observational data,
  disclosure-based treatment labels, dataset scale, India-skewed sample, engagement-per-rupee
  rather than true ROI.
- Repo cleanup — it's a compulsory deliverable in its own right, not just the paper's appendix.
- Fix the HLD diagram (still shows Twitter instead of Instagram).
- Prepare the live demo (extra credit, worth having given Phase 5 makes it nearly free).

---

## 7. Scenario planning

**Best case:** captions backfill cleanly → real disclosures surface → team rosters populate edges
→ GAIL trains on real data → fusion scores become real → the app shows genuine recommendations
plus an interactive causal graph. A complete end-to-end thesis with honest limitations.

**Scenario C — good captions but still 0 sponsorships:** disclosure-tag detection isn't viable
for this population. **Candidate pivot:** redefine the treatment as *brand-tagged posts*
(`brand_id` set) regardless of disclosure text. Still defensible — brand tagging is a real,
observable commercial relationship — but it changes the thesis's treatment definition and must be
stated plainly in the writeup.
⛔ **NOT pre-approved. The user explicitly asked to be brought this decision if it happens**,
with Phase 1's actual numbers in hand. Do not have Track C start building it on a confirmed zero
— surface the finding and wait.

**Scenario D — captions unfixable:** revisit extraction entirely, or treat Instagram text as
unusable and lean on YouTube descriptions (which are API-sourced and not truncated).

**Worst case:** no treatment signal is ever found, GAIL never trains on real labels, and the
thesis becomes "we built a pipeline but couldn't validate the core method." The mistakes that
would have caused it, stated plainly so they aren't repeated: caption truncation went undetected
for ~2 weeks while collection ran on top of it; a 9-hour discovery loop optimised creator count
while the real blocker was elsewhere; `creator_related_accounts` sat empty the whole project with
nobody checking the table edges derive from; curl-only testing hid the CORS bug for 8 weeks.
**The common thread: verifying that code ran, rather than that data arrived.**

---

## 8. Standing rules (earned the hard way)

1. **Verify the consumer, not just the writer.** Most silent-zero failures came from two tracks
   agreeing a feature exists while the string/table/value each assumed differed. Read the
   consuming code before bulk-writing.
2. **"Enabled" ≠ reachable.** Docker, claude-in-chrome, and Apify were all reported available
   before they actually were. Restart, then verify by *using* it.
3. **Never trust a guessed handle.** ~4 of 5 guessed handles resolved to fan/unrelated accounts.
   Verify against the real API; a wrong handle pollutes a real creator's data.
4. **Data changes under claims.** A same-day-true statement can be false hours later (Track A's
   relevance purge invalidated Track C's co-occurrence example within one day). Re-query.
5. **Adversarial self-check every round.** Re-derive, don't re-assert. It has found real bugs
   every single time it's been run.
6. **Commit verified work as you go** — Track D went 3 rounds without committing real, tested code
   because it never asked.
7. **Report deviations in chat, not just in commit messages/docs.**
8. **Row counts ≠ resolved counts.** Report what the consumer actually resolves.

---

## 9. Questions — resolved & open

**Resolved 2026-08-11:**
- ✅ **Deadlines:** Review 1 late Aug–early Sep (≥50% + examples), Review 2 late Oct–early Nov
      (80–100%), submission late Nov–early Dec (complete, secure, deployable). See §1.
- ✅ **Deliverables:** repo + paper compulsory; live demo = extra credit; public deployment
      deliberately post-submission.
- ✅ **Scenario C:** *not* pre-approved — bring the decision back with real numbers.

**Still open:**
- [ ] **Review 1 demo shape** — once Phase 1 lands, decide what specifically gets shown. Likely
      the interactive graph + a live recommendation query on real creators, but worth choosing
      deliberately rather than demoing whatever happens to work.
- [ ] ~~Is ~19 creators enough to demo credibly at Review 1?~~ **Resolved: ~100 is the bar, and
      collection quality outranks demo density.** Track B's Phase 1 sufficiency call still
      matters — but for *model training* viability, not for demo adequacy.
