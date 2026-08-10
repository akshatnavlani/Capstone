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

### 3.2 Live DB state — **orchestrator-verified 2026-08-11 after Phase 1A**

| Table | Rows | Note |
|---|---|---|
| `creators` | **55** | was 16. Promote step built: 39 promoted + 16 grandfathered *enriched* (not duplicated), 0 duplicate handles |
| `creator_related_accounts` | **1** | was 0. 1 resolvable edge; mechanism needs rework (§2) |
| `brands` | 1 | unchanged — new `@oakleymeta`/Milton mentions not yet through extraction |
| content rows with `brand_id` set | 1 | unchanged |
| `instagram_posts` | 97 | **60 captions non-null & distinct, max 1058, avg 257, 35 >100 chars; 37 NULL** |
| `reddit_post_creators` | 346 | junction table, working |

**Sheet is now at 55 accepted** (was 19) — the user has reviewed considerably more.

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

**⚠️ P0.2 Collaboration edges — table populated but MECHANISM FAILED** *(Track A → C → B)*
0 → 1 edge. Team→player tagging doesn't exist on IPL/ISL accounts (they caption with hashtags).
**Next mechanisms to try, in order:** (1) Instagram collab co-author list ("X and N others") —
a native, unambiguous collaboration fact; (2) Instagram "tagged people" on posts, distinct from
caption @-mentions; (3) resolve whether the 37 NULL-caption rows are collab posts (⇒ edges) or
scraper contamination (⇒ delete). See §2.

**✅ P0.3 Promote-to-DB — DONE 2026-08-11.** `creators` 16 → 55, upsert semantics correct
(`athleanx` gained the instagram_handle it had on the sheet but not the DB — exactly the case
insert-only would have missed), 0 duplicates, `approval_status` untouched.

**P0.4 Sponsorship events — signal confirmed, labeling pending** *(Track C, now unblocked)*
Still 0 in the DB (`is_sponsored` is Track C's to populate) but ≥4 genuine disclosures are now
present in real captions. **Track C's re-label is the immediate next step**, and those 4 known
disclosures are a concrete validation target — if the labeler misses them, that's a labeler bug,
not an absence of signal.

**P0.5 Deepening not completed** *(Track A)* — the full IG→YT→Reddit cycle per approved creator
did not run; time went to the caption incident. **We still have no per-creator datapoint counts
or wall-clock timings**, which Phase 2 feasibility projections depend on. Real gap, carried
forward.

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

- **`reputation_score` has no source anywhere** in the schema *(C flagged, correctly unfabricated)*.
  Track A's Reddit rework makes a sentiment-derived proxy plausible — Track B's to build if wanted.
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

### PHASE 1 — Validation *(now, days not weeks)*
**Question it answers:** does the pipeline produce the treatment signal GAIL needs?
Sequential relay, each step gated on the previous:

1. **A** — fix captions (P0.1) + backfill · build promote step (P0.3) · deepen the 19 approved ·
   write team→player rows (P0.2) · clean duplicates (P1.5)
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
