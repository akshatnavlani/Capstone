# HANDOFF — Track A (Data/Infra)

**Start here.** Canonical entry point for a fresh session on this track. Last updated
2026-08-12 (end of Weeks 11-13). Branch: `track-a-data-infra`. Worktree:
`D:\Capstone-worktrees\track-a-data-infra`.

Read this first, then `DATA_COLLECTION_STATUS.md` (real backend state + measurements),
`ORCHESTRATION.md` (pipeline design + the parallelization rule), `SCHEMA.md` (DB
contract other tracks build against).

---

## Current state (one paragraph)

The full data layer is **built, live, and collecting real data**. Supabase Postgres is
provisioned with 13 tables + 1 view (DDL in `supabase/migrations/`, applied in filename
order). `scripts/ingestion/orchestrator.py` is a working pipeline for all three
platforms — YouTube via the official Data API, Instagram and Reddit via OpenCLI driving
a real logged-in Chrome session. As of the last run: **24,043 datapoints across 15
curated creators, 7 of them at or over the 1,000-datapoint floor**, with relevance and
recency independently verified (Reddit topic-sub relevance 223/223 = 100%; zero rows
older than the rolling 6-month cutoff). Brand extraction works and has one proven real
positive case (Virat Kohli / Agilitas). What is **not** done: the v1 dataset is
deliberately **not frozen** (PROJECT_PLAN's Week 9-10 row says to freeze — do not,
several creators are still far below the floor); Instagram comment coverage is capped
by a page-render truncation that remains unsolved; and the scheduled daily task fires
but does not run to completion.

---

## Open items

| Item | Why it's open |
|---|---|
| **Scheduled task doesn't complete** — `CapstoneDataIngestion` (Task Scheduler, daily 10:00) fired on 2026-08-10, ran ~3 min of YouTube (2 channels), then stopped. No Instagram/Reddit sections, no completion marker, no traceback. | **Not started / needs diagnosis.** Earlier reporting said "scheduling works" — that was only half true (it *fires*; it doesn't *finish*). Suspect the PowerShell wrapper treats Python's stderr logging as a terminating error (log shows `python.exe :` prefixes and `At ...run_pipeline.ps1:26 char:5`). Check `$ErrorActionPreference` / stderr handling in `run_pipeline.ps1`. |
| **Instagram grid stalls at ~12 links** on most profiles despite `post_cap=40`; only `virat.kohli` reached the cap (48 links found). | **Not started.** This — not the post cap — is now the binding constraint on Instagram volume. |
| **Instagram high-engagement comment truncation** — page render shows only ~9-15 comments regardless of true count (measured 9 of 352,130 on a Cristiano post = 0.0026%). | **Blocked-ish.** Exhausted the non-risky options (load-more control, scrolling, network inspection). The remaining path is reverse-engineering Instagram's private GraphQL, which carries real ban risk — **needs a user decision**, not a unilateral call. |
| **4 creators structurally below floor** — Saina Nehwal (108), PV Sindhu (74), MC Mary Kom (208), Bhuvan Bam (1). | **Needs a user decision.** No dedicated audience surface (no own YouTube channel, no creator-specific subreddit), or an inactive channel. Options: widen the recency window, accept them as low-volume entities, or replace them in the target list. |
| **Freeze v1 dataset** (PROJECT_PLAN Week 9-10). | **Deliberately deferred** by user direction — freezing now locks in a dataset too thin for GAIL training. Revisit once more creators clear the floor. |
| **Instagram scroll change aborts instead of degrading** — raises `no post links found after scrolling` where older code took a partial screenful. | **Not started.** Turned partial results into total per-creator failures under contention. Should degrade, not abort. |

**Closed, do not reopen:** Apify is genuinely unavailable — checked across **three**
separate restart cycles (no MCP server, CLI, Python client, token, or config, ever).
Stop re-checking it each round.

---

## Non-obvious lessons (these are not visible from reading the code)

1. **OpenCLI arbitrates browser access via TAB LEASES from one daemon per Chrome
   profile — so no two OpenCLI-backed platforms can run concurrently.** Running
   Instagram and Reddit sub-agents in parallel starved Reddit out completely (0 of 8
   creators, all `TypeError: Failed to fetch`) while Instagram kept succeeding on the
   same browser. This is *not* a rate limit (failures were instant, at exactly our own
   3s gap; a real limit is an HTTP 429 from the platform). It cannot be fixed by naming
   sessions — only `opencli browser <session>` takes a name, site adapters don't.
   **Safe pattern: one sub-agent for YouTube ∥ one sub-agent doing Instagram then
   Reddit sequentially.** Full detail in `ORCHESTRATION.md`. YouTube is always safe —
   verified it makes zero browser calls (`urllib` straight to `googleapis.com`).

2. **Never trust a handle guessed from training knowledge — verify every one against
   the real API/profile first.** Hit repeatedly: `whitneysimmons` resolved to an
   unrelated 460-follower account; `neeraj_chopra1` and `mirzasania` to unrelated
   accounts; **4 of 5** guessed YouTube handles resolved to fan/unrelated channels. A
   wrong handle pollutes a real creator's data with a stranger's. Best verification
   trick found: **cross-platform corroboration** — Neeraj Chopra's YouTube listed
   management contact `connect@velsports.com`, matching the `velsports.co` in his
   already-verified Instagram bio.

3. **A volume number is meaningless without a relevance check attached.** Reported
   volume for two rounds before ever checking the rows were about the right people —
   then measured **0%** relevance on general subreddits (0 of 41 r/tennis posts
   mentioned Sania Mirza, etc.) and had to purge **88%** of Reddit data (289 of 330
   creator↔post links). Every volume figure quoted now carries a relevance number.

4. **Posting FREQUENCY, not audience size, predicts data volume.** Deeply
   counter-intuitive and it will mislead target selection: CarryMinati (45.7M subs)
   yielded 5 videos in the recency window; Bhuvan Bam (26.5M subs) yielded **zero**
   (all 40 most recent videos predate the cutoff); Mumbiker Nikhil (4.0M subs but 3,168
   lifetime videos) topped the entire dataset at 3,928 datapoints. **Filter future
   targets on upload cadence, not subscriber count.**

5. **"Tool X is now enabled/installed" is a statement of intent, not a guarantee this
   session can reach it — verify each claimed unblock independently.** Apify was
   reported enabled three times and never was. Notably one restart *did* deliver the
   `claude-in-chrome` tools while Apify still didn't arrive — so bundled claims resolve
   on **different timelines** and must be checked per-item, not accepted or rejected
   together.

6. **Merge-on-upsert is right for incrementally-discovered values and wrong for a
   curated source of truth.** The creator upsert merged Reddit source arrays, making it
   impossible to *reclassify* a subreddit — after re-seeding, Sania Mirza still had
   r/tennis flagged creator-specific. The curated target list is now authoritative
   (replace, not merge) for those fields.

7. **Windows/encoding gotchas that cost real debugging time:** `subprocess.run(text=True)`
   defaults to cp1252 and crashes on emoji in real comment text — force
   `encoding="utf-8", errors="replace"`. Bare `"opencli"` won't resolve via
   `CreateProcess` (npm `.cmd` shim) — use `shutil.which()`. `opencli reddit user -f json`
   crashes on emoji fields but `-f yaml` works. PowerShell's profile prints a banner that
   makes naive `grep -q .` liveness checks always true — use `-NoProfile`.

---

## Exact next steps

1. **Diagnose the scheduled task** (highest value — it's the difference between a
   pipeline and a manual script). Start with stderr handling in `run_pipeline.ps1`; the
   log strongly suggests PowerShell aborts on Python's stderr logging output.
2. **Fix the Instagram ~12-link grid stall** — biggest single lever on Instagram volume.
3. **Get a user decision** on the two blocked items above: the Instagram comment
   truncation (GraphQL = ban risk), and what to do about the 4 structurally-low creators.
4. **When the target list changes, re-run ALL platforms, not just the reworked one.**
   Cost a round: added 6 creators, ran only Reddit, and they showed ~0 volume until
   YouTube was re-run — at which point three of them jumped straight over the floor.
5. Re-check other tracks before assuming interfaces hold:
   `git fetch origin && git show origin/track-c-fusion-backend:API_CONTRACTS.md`
   (also `origin/track-b-ml-core:GRAPH_SCHEMA.md`).

## How to run it

```bash
cd scripts/ingestion
PY="C:/Users/Sonic/AppData/Local/Programs/Python/Python314/python.exe"
"$PY" orchestrator.py --seed target_list.json                       # seed/refresh creators (authoritative)
"$PY" orchestrator.py --platform youtube  --target-list target_list.json
"$PY" orchestrator.py --platform instagram --target-list target_list.json
"$PY" orchestrator.py --platform reddit   --target-list target_list.json   # never concurrent with instagram
```
Needs `.env` at repo root (gitignored, never committed): `DATABASE_URL`,
`YOUTUBE_API_KEY`, `OPENCLI_PROFILE`. Instagram/Reddit need **real Chrome** open and
logged in — **not Arc** (Arc connects but every command hangs; documented in
`DATA_COLLECTION_STATUS.md`).

---

## ⚠️ INSTAGRAM RATE LIMIT REACHED — HTTP 429 (2026-08-11, Phase 1B pilot)

`opencli instagram profile <any handle>` now returns **HTTP 429**, including for a
control account (`nasa`), and it persisted across a 20s re-probe. This is a **genuine
platform rate limit**, categorically different from the `HTTP 400 - make sure you are
logged in` failures seen intermittently all session — and it matches this file's own
lesson 1 criterion verbatim: *"a real limit is an HTTP 429 from the platform."*

**What triggered it:** cumulative Instagram request volume in one day — a ~9-hour
discovery loop, then a 97-post caption backfill, then a 97-post collab/edge pass
(~200 post-page fetches inside a few hours), then the deepening pilot.

**Consequence: Instagram deepening cannot proceed until this clears.** The Phase 1B
pilot collected 0 Instagram datapoints for all 4 pilot creators. YouTube (official API,
independent transport) and Reddit were unaffected and worked normally.

**Before resuming Instagram work:** probe a single `instagram profile nasa` call and
confirm a real result. Do NOT run a bulk job to "see if it works" — that is what
accumulated the limit. Back off in hours, not minutes.

## UNFINISHED: collab pass killed mid-run 2026-08-11 (resume this)

`collab_edges.py` over all 97 posts was **killed at ~83/97**, so its edge INSERT and
co-author sheet push — both of which run at the END — never executed for that pass.

**What persisted (written incrementally, per-post):** `has_paid_partnership_label` for
83 of 97 posts (80 false, 3 true, 14 still NULL) and all caption fixes. Verified clean:
82 non-null captions / 82 distinct.

**What was lost:** edges and co-author candidates from the ~53 posts beyond the first
paced batch. Current totals (20 edge rows / 2 resolved / 18 sheet candidates) come from
the earlier 30-post run only.

**To finish:** re-run `python collab_edges.py` (~18 min at the 5s pacing). It is safe to
re-run — UNIQUE(creator_id, platform, handle) prevents duplicate edges, the caption
update is guarded by a strictly-longer check, and the sheet push dedups on
instagram_handle. Do NOT run Reddit concurrently with it.

**Lesson worth keeping:** batch-terminal writes are fragile for long browser jobs. The
per-post writes (captions, paid-partnership flag) all survived the kill; the
end-of-run writes did not. Future long passes should flush edges incrementally too.

---

## Instagram grid-stall: characterised 2026-08-14 (one leak FIXED, root cause still open)

Diagnosed from 3 days of unattended scheduled-run logs (Aug 11/12/13) — a repeatable
signal that did not exist when this was a single incident.

**The failure sequence is byte-identical across Aug 11 and Aug 12, in processing order:**
```
virat.kohli OK | neeraj____chopra FAIL | pvsindhu1 FAIL | nehwalsaina FAIL
mirzasaniar FAIL | mcmary.kom OK | kingjames FAIL | cristiano FAIL
beerbiceps OK | bhuvan.bam22 FAIL | carryminati FAIL | mostlysane OK | gurumann OK
```

**What this rules OUT (each tested against the logs, not assumed):**
- *Positional session degradation* — failures are interleaved with successes, not
  clustered at the end.
- *Rate limiting / time-of-day* — Aug 11 ran at 10:00, Aug 12 at 23:46; identical result.
  A rate limit would not reproduce byte-for-byte at different hours.
- *Follower count / account size* — `cristiano` (678M) fails, `virat.kohli` (272M)
  succeeds; `mcmary.kom` (2.0M) succeeds, `pvsindhu1` (3.9M) fails.
- *Account being broken/private* — see next point.

**Cleanly isolated:** `opencli instagram user <handle>` (site adapter) **never failed
once** across all three days — 0 errors. Only the browser path
(`browser open` → `find --css 'a[href*="/p/"]'`) returns nothing. So the accounts are
reachable and the login is valid; the failure is specific to **browser-driven grid
rendering**. This is the same shape as the documented Arc symptom (site adapters work,
browser automation hangs/returns nothing), which is worth remembering as a *class* of
failure, not an Arc-only quirk.

**Aug 13 is a DIFFERENT failure** — 5x `timed out after 30 seconds`, including on
`instagram profile mirzasaniar`, with no grid-stall at all. That day the browser layer
was unavailable outright, most likely the same stale/wrong-profile condition hit
manually on Aug 14 (see below). Do not conflate the two.

**FIXED this round — tab-lease leak on the failure path.** `process_creator` opens a new
named session per creator (`orc_<handle>`) and closes it only at the END of the method;
the no-post-links `raise` sits before that close, so **every failed creator leaked a held
tab lease and an orphaned tab for the rest of the run** — up to 8 leaks in the Aug 12
pass. Now released explicitly there, plus a deterministic-name backstop in `run_batch`'s
per-creator `except` covering all other raise paths. Corroborated independently: a
killed collab run left a stale `collabx` lease that had to be released by hand.
⚠️ **This is a real leak fix, NOT a proven fix for the stall.** Failures do cluster
immediately AFTER heavy successful scrapes and then recover, which is consistent with
leaked leases/orphaned tabs degrading the browser — but that is a hypothesis. It needs
re-measurement against a real scheduled run before anyone claims the stall is solved.

**Next thing to try** (cheap, high information): run ONE consistently-failing creator
(e.g. `cristiano`) in **isolation, first call of a fresh session**. If it succeeds alone,
the cause is cumulative browser state (leases/tabs) and the leak fix likely addresses it.
If it fails alone too, the cause is per-account page structure and the grid selector
needs revisiting.

**Also worth building** (documented open item "aborts instead of degrading"): since
`instagram user` succeeds even when the grid fails, the worker could fall back to the
listing for post metadata instead of aborting the creator entirely. Caveat to check
first: the listing reportedly returns no post URLs/IDs, and `post_id` is the PK — so
confirm whether any usable ID is available before designing the fallback.

**Environment gotcha found the same day:** `OPENCLI_PROFILE` in `.env` went stale.
Chrome's extension instance re-registered during a 3-day gap and for a period the only
connected profile was **Arc's**. Arc's failure mode is more insidious than recorded above:
`instagram profile nasa` returned real data **fast**, while `browser open` hung for 120s.
Arc can look partially healthy. Always confirm `opencli doctor` shows the intended
profile before blaming the scraper.

## ✅ Instagram grid-stall RESOLVED in practice (2026-08-14, Phase 1E)

**Discriminating test:** `cristiano` (a both-days failure), fresh session, grid path only →
**12 → 12 → 24 → 36 links** across successive scrolls. Healthy progressive lazy-load.
Branch: *succeeds alone* ⇒ cumulative browser state, not per-account page structure.

**Confirmation batch — the 8 creators that failed in the Aug 11/12 logs, re-run with the
tab-lease fix active:**

| | Before (Aug 11/12) | After (Aug 14) |
|---|---|---|
| Stall rate | **8 of 8 failed** (100%) | **0 of 8 failed (0%)** |
| Links found | 0 | 48 for 7 of 8 (12 for carryminati) |
| Datapoints | 437 | **4,482 (+4,045)** |
| Creators with any `instagram_posts` | 10 | **13** |
| `instagram_posts` | 143 | **401** |
| Leaked sessions after run | up to 8 | **0** (doctor: single profile, 0.1s connectivity) |

Runtime 1853s for 8 creators (~232s/creator at post_cap=40).

⚠️ **Honest caveat on causality:** Chrome was also restarted that morning, so "leak fix
working" and "fresh Chrome process" are confounded — this is strong practical evidence
the stall is gone, NOT proof the leak fix alone caused it. The next unattended scheduled
run is the real test: it accumulates state across a full pass without a manual restart.
**If the stall returns there, the leak fix was not sufficient and the cause is something
that survives it.**

**Caption distinctness note:** the standing check flagged 319 non-null / 316 distinct.
Investigated rather than assumed — all 3 collisions are 1-2 character EMOJI-ONLY captions
(two different creators each posting a single emoji). Genuine duplicates, not corruption.
The corruption signature was *long* (400-1100 char) captions repeated across unrelated
posts. Worth remembering: interpret the distinctness check with caption LENGTH in mind,
or trivially-short captions will keep raising false alarms.

### Incremental flush proved itself again — this time unplanned (2026-08-14)

The edge-extraction run over the enlarged post set was killed at 280/401 posts after
~30 minutes. Result: **120 new edge rows survived (72 → 192) and RESOLVED doubled
(2 → 4)**, plus a 25 KB co-author checkpoint on disk. Under the previous
end-of-run batching, all 120 rows would have been discarded — which is exactly what
happened the last time a run was killed. First proof was a deliberate test; this one
was a real interruption, which is better evidence.

**First new cross-creator edge in the project: Cristiano Ronaldo ↔ LeBron James**
(both directions), discovered only because their posts had just been scraped. Resolved
pairs went 1 (Kohli↔RCB) → 2. This is direct confirmation that resolved edges are gated
on Instagram COVERAGE, not on the extraction mechanism: scrape two creators, and any
collaboration between them resolves automatically.

## ⚠️ Instagram network-layer throttle — and why a single probe MISLEADS (2026-08-14)

A distinct failure mode from the HTTP 429 recorded earlier. It arrives as
`page mismatch: got chrome-error://chromewebdata/` — Chrome failing to establish the
connection at all. **No 429 appears anywhere.** So any check keyed on the string "429"
will not fire, and a naive per-item skip will grind through hundreds of guaranteed
failures (one run burned 106 consecutive ones, posts 66-171, before being stopped by hand).

**THE LESSON THAT COST A WRONG CALL: one successful probe does not mean the throttle
cleared.** After stopping the burning run, three probes all passed — the exact failing
post loaded, `instagram profile nasa` returned data, a non-Instagram control loaded — and
that was reported as "fully recovered." It was not. Resuming sustained scanning re-tripped
the throttle within **4 posts (~45 seconds)**. Single requests are served fine while
sustained request *rate* is still blocked. To test whether it has really cleared, you need
sustained load or a genuinely long wait — not one call.

**Handling now in `collab_edges.py`:** abort after 5 CONSECUTIVE failures regardless of
error string (reset on any success), and 8s between posts. On the re-trip this aborted in
48s instead of ~54 minutes of failures.

**What to do when it happens:** stop, wait properly (hours, not minutes — the earlier 429
cleared in ~25 min but this one did not clear in ~20), then re-run with `--only-new`.
Everything already extracted is flushed incrementally and safe. Do NOT probe-and-resume.

**Why this was diagnosable at all:** the URL assertion (`post_id` must appear in the
returned page URL). Without it the extractor would have silently parsed the chrome-error
page and written garbage captions — the exact corruption class the assertion was added to
prevent. It converted a silent-corruption bug into a loud one.

---
---

# LOOP (2026-08-18) — batch-readiness loop, 30-min cadence. CYCLES 1-3 DONE

**A fresh session resuming this loop should read THIS section first — it is the live state.**

## ⚠️ CYCLE 11 — FALSE BRAND POSITIVES FROM GRID TEXT, found and fixed

The co-author run's classification pass routed real PEOPLE to `brand_signals`:

```
brisonfernandes17_  -> BRAND: 'sportswear'   (from grid, bio inconclusive)   a Goan footballer
duamirzaasad        -> BRAND: 'skincare'     (from grid)                     a person
abhishekganguly     -> BRAND: 'activewear'   (from grid)                     a person
```

**Root cause:** the brand rules were being applied to **grid text**, i.e. post captions. A
product-category noun in a *bio* identifies the account as a brand; the same noun in a
*caption* just means the creator posts about products — which creators do constantly. Applied
to captions the rule inverts, and its failure mode is the worst one available: a false BRAND
**drops a real person** instead of queuing them for review.

**Fixed:** brand determination is now **bio/name only**. The grid may still refine a CREATOR
category, but a BRAND verdict originating from grid text is rejected and recorded as such.
Bio-based brand detection verified still working (`Luxury Fragrances`, `leading bottom-wear
brand` both still BRAND); 42-case suite still 42/42.

⚠️ **Follow-up owed:** the 3 handles above were routed instead of pushed, so they are missing
from the sheet. Re-run `push_checkpoint_candidates.py --from-db` after the current run
finishes — it skips anything already on the sheet, so it will pick up exactly these.

## 🚨 CYCLE 10 — THE SINGLE BLOCKER IS `posted_at`, QUANTIFIED

The co-author run finished: **184 new edge rows, RESOLVED 185 → 203, +21 paid-partnership
posts, 25 caption fixes, 0 failures.** Edge pairs 163 → **170**. Computable pairs **still 14**.

That combination is the whole story, and this is the number that explains it:

| | count |
|---|---|
| Sponsorship events found | **53** |
| …of which **DATED** | **7 (13%)** |
| Event-neighbour combos **if every event were dated** | **145** |
| Event-neighbour combos **with dates as they actually are** | **25** |
| **Undated events sitting on ALREADY-CONNECTED creators** | **43** |

⇒ **Dating, not discovery, is the binding constraint.** We are finding events faster than we
can date them (24 → 45 paid-partnership posts this cycle, of which ~0 dated). At the observed
straddle rate (14 of 29 ≈ 48%), those ~120 lost combos are worth roughly **50–70 pairs** —
far beyond the 20-pair target.

Worst offenders, all already graph-connected: `anushkasharma` **0 of 15 dated**,
`CarryMinati` 6 undated, `karanjohar` 4, `taarukraina` 4, `Bhuvan Bam` 4, `Virat Kohli` 3.

### Why this cannot be fixed with the current toolkit (all three tested, not assumed)
- **Adapter listing** — capped at **12 posts** regardless of `--limit` (verified on 2 creators
  at both 12 and 40). Sponsored posts sit deeper than 12.
- **Profile grid alt-text** — only carries a date for **caption-less** posts; sponsored posts
  essentially always have captions.
- **Post page** — carries **no date at all** (0/4 against ground truth), and its like counts
  belong to *suggested* posts (DB 172,598 vs extracted "8").

### ⇒ RECOMMENDATION FOR §1a BATCH-READINESS
**Do not promote a new batch to chase more pairs.** More creators produce more *undated*
events, which is what this cycle just demonstrated. The highest-value work is a reliable
`posted_at` source for sponsored posts — that alone would take this dataset from 14 pairs to
an estimated 50+ **with the creators already collected**.

## 📐 CEILING ANALYSIS (cycle 7) — READ THIS BEFORE PLANNING MORE WORK

Every event-neighbour combination, classified by what actually blocks it:

| | count | fixable? |
|---|---|---|
| **Computable now** | **14** | — |
| Neighbour has NO Instagram content | 6 | deepening CAN fix |
| Neighbour's collected window STARTS AFTER the event | 7 | **unreachable** without history extension |
| Window covers the event but before=0 | 0 | — |
| **Total combos** | **29** | |

⇒ **With the CURRENT set of events and edges, the hard ceiling is 20 pairs** (14 + 6), and
only if all six deepen successfully. Of those six:
- `sporting.beyond` — **must not be deepened**: flagged brand (Sporting Beyond Pvt Ltd) and a
  dead handle
- `portugal`, `nikkhiladvani` — each **failed twice**; treat as dead/blocked, do not retry
  again without a different approach
- `suhan.khnofficial`, `Mumbai City FC` — the only clean targets left

**Realistic ceiling on the current graph is therefore ~16, not 20.** Exceeding it requires
either MORE DATED EVENTS (blocked — the 25 dateless sponsored posts are unreachable by every
mechanism: adapter capped at 12, grid only dates caption-less posts, post page has no date)
or MORE RESOLVING EDGES (the co-author run in flight is exactly this).

**That makes edges, not deepening, the binding constraint from here.**

## 🎯 COMPUTABLE PAIRS: 3 (baseline) → 14 of the 20 target

Trajectory by cycle: **3 → 4 → 5 → 10 → 13 → 14**.

| | baseline | cycle 6 |
|---|---|---|
| Instagram attempted | 121 (46.7%) | **130 (50.2%)** |
| Instagram with content | 36 (13.9%) | **47 (18.1%)** |
| YouTube attempted | 259 (100%) ✅ | 259 (100%) ✅ |
| Reddit attempted | 36 (13.9%) | 54 (20.8%) |
| Reddit name-gated | 215 (83%) | 200 (77%) |
| **Computable pairs** | **3** | **14** |
| Collaboration edge pairs | 161 | 163 |

**Cycle 6 note — the contentless-neighbour lever is showing diminishing returns.** The second
batch (chennaiyinfc, anushkasharma, nasimamirza, saniamirzatennisacademy, servingitupwithsania)
deepened 5 creators for **+1 pair**, versus +4 from the Bhuvan Bam batch. The remaining
contentless neighbours mostly touch a single event each, and several fail outright
(`nikkhiladvani` twice, `portugal` — both look like dead/blocked handles).

**IN FLIGHT:** co-author extraction over **284 newly deepened posts** (chennaiyinfc 40,
karanjohar 40, pratibha_ranta 39, nasimamirza 38, saniamirzatennisacademy 35, anushkasharma 31,
servingitupwithsania 30, …). New edges are the other route to pairs, since every new resolving
edge multiplies against the dated events already held.

### (superseded) earlier snapshots below

Cycle 5's full deepening run (5 of 6 creators; `nikkhiladvani` failed and is being retried)
took pairs 10 → **13**. Instagram attempted 121 → 126 (48.6%), with content 37 → 42 (16.2%).

**IN FLIGHT:** deepening the remaining 8 contentless neighbours of dated events —
`chennaiyinfc`, `nikkhiladvani`, `anushkasharma`, `nasimamirza`, `portugal`,
`saniamirzatennisacademy`, `servingitupwithsania`, `suhan.khnofficial`. `chennaiyinfc` and
`nikkhiladvani` each touch **2** events, so the upper bound on that batch is ~10 more pairs.
`sporting.beyond` was excluded — a flagged brand (Sporting Beyond Pvt Ltd) and a dead handle.

### The full-list snapshot below is from the 10-pair moment; re-run `loop_stats.py` for live.

## (snapshot at 10 pairs)

| Creator | src | Event date | Neighbour | before | after |
|---|---|---|---|---|---|
| Bhuvan Bam | ig | 2026-05-14 | gurfatehpirzada | 1 | 9 |
| Bhuvan Bam | ig | 2026-06-11 | gurfatehpirzada | 1 | 9 |
| Bhuvan Bam | ig | 2026-05-14 | mohitvaru | 1 | 9 |
| Bhuvan Bam | ig | 2026-06-11 | mohitvaru | 1 | 9 |
| Cristiano Ronaldo | ig | 2026-07-21 | LeBron James | 17 | 179 |
| Kerala Blasters | yt | 2026-05-18 | Mumbai City FC | 3 | 37 |
| Sania Mirza | ig | 2026-08-01 | Parikshit Balochi | 12 | 2 |
| Virat Kohli | ig | 2026-04-29 | PV Sindhu | 3 | 12 |
| Virat Kohli | ig | 2026-04-29 | Karan Aujla | 9 | 11 |
| mrbeast | ig | 2026-08-12 | CarryMinati | 69 | 13 |

### 🔑 THE HIGHEST-YIELD LEVER FOUND SO FAR
**Deepen the CONTENTLESS NEIGHBOURS of an already-dated event.** Bhuvan Bam had 2 dated
events and 6 connected neighbours with **zero posts**. Deepening them produced **4 pairs from
one run** — more than every other mechanism this loop combined.

Why it works, and when it does not: a contentless neighbour gets a *fresh* 40-post window
(roughly the last few months), which straddles a recent event. A neighbour that already has
content has a FIXED window, and if that window starts after the event it can never straddle
it — which is exactly why RCB is unreachable.

**Rule: for a `before=0` near-miss, check the neighbour's `min(posted_at)` against the event
date. Earlier ⇒ dating its posts can work (Karan Aujla: before 0 → 9). Later, or no posts at
all ⇒ deepen instead (Bhuvan Bam's neighbours), unless the cap makes it impossible (RCB).**

⚠️ Correction: I predicted `karanaujla` would be unreachable like RCB. **Wrong** — its window
does extend before 2026-04-29, and grid dating converted it into a pair.

### (superseded) earlier pair list at 5

| Creator | Event src | Date | Neighbour | before | after |
|---|---|---|---|---|---|
| Virat Kohli | instagram | 2026-04-29 | PV Sindhu | 3 | 12 |
| mrbeast | instagram | 2026-08-12 | CarryMinati | 69 | 13 |
| Sania Mirza | instagram | 2026-08-01 | Parikshit Balochi | 12 | 2 |
| Cristiano Ronaldo | instagram | 2026-07-21 | LeBron James | 17 | 179 |
| **Kerala Blasters** | **youtube** | **2026-05-18** | **Mumbai City FC** | **3** | **37** |

## Stats: baseline → cycle 3 (259 creators)

| | baseline | now |
|---|---|---|
| Instagram attempted | 121 (46.7%) | 121 (46.7%) |
| Instagram with content | 36 (13.9%) | 37 (14.3%) |
| **YouTube attempted** | **259 (100%)** ✅ | **259 (100%)** ✅ |
| Reddit attempted | 36 (13.9%) | 54 (20.8%) |
| Reddit name-gated | 215 (83%) | 200 (77%) |
| **COMPUTABLE PAIRS** | **3** | **5** |
| Collaboration edge pairs | 161 | 163 |

## CYCLE 3 — Kerala Blasters roster extraction WORKED (the loop's own idea, validated)

Deepened `keralablasters` on Instagram (40 posts, 48 links), then ran co-author extraction:
**edges 0 → 19, of which 2 RESOLVE** — to `chennaiyinfc` and `Mumbai City FC`, rival ISL
clubs tagged in match posts. That converted KB's previously-orphaned YouTube sponsorship
events into the **5th computable pair**. Also routed 2 brands (`oppokerala`, `suryadev_tmt`)
to brand_signals and pushed 15 candidates for review. Real players surfaced but stay dangling
(`fallou_ndiaye04` etc.) — promotion is the user's call.

## ⚠️ MEASUREMENT BUG FIXED THIS CYCLE — the 5th pair depended on it
`loop_stats` counted sponsorship events on **Instagram only**, so Kerala Blasters' 2 YouTube
events were invisible to the pair query — the *same* cross-platform blind spot already fixed
on the NEIGHBOUR side of the same calculation. The event side is now a UNION across
Instagram + YouTube + Reddit. **Without this fix the KB pair would not have been counted.**

## CYCLE 2 findings (Instagram mechanics — all three settled)
- **Adapter partially recovered** after 4 rounds blocked: 4 of 6 sustained requests succeed
  (mostlysane, taarukraina, ajinkyarahane, kkriders); carryminati and virat.kohli still 429.
  **Intermittent, not recovered.**
- **`--limit` does NOT lift the 12-post metadata ceiling.** `--limit 40` returns exactly 12,
  verified on 2 creators at both values. My earlier "very likely the entire cause" hypothesis
  was WRONG. With the grid (dates only for caption-less posts) and the post page (no date at
  all), **the 25 dateless sponsored events are unreachable by every available mechanism.**
- **Positional-alignment corruption: no evidence.** Built `backfill_meta_by_caption.py`
  (matches on CAPTION, no ordering assumption) and audited 4 creators: **0 date conflicts in
  15 caption-verified comparisons.** Small sample; kkriders matched 0 (captions differ).

## ⚠️ PHASE 1 CLEARANCE RETRACTED — run Instagram and Reddit SEQUENTIALLY
The 3-call burst said browser+adapter don't contend. **Under sustained load they do**: Reddit
ran clean ~8 min, then every search failed starting ~4 min after a concurrent Instagram
browser job began; the same queries succeeded immediately once Instagram stopped. **A short
burst is not a valid concurrency test** — same error class as the single-probe throttle test.

## ⚠️ Standing hazards
- **Generic names cause Reddit false positives.** "Fitness Standards Council" matched 11
  unrelated r/india posts on bare tokens. Fixed via `_GENERIC_NAME_TOKENS`; fully-generic
  names now need the full phrase. 10 bad rows purged.
- **Creators with NULL instagram_handle duplicate on `--target-list` runs.** A second
  `Mumbiker Nikhil` was inserted and removed. Watch for this.
- **Reddit is a weak lever**: of 38 creators searched, only 1 produced posts, and those were
  the false positives.

## ⛔ CYCLE 4 — the RCB near-miss is STRUCTURALLY UNREACHABLE, closed

`royalchallengers.bengaluru` looked one step from a pair (Kohli 2026-04-29, before=0/after=12,
28 dateless posts). It is not reachable:

- Its dated posts span **2026-05-31 → 2026-08-14**, and **0 posts predate 2026-04-29**.
- The 40-post cap only reaches back to late May, so its *undated* posts cannot predate the
  event either.
- Grid backfill confirmed it empirically: 28 grid dates found, **0 matched a dateless post**.

⇒ Straddling that event would require fetching posts older than the cap — **history
extension, explicitly forbidden for RCB**. Closed, not retried. The same reasoning likely
applies to `karanaujla` (same event, same cap).

**Generalisable:** a near-miss with `before=0` is only worth pursuing when the neighbour's
collected window actually extends earlier than the event date. Check the neighbour's
min(posted_at) against the event BEFORE spending a backfill run on it.

## Next actions
- Grid-date `royalchallengers.bengaluru` + `karanaujla` — both are **one step from a pair**
  (Kohli 2026-04-29, before=0/after=12 and 0/11, each with 28 dateless posts). Dating existing
  posts is metadata completion, NOT the disallowed RCB history extension.
- Deepen Bhuvan Bam's 5 contentless neighbours (gurfatehpirzada, nikkhiladvani, mohitvaru,
  karanjohar, pratibha_ranta) — all have 0 posts, 0 videos, and no YouTube handle found.
- Instagram adapter: re-test each cycle; still intermittent.

---

# (earlier) CYCLE 1 DETAIL

**A fresh session resuming this loop should read THIS section first — it is the live state.**

## Stats: baseline → after cycle 1 (259 creators)

| | baseline | after cycle 1 |
|---|---|---|
| Instagram attempted | 121 (46.7%) | 121 (46.7%) |
| Instagram with content | 36 (13.9%) | 36 (13.9%) |
| **YouTube attempted** | **259 (100%)** | **259 (100%)** ✅ |
| YouTube with handle | 41 (15.8%) | 41 (15.8%) — of those 39 deepened (95.1%) |
| **Reddit attempted** | 36 (13.9%) | **55 (21.2%)** |
| Reddit with content | 16 (6.2%) | 18 (6.9%) |
| Reddit NAME-GATED | 215 (83%) | **200 (77%)** |
| Reddit untouched | 8 (3.1%) | **5 (1.9%)** |
| **COMPUTABLE PAIRS** | **3** | **4** ✅ |
| Collaboration edge pairs | 161 | 161 |

## 🎯 4th computable pair — Virat Kohli ↔ PV Sindhu

| Creator | Event | Neighbour | before | after |
|---|---|---|---|---|
| Virat Kohli | 2026-04-29 | **PV Sindhu** | 3 | 12 |
| Cristiano Ronaldo | 2026-07-21 | LeBron James | 17 | 179 |
| Sania Mirza | 2026-08-01 | Parikshit Balochi | 12 | 2 |
| mrbeast | 2026-08-12 | CarryMinati | 69 | 13 |

Enabled by the grid date backfill (**62 posts newly dated** this cycle), which gave PV Sindhu
pre-event activity she previously lacked.

## ⚠️ PHASE 1 CONCLUSION WAS WRONG — REVERTED TO SEQUENTIAL

The burst test said Instagram-on-browser + Reddit-on-adapter don't contend. **Under sustained
load they do.** Reddit ran cleanly for ~8 minutes, then every search began failing
(`ok: false`) roughly 4 minutes after the concurrent Instagram browser job started — Mumbai
Indians, Prajakta Koli, Sania Mirza all failed. The moment the Instagram job finished, the
*same queries* returned real results immediately.

⇒ **A 3-call burst is not a valid concurrency test**, the same error class as the
single-probe throttle test this project already learned twice. **Run Instagram → Reddit
sequentially.** The standing rule stands; my Phase 1 clearance is withdrawn.

## ⚠️ REAL-NAME BACKFILL INTRODUCED A FALSE-POSITIVE CLASS — found and fixed

`mentions_creator` matched ANY name token >3 chars. That is right for a distinctive surname
and catastrophic for a generic organisation name harvested from a YouTube channel title:
**"Fitness Standards Council" matched 11 r/india posts** on bare tokens — including
*"Democracy is a true Kaliyug construct"* and *"Bell jar"*. Same false-positive class as the
88% Reddit purge, resurfacing because backfilled names are multi-word and generic.

**Fixed**: `_GENERIC_NAME_TOKENS` stoplist; a name made entirely of generic tokens now
requires the **full phrase**. Verified on 8 cases including the real failures. **Purged the
10 bad rows** (10 posts, 67 comments, 10 links).

## ⚠️ Two data-integrity items this cycle

1. **Duplicate creator row created and removed.** `--target-list` on Reddit inserted a second
   `Mumbiker Nikhil` because the original has `instagram_handle=NULL`, so
   `get_or_create_creator` could not match it. Verified empty across all 10 `creator_id`
   tables, deleted. `creators` back to **259**. **Creators with NULL instagram_handle are a
   duplicate-insert hazard on any `--target-list` run.**
2. **Sub-routing bug caught in dry run before it wrote**: the category fallback sent
   Philadelphia 76ers / Matthew Dellavedova to r/ipl+r/Cricket and Ohio State Football to
   r/IndianFootball. Added r/nba routing (proven in-repo via LeBron) and an explicit skip for
   US college sports and E1 Series. 18 assigned, 3 skipped.

## Reddit yield is poor and worth stating plainly
Of 38 creators searched, **only 1 produced posts — and those were the false positives**. The
handle-named ones return 0 by construction; the real-named ones mostly returned nothing
usable. **Reddit is not currently a productive lever** for this creator set.

## Next cycle should
- Run Instagram (browser grid dates) and Reddit **sequentially**, never concurrently.
- Continue grid date backfill — it is what produced the 4th pair.
- Kerala Blasters roster extraction (once per loop, not yet done).
- Instagram adapter re-check: still 429 as of last test.

# PHASE 1L — (2026-08-18, agent-reach routing + browser-only pivot)

## TASK 1 ⛔ — the adapter block is NOT a pacing problem, and that is now settled

Ran this round through **agent-reach** rather than the prior ad-hoc pattern. Two things came
out of its guidance:

- `agent-reach doctor` reports Instagram's backends as **`["OpenCLI"]` — the only one.** There
  was never an alternate route to switch to; the previous four rounds were already on the
  correct backend.
- Its substantive advice is *re-login and reduce frequency*, so the retry used **25–50s
  jittered gaps** with latency/degradation monitoring instead of 4s rapid-fire.

**Result: HTTP 429 on the FIRST request.** Frequency is therefore not the variable — the block
is persistent and predates this session's traffic. Backed off after 2 consecutive failures
rather than pushing to a hard block.

## TASK 2 ✅ — browser-only path: partly viable, and the limits are measured not guessed

Validated against **ground truth** (re-fetch posts whose metadata we already hold, compare):

| source | date | like count | comment count |
|---|---|---|---|
| **post page** | **0/4** | 2/4 and **WRONG** | **0/4** |
| **profile grid alt-text** | present for some posts, **4/4 agreed with DB** | — | — |

The post page's like numbers belong to **suggested posts**, not the subject post — DB 172,598
vs extracted `"8"`; DB 228,603 vs `"3,132"`. **Parsing that page would write corrupt data**, so
it is reported as not viable rather than forced into a fragile parser.

⇒ New tool `backfill_dates_from_grid.py`: browser-only, conservative jittered pacing, never
overwrites an existing date (conflicts are reported, not applied).

## TASK 3 ⚠️ — the mechanism works, but it CANNOT REACH the posts that matter

Ran across all 5 priority creators: **19 posts newly dated, 6 conflicts, 0 failures.**

**But 0 of the 14 priority SPONSORED posts got a date, and all 25 sponsored events remain
dateless.** The predicted ceiling held exactly:

> Instagram uses the **caption** as a post's alt-text when one exists, falling back to
> "Photo by X on \<date\>" only when it does not. **Sponsored posts essentially always have
> captions**, so they are precisely the posts this method cannot date.

⇒ **The highest-value target is structurally out of reach of the working path.** The 19 dates
landed on caption-less posts, which were never the bottleneck. `posted_at` 435 → 454.
**Computable pairs stay at 3** — unchanged, because a new pair needs a dated *sponsored* event.

### 📐 Grid dates are accurate ±1 day, and the error is systematic
Across 54 grid-dated entries: **29 agreed exactly, 6 differed by exactly one day, 19 were new.**
Every single conflict was the grid reading **one day EARLIER** than the DB — never later, never
by more than a day. That is a **timezone-boundary effect** on posts published near midnight,
not random noise (posts published mid-day agree exactly).

**Left uncorrected deliberately.** Shifting all 19 by +1 day would be inferring from a 6-sample
pattern, and the existing dates came from a different source (adapter metadata) whose own
timezone basis is unverified. For before/after straddle analysis a 1-day bias is immaterial —
events and neighbour activity are months apart — but it must be stated, not hidden.

### 🔍 Detection-hypothesis check, reported proactively
The browser path shows **no degradation signals**: 5/5 creator grids fetched cleanly, page
sizes consistent (9.6–19k chars), no latency drift, no partial payloads, no intermittent
failures. Treated as *not yet flagged* rather than safe — jittered 2.5–4.5s between scrolls,
15–30s between creators, back off on two consecutive failures rather than probing for a
ceiling.

**The asymmetry itself remains the strongest evidence for the behavioural-detection
hypothesis:** an IP/volume block would hit both paths, and the browser path is completely
clean while the adapter 429s on request one.

# PHASE 1K — (2026-08-18, stub cleanup + quota rotation + Instagram retry)

## 🎯 COMPUTABLE TRAINING PAIRS 2 → 3 — and YouTube alone produced the third

| Creator | Event date | Neighbour | before | after |
|---|---|---|---|---|
| Cristiano Ronaldo | 2026-07-21 | LeBron James | 17 | 179 |
| **Sania Mirza** | **2026-08-01** | **parikshitbalochi** | **12** | **2** |
| mrbeast | 2026-08-12 | CarryMinati | 66 | 13 |

`parikshitbalochi` was one of the 15 channels discovered and deepened THIS round. Checked
where its straddling activity comes from rather than assuming:

```
parikshitbalochi BEFORE 2026-08-01 — instagram: 0   youtube: 12   reddit: 0
                 AFTER  2026-08-01 — instagram: 0   youtube:  2   reddit: 0
```

⇒ **100% YouTube.** The neighbour has no Instagram or Reddit activity at all on either side
of the event.

**Taken with last round's Reddit-only pair, the pattern is now explicit: of the 3 computable
pairs, 2 exist ONLY because of non-Instagram data.** Instagram-only straddle checking would
report 1. The cross-platform check is not a refinement — it is the difference between 1 and 3.

⚠️ **Correction to my own mid-round report:** I stated the new YouTube coverage "didn't add a
third" — that was measured BEFORE the deepening job finished and is wrong. Re-measuring after
a background job completes is the discipline that caught it.

## TASK 1 ✅ — Gujarat Titans stub re-pointed and deleted; creators back to 259

The stub held 1 genuinely-collected Reddit post (*"Absolute Stunning Catch by Gill!"* — Gill
is their captain, so real and relevant). Re-pointed to the real creator
(`Gujarat Titans`, `instagram_handle=gujarat_titans`, `team`), **verified the re-point landed
before deleting anything** (real creator now 64 `reddit_posts` / 69 links), then re-checked
the stub against every `creator_id`-bearing table and deleted it.

**`creators` 260 → 259** — the correct baseline restored, and last round's bug fully cleaned.

## TASK 2 ⛔ — Instagram STILL blocked, and the stale-session hypothesis is DISPROVEN

Chrome was fully killed and relaunched with clean tab groups; `opencli doctor` reported the
extension connected and 0.3s connectivity. The sustained scan still returned **HTTP 429 on 3
consecutive requests**.

⇒ **The 429 is not stale tab-lease/session state.** That was worth testing and it is now
ruled out. Tasks 1.2 / 1.3 / 1.4 remain untouched — fourth round blocked, not forced.

### 🔍 NEW: the BROWSER path works while the ADAPTER is throttled
Tested at the same moment the adapter was returning 429:

```
opencli instagram user/profile <handle>   -> HTTP 429
opencli browser open + extract virat.kohli -> real page, 10,099 chars, 4 post links
```

⇒ The block is **specific to the adapter's API-style requests**, not the account, the login,
or the browser session — consistent with the user being able to browse Instagram normally.

**Why this does NOT unblock Tasks 1.2–1.4 today, stated plainly:**
- **1.2** needs `instagram user` for the *listing* side of the caption comparison — that IS
  the adapter. Blocked by definition.
- **1.3 / 1.4** both start with an `instagram profile` adapter call in `process_creator`, so
  a creator fails before the browser grid is ever reached.

**But it is a real route for a future round:** a browser-only collection path would sidestep
the adapter entirely. That is a deliberate build, not something to improvise unattended.

## TASK 3 ✅ — quota rotation works; the ENTIRE YouTube backlog is now cleared

⚠️ **The first rotation attempt failed completely and silently — worth understanding.**
It rotated only on `403 + "quota"`, but **an exhausted YouTube search quota surfaces as
HTTP 429 `rateLimitExceeded`**. So rotation never fired, and **two entirely healthy keys went
unused** while all 137 creators failed. Two bugs compounded it:

1. `youtube_api_get` called `e.read()` to inspect the body, which **consumes the stream**;
   re-raising then left callers with an empty body, so their own quota check silently failed
   and logged 137 blank `search failed for X:` warnings. The body is now stashed on the
   exception as `body_text`.
2. Rotation now triggers on **429 OR 403-quota**.

Diagnosed by testing each key independently rather than guessing:

```
key1  channels: OK   search: HTTP 429 rateLimitExceeded
key2  channels: OK   search: OK
key3  channels: OK   search: OK
```

**After the fix, one run cleared the whole backlog**, rotating 1 → 2 → 3:

| | |
|---|---|
| Creators searched this run | **137** |
| Found (exact-handle-equality + scale) | **15** |
| Quota spent | 13,813 units across keys 1→2→3 |
| **Cumulative coverage** | **249 of 249 — backlog CLEARED** |
| Cumulative found | **30** · needs_review 36 · no confident match 140 · no channel 41 · clash 2 |
| `creators.youtube_handle` | 26 → **41** |

Examples: `@mrbeast` (513M), `@mumbaiindians` (8.43M), `@keralablasters.` (829k),
`@mumbaicityfc` (119k), `@nisha_optimist` (103k), `@ohiostatefb` (82.4k).

**Honest read on the 140 `no_confident_match`:** that is 56% of creators, and it is the strict
rule working as intended after three verification failures last round — a fan channel or a
namesake is not a match. They are recorded, not lost.

### ✅ Name-persistence fix CONFIRMED WORKING (not assumed)
Instagram deepening is blocked, so the fix was verified by exercising the exact upsert SQL
against the live DB, reproducing the real failure sequence:

```
after comment-author insert (username only) : (None, None)
after creator-profile upsert                : ('Real Person Name', 'a real bio', 100)
after a later NULL-name rewrite             : ('Real Person Name', 'a real bio', 200)
  fills name over a username-only row : PASS
  NULL write does not wipe good name  : PASS
```

## TASK 4 — did not run, and should not be implied to have

Reddit was gated on creators gaining a real name, which is gated on Instagram deepening,
which is blocked. **No Reddit work happened this round.**

# PHASE 1J — (2026-08-17 late, cleanup + backfill + retry round)

## 🎯 COMPUTABLE TRAINING PAIRS 1 → 2, and REDDIT is what unlocked the second

| Creator | Event | Date | Neighbour | before | after |
|---|---|---|---|---|---|
| `mrbeast` | Db5rzczsSV5 | 2026-08-12 | CarryMinati | 66 | 13 |
| **Cristiano Ronaldo** | **DbDp7T4olyC** | **2026-07-21** | **LeBron James** | **17** | **179** |

The Ronaldo↔LeBron pair was **not** computable last round (Instagram-only: before=0). Checked
where the before-side activity actually comes from rather than assuming:

```
LeBron activity BEFORE 2026-07-21 —  instagram: 0   youtube: 0   reddit: 17
```

⇒ **It is computable ONLY because of Reddit data.** That is a direct answer to "can
YouTube/Reddit coverage surface pairs Instagram alone cannot": **yes, demonstrably.** The
cross-platform straddle check should be the standard measurement from now on — the
Instagram-only version undercounts.

## TASK 1 — 4 of 5 blank rows deleted; 1 was NOT empty

These were created by **my own bug last round**, and my cleanup was incomplete: I cleared the
`reddit_handles` pollution but missed that `get_or_create_creator` had already INSERTED 5
blank creator rows. The orchestrator caught that, not me.

Verified against **every** table carrying `creator_id` (enumerated from `information_schema`,
not from memory), plus whether each name is the sole resolver for another creator's edges:

| Row | Verdict |
|---|---|
| `ajinkyarahane`, `delhipremierleaguet20`, `karanaujla`, `ptushaofficial` | empty → **DELETED** |
| `gujarat_titans` | ⚠️ **NOT EMPTY — kept and reported** |

All four deleted rows *are* referenced as handles by other `creator_related_accounts` rows,
but a real creator owns that `instagram_handle` in each case, so those edges resolve through
the real creator — deleting the blank row destroys nothing.

⚠️ **`gujarat_titans` holds 1 `reddit_posts` + 1 `reddit_post_creators` row.** `r/gujarat_titans`
is a genuine subreddit, so the killed `--handles` run collected a real post onto the blank row
before being stopped. **Needs a decision:** re-point that post to the real `gujarat_titans`
creator and then delete, or delete both. Not done unilaterally — it is real scraped data.

**`creators`: 264 → 260.**

## TASK 2 — real-name backfill resolved ZERO, and the diagnosis is the useful part

Free sources are **exhausted**: all 13 recoverable names were already taken last round.

| Of the 231 handle-named creators | count |
|---|---|
| No `instagram_profiles` row at all | **101** |
| Row exists but `full_name` is EMPTY | **130** |
| Row with a usable `full_name` | **0** |

Project-wide, only **15 of 13,746** `instagram_profiles` rows carry a `full_name` at all.

### ✅ Root cause found — a persistence gap, not a data-availability gap
`instagram_profiles` has **two writers**:
- the comment-author path inserts **username only** (`ON CONFLICT DO NOTHING`)
- the creator-profile path *does* pass `full_name`, but its `ON CONFLICT DO UPDATE` refreshed
  **only the counts**

So any creator whose username was first seen as a **comment author** could never have its name
filled in — precisely the 130. Fixed: `full_name`/`bio` now use
`coalesce(excluded, existing)` in the update clause, so a later NULL-bearing write also cannot
wipe a good name.

**The profile fetch already retrieves the name — it was simply never persisted.** Populating
the existing 231 still needs Instagram calls (blocked), but every future deepening run now
fills names for free.

## TASK 3 — Instagram STILL BLOCKED (third round); YouTube advanced; Reddit had nothing new

**Instagram: HTTP 429 on 3 consecutive requests**, with `opencli doctor` reporting the browser
healthy — so it is the platform limit, not the environment. Tasks 1.2/1.3/1.4 remain untouched.
**Not forced.**

**YouTube — continued from creator #90:**

| | this run | cumulative |
|---|---|---|
| Creators searched | 23 | **112 of 248** |
| Found (exact-handle-equality + scale) | **6** | **15** |
| `needs_review` (evidence kept, not written) | — | 36 |
| No confident match / no channel | 17 | 60 |
| Quota | 2,320 units, then **daily Search-Queries quota exhausted — stopped cleanly** | |

All 6 passed the strict rule: `@indiansuperleague` (2.56M), `@jumperaj` (1.02M),
`@lucknowsupergiants` (750k), `@indian_kushti_tv` (282k), `@inspireinstituteofsport` (26.5k),
`@jeet_selal` (3.3k). **Deepening completed: `youtube_videos` 579 → 797 (+218), creators with
video content 19 → 25, `youtube_comments` 25,629, `youtube_handle` 26.** (Superseded by
Phase 1K's totals: videos 1,227, comments 37,971, creators with video 39.) Only `jeet_selal`
lost volume to the recency window (18 kept / 22 stale); the other five returned a full 40.

⚠️ **Re-checked the pair count after that deepening landed: still 2.** The new YouTube data
did not add a third — the six newly-deepened channels belong to creators who are not
graph-connected to a dated sponsorship event. Coverage alone does not manufacture pairs;
it has to land on the right side of an existing edge, which is the same lesson the
Instagram coverage-vs-promotion experiment produced.

**Reddit — nothing new to run, and that is the honest answer.** The round's criterion was to
run Reddit for creators that gained a real name in Task 2; Task 2 resolved **0**. Last round's
pilot did finish, though, and its per-sub relevance is worth recording:

| Creator | sub | kept | off-topic |
|---|---|---|---|
| Gujarat Titans | r/Cricket | **40** | 0 |
| Gujarat Titans | r/ipl | 28 | 12 |
| Delhi Premier League T20 | r/IndianCricket | 16 | 24 |
| Ajinkya Rahane | r/IndianCricket | 15 | 8 |
| Ajinkya Rahane | r/Cricket | 11 | 5 |
| Karan Aujla | r/india, r/IndianMusic | **0** | 0 |
| P.T.Usha | r/india, r/Athletics | **0** | 5 |

`reddit_post_creators` 435 → **687**, creators with Reddit content 13 → **17**. Yield is
**highly uneven** — cricket subs are productive, `r/india` and `r/IndianMusic` returned nothing
usable. Sub choice matters far more than creator count.

# PHASE 1I — (2026-08-17 evening, three-track round)

## TRACK 1 — Instagram: BLOCKED, the 429 has NOT cleared

Sustained test (the only valid clearance check) returned **HTTP 429 on 3 consecutive
requests** and aborted. ~3.5 hours of cooldown was not enough. **All four Track 1 tasks
(1.1–1.4) are Instagram-bound and therefore untouched.**

One thing was still established without spending Instagram traffic:

✅ **Task 1.1 — `--limit` confirmed as the cause, from the CLI contract:**
`opencli instagram user --help` documents `--limit [value] Number of posts **default: 12**`.
That default matches the 12-item metadata ceiling exactly, which is what starved
`posts_meta` past index 11 in `orchestrator.py:447`. The live confirmation (does
`--limit 40` actually return >12 posts *with dates*) still needs one Instagram call and is
**queued, not proven**.

⚠️ **Task 1.2 remains the more important half and is untested.** Matching list LENGTHS does
not establish matching ORDER. Until a same-index caption comparison is run against a handle
that pins posts, `--limit` should be treated as a **partial** fix.

⚠️ **A misleading failure to know about:** the first sustained attempt failed with
`BROWSER_CONNECT: profile not connected`, which looks like a throttle but is just Chrome not
running. **Check `opencli doctor` before interpreting any Instagram failure** — restarting
Chrome then produced clean 429s, which is the real signal.

**Task 1.3 fresh count (the 25-vs-28 discrepancy, resolved):** **32** sponsorship events
total, **7** with `posted_at`, **25 dateless** — 25 is the backfill target. Note
`is_sponsored` is now 32 (was 18); Track C has relabelled since.

## TRACK 2 — YouTube: capability built, and 45 wrong handles caught before they stuck

`orchestrator.py` could only resolve a channel from an ALREADY-KNOWN handle
(`channels?forHandle=`) — which is *why* 248 creators had never had YouTube attempted.
`discover_youtube_handles.py` adds search-by-name with verification, checkpointing and quota
accounting.

**Results:** 89 of 248 creators searched (quota-capped at 8,975/9,000 units), then
**every result inspected rather than trusted**:

| | |
|---|---|
| Auto-accepted by the first two rule sets | 45 |
| **Wrong on inspection → all 45 reverted** | 45 |
| Re-applied under a strict rule | **9** |
| Marked `needs_review` (evidence recorded, not written) | 36 |
| Genuinely absent / rejected outright | 44 |
| `creators.youtube_handle` | 11 → **20** |

**Three successive verification rules were wrong, each caught by looking at the data:**

1. **Circular** — searched for the Instagram handle across title+description+**customUrl**.
   A channel's customUrl derives from its own name, so any name-similar channel trivially
   "corroborated" itself. Accepted `@camgreen-to5kr` (**0 subs**) and
   `@fitnesssport-entrenandoenc6492` (Spanish, unrelated).
2. **Corroboration-only** — description references the Instagram handle. But **fan channels
   legitimately do that**: `fcgoaofficial → @ubaidmellow` (29 subs, no name relationship at
   all), `chennaiipl → @chennaiipl-msd` (54 subs), `imbhuvi → 0 subs` despite 6.3M IG
   followers.
3. **Name-match** — produced a **NAMESAKE COLLISION**: `_ramandeep.singh_`, a KKR cricketer,
   matched *"AFLM – A venture of CS Ramandeep Singh"*, a coaching institute.

⇒ **Auto-write now requires the customUrl to be essentially the SAME STRING as the creator's
own handle, plus real scale (≥1000 subs, owner-chosen handle).** Fans don't get the exact
handle and namesakes rarely match one. Everything else returns `NEEDS REVIEW` with its
evidence. Tested against all six real failure cases: 6/6 correct.

**Task 2.2 — deepening the found channels:** `youtube_videos` 315 → **579 (+264)**, creators
with video content **10 → 19**, `youtube_comments` **24,236**. `BBKiVines` returned 0 videos
— all older than the recency cutoff, consistent with the standing "posting frequency, not
audience size, predicts volume" lesson.

## TRACK 3 — Reddit: the coverage gap has a DEEPER cause than "never attempted"

**Reddit's topic-sub search is structurally blocked for 244 of 259 creators, and would have
returned ~0 even if it had been run.** The mechanism searches a sub for `creators.name`, but
bulk promotion set **`name = instagram_handle`** for every promoted row.

Proven with two calls rather than assumed:

```
reddit search "rohitsharma45" in r/Cricket ->  0 results
reddit search "Rohit Sharma"  in r/Cricket -> 10 results
```

⇒ P0.5's "the 240+ bulk-promoted creators have never had Reddit attempted" is correct but
incomplete: **attempting it without fixing names produces nothing.** Assigning topic subs to
231 creators would have burned ~460 name-searches to discover that.

**Fixed what could be fixed locally, at zero network cost:** recovered 13 real names from
`instagram_profiles.full_name` and `youtube_channels.title`
(`ajinkyarahane → Ajinkya Rahane`, `gujarat_titans → Gujarat Titans`, …). **231 still hold
handle-as-name**, and recovering those needs Instagram profile fetches (429-blocked today)
or more YouTube coverage.

⚠️ **Own error, caught and reverted:** ran the pilot first with
`orchestrator.py --platform reddit --handles <ig_handle>`, which sets `reddit_handles=[h]` —
i.e. it treats the Instagram handle as a **creator-specific subreddit** (r/ajinkyarahane) and
merges it in. Killed the run and cleared all 5 polluted rows; `reddit_handles` back to `[]`,
topic subs intact. **For Reddit, use `--target-list`, never `--handles`.**

# PHASE 1H — (2026-08-17, autonomous overnight round)

**Live status — updated as the run proceeds, not written at the end.**

Base state confirmed before starting: `creators` **259**, distinct pairs **152**, resolve
rate 31%. Matches the Phase 1G close exactly, so this round built on a verified base.

## 🛑 ROUND ENDED ON A GENUINE HTTP 429 — Instagram budget exhausted for the day

The final deepening batch failed **8 of 8 creators, ~4 seconds apart**, with:

```
opencli instagram profile mihirahuja_ failed: HTTP 429 - make sure you are logged in
```

This is the **real platform rate limit**, not the network-layer `chrome-error` throttle and
not a grid stall — it matches this file's own criterion verbatim (*"a real limit is an HTTP
429 from the platform"*), and the near-instant, uniform failure across every handle confirms
it is systemic rather than per-account.

**Response taken, per the standing rules: stopped Instagram work immediately.** No probing,
no retrying, no "see if it works now". Cooldown is measured in **hours**.

**Observed daily ceiling — useful for planning, this is the largest Instagram day the
project has had:**

| Activity | Post-page fetches (≈3 opencli calls each) |
|---|---|
| Backlog co-author scan | 245 |
| Resumed scan after kills | 189 + 50 |
| Scan of newly deepened posts | 195 |
| Profile + grid fetches for classification | ~230 |
| Deepening (13 creators × ~40 posts + comments) | ~520 |

Roughly **1,400+ post/profile fetches ≈ 3,000–4,000 opencli calls in one day.** The 429
arrived after that, which is the first time this project has a rough number for where the
ceiling sits.

**Nothing else was runnable:** only 1 of 259 creators lacks YouTube content and 0 lack Reddit
rows — the 248 sheet-promoted creators carry Instagram handles only. So every remaining
mechanism in the task list (co-author extraction, deepening, follower-graph, roster,
brand-anchored) is Instagram-bound. **The loop was stopped rather than left ticking**, since
further ticks could only tempt a probe-and-resume, which this file already documents as the
wrong move twice over.

**To resume next session:** wait hours, then verify with a **sustained 10-15 request scan**,
never a single probe. `collab_edges.py --only-new` is safe to run first — it resumes cleanly
and there were 0 unscanned posts at stop time, so the first new work is a deepening batch.

## 🎯 FIRST FULLY COMPUTABLE TRAINING PAIR — Review-1 go/no-go moved 0 → 1

CAPSTONE_NEXT_STEPS' Review-1 criterion reads: *"At least one (ideally 3-5) fully computable
training pair — a sponsorship event that is BOTH graph-connected to another creator AND has
pre-event data on that neighbour. **Currently 0**."*

**It is now 1:**

| Creator | Event | Date | Neighbour | posts before | posts after |
|---|---|---|---|---|---|
| `mrbeast` | `Db5rzczsSV5` | 2026-08-12 | CarryMinati | **11** | **1** |

**`mrbeast` was deepened THIS ROUND**, by the "creators already in a resolved pair but with
no content of their own" targeting rule. So that rule did not just win on pairs-per-post —
it produced the project's first computable training pair.

⚠️ **Honest caveats, none of them small:**
- **It is 1, against a target of "ideally 3-5".** Not sufficient on its own.
- The after-side is a single post. Thin for any before/after delta.
- 11 of the 12 connected dated events have **0** pre-event neighbour data.
- **These counts only see posts that HAVE `posted_at` — 31% of them.** The metadata gap
  below is directly suppressing this metric, so the true figure is unknown and probably
  higher. **Fixing `orchestrator.py:447` is the highest-value action available**, and it is
  now measurable: re-run this query after the fix and watch the number move.

## 0. VERIFIED TOTALS (live DB, close of round)

| | start of round | now |
|---|---|---|
| `creators` | 259 | **259** (no promotions — correct, review is the user's) |
| `instagram_posts` | 1,224 | **1,419** (+195) |
| Creators with IG content | 31 | **36** |
| `instagram_comments` | 13,097 | **18,803** (+5,706) |
| Posts unscanned for co-authors | 245 | **0 — fully cleared** |
| `creator_related_accounts` | 508 | **668** (+160) |
| Resolved rows | 157 | **181** (+24) |
| **Distinct pairs** | 152 | **161** (+9) |
| `has_paid_partnership_label` | 12 | **24** (+12) |
| Sheet rows | 995 (full!) | **1,066+** |

**Posts with `posted_at`: 435 of 1,419 (31%)** — see the metadata finding below; this is the
number that actually gates Review 1.

## ⚠️ FIVE SILENT-WRITE FAILURES IN ONE NIGHT — the infrastructure lesson of this round

The end-of-run sheet push failed **five times**: two external kills and **three
`ConnectionResetError(10054)`**. Every one was silent — the caller logs a warning and
continues, so candidates simply never appeared and nothing flagged it.

Three separate defects, each found only by checking the data rather than the exit code:

1. **The sheet was FULL** (995 of 995 allocated rows). Explicit-range writes do not extend
   a worksheet, so every push had been failing. Fixed: `push_candidates` now calls
   `add_rows()` with headroom.
2. **`coauthor_checkpoint.json` is REWRITTEN per run, not accumulated.** It held 90 entries
   before the final 50-post run and 17 after. So a *completing* run silently discards what a
   *killed* run found — and I only caught it because the recovery script's pending count
   collapsed between two invocations.
3. **Sheets calls had no retry**, while each one builds a fresh authorized client (dozens of
   TLS + auth handshakes per batch). Fixed: `_retry` with backoff on `read_rows`,
   `push_candidates`, `append_brand_signal`, `update_category`.

⇒ **The durable record is the DATABASE, not the checkpoint file.**
`creator_related_accounts` rows are flushed per post and never overwritten.
`push_checkpoint_candidates.py --from-db` recovers co-authors that are neither creators nor
on the sheet: **181 found that way vs 63 from the checkpoint** — a backlog accumulated
across every run whose push has ever failed, not just tonight's.

**Standing rule earned:** *a warning-and-continue on a write path hides a permanent failure
exactly as well as a transient one.* Verify writes by reading the data back, not by checking
that the code ran — which is this project's oldest recurring lesson, now with three fresh
instances in one night.

## TASK 2 — deepening (5 of 6 creators, +195 posts)

Targeted at creators who already sit in a resolved pair but had **no content of their own** —
scraping them can surface the reciprocal side plus new co-authors.

| | before | after |
|---|---|---|
| `instagram_posts` | 1,224 | **1,419** (+195) |
| Creators with IG content | 31 | **36** |
| `instagram_comments` | 13,097 | **18,803** |

`jimmysheirgill` failed (grid path) — consistent with it being one of the handles that also
rejects the `instagram profile` adapter. Not retried.

**This batch is what cracked the metadata bug below** — fresh posts reproduced the 31% rate
exactly, which disproved the "just re-scrape" fix.

### ⚠️ Killed mid-scan, and the incremental flush earned its keep again

The follow-up co-author scan over those 195 posts was **stopped externally ~6 posts in**
(0 failures logged, environment healthy afterwards — daemon, extension and Chrome all fine,
so this was a harness/session kill, not a crash). Work already done survived: **+6 edge rows,
+2 resolved, +1 pair**, all flushed per-post.

**The documented tab-lease leak reproduced exactly.** After the kill, all five named sessions
(`collabx`, `classify`, `catfix`, `gridtest`, `datetest`) were still holding leases and had
to be released by hand before resuming — matching the standing lesson that a killed collab
run strands its lease. **Release leases before resuming after any kill**, or the next run
degrades against a browser that is still holding tabs.

## 📊 YIELD BY MECHANISM — the actionable comparison from this round

Same mechanism (`collab_edges.py`), two different post populations, very different yield:

| Posts scanned | Source | New distinct pairs |
|---|---|---|
| 245 | Backlog of already-covered creators | **+1** |
| 195 | **Creators deepened *because* they already sat in a resolved pair** | **+7** (so far, scan still running) |

**~17x better pairs-per-post from targeted deepening.** The targeting rule that produced it:
pick creators who are *already referenced by 2+ other creators* in
`creator_related_accounts` but have **no content of their own**, then scrape and scan them.
Their co-authors are disproportionately other creators, so edges resolve immediately instead
of landing as dangling rows awaiting review.

⇒ **Recommended default for future rounds:** deepen by graph position, not by follower count
or list order. This is the first mechanism this project has found that produces resolved
pairs *without* waiting on a user review pass.

## 🚨 BIGGEST FINDING OF THE ROUND — 69% of posts have NO DATE and NO ENGAGEMENT DATA

Found while trying to answer the report question "any newly-connected creator with a
sponsorship event that now has data on both sides of the event date". **That question
cannot currently be answered for most events, and the reason is structural.**

| | total | with `posted_at` |
|---|---|---|
| `instagram_posts` | 1,224 | **374 (31%)** |
| **paid-partnership posts** | 19 | **5** |
| **`is_sponsored` posts** | 18 | **6** |

**Root cause, established by a perfect correlation, not a guess:** all **850** rows lacking
`posted_at` ALSO lack `media_type` AND `like_count`. That is the exact signature this
project already documented for the caption bug — *listing-sourced rows*: the grid listing
yields a post ID with an empty metadata dict, so every field lands None. **The same
root-cause class is still live for dates and engagement.**

⚠️ **This is worse than a missing-dates problem.** `like_count` / `comment_count` are NULL
on the same 850 rows — that is the engagement data GAIL needs to compute before/after
deltas. So the gap hits both halves of a training pair: no event date to straddle, and no
engagement series to measure.

**Why this matters more than tonight's edge counts:** CAPSTONE_NEXT_STEPS' Review-1 go/no-go
criterion is "at least one fully computable training pair — a sponsorship event BOTH
graph-connected AND with pre-event data on that neighbour." **That metric is currently
capped by this, not by graph density.** We have 153 pairs and 19 paid-partnership posts,
but only 5 of those posts even have a date.

**Recoverable? PARTIALLY — and I tested this rather than assuming it.** An earlier draft of
this section said "almost certainly recoverable". **That was wrong, and the correction
matters because it changes what the next session should attempt:**

| Route | Result (measured, 2026-08-17) |
|---|---|
| Post page (`/p/<id>/` extract) | **0%** — no dates, no relative-age tokens at all |
| Profile grid alt-text | **~30%** — 3 of 10 entries carried "on August 13, 2026" |

Why the grid is partial: Instagram uses the **caption** as a post's alt-text when one
exists, and only falls back to "Photo by X on <date>" boilerplate when it doesn't. So the
posts that expose a date are largely the caption-less ones — close to the inverse of the
posts we most want dated.

⇒ **Do NOT plan on a cheap grid-based backfill.** It would recover roughly a third, biased
toward caption-less posts.

### ✅ ROOT CAUSE FOUND — `orchestrator.py:447`, and it is not a parsing problem at all

Fresh scrapes reproduce the gap exactly, which is what cracked it: the deepening batch run
this round wrote 195 new posts and **only 61 (31%) got a date** — the same ratio as the old
rows. So re-scraping would NOT have fixed it, and the fix I first suggested was wrong.

Per-creator, the pattern is unmistakable — **~12 of ~40 posts get metadata, every time**:

```
ajinkyarahane   39 posts, 11 dated      taarukraina  34 posts, 10 dated
mrbeast         37 posts,  9 dated      ptushaofficial 38 posts, 10 dated
delhipremierleaguet20 40 posts, 12 dated
```

The orchestrator builds each post row from **two separate calls matched POSITIONALLY**:

| source | what it gives | how many |
|---|---|---|
| `opencli instagram user <handle>` | metadata: `date`, `likes`, `comments`, `type` | **exactly 12** (verified live on 2 handles) |
| `browser find` after scrolling | post URLs | **up to 40** (the post cap) |

```python
meta = posts_meta[i] if i < len(posts_meta) else {}     # orchestrator.py:447
```

Once `i` passes 11, `meta` is `{}` and **every metadata field lands NULL** — `posted_at`,
`like_count`, `comment_count`, `media_type`. 12/40 = 30%, which matches the observed 31%
exactly. **The dates were never lost in parsing; they were never fetched.**

⚠️ **SECOND, MORE DANGEROUS BUG IN THE SAME LINE — positional matching is unsafe.** The
code's own comment admits it: *"Not guaranteed aligned if a new post landed between the two
calls."* There is a worse and permanent misalignment source it does not mention:
**Instagram pins up to 3 posts to the top of a profile grid.** Pinned posts appear FIRST in
`browser find` order but are NOT newest, while `instagram user` lists by recency. On any
creator with a pinned post, the two lists are offset — so post N is written with post M's
date and like count. That is **silent cross-post metadata contamination**, the same class as
the 2026-08-11 caption incident, and nothing downstream would catch it because a wrong-but-
plausible date raises no error. **Not yet confirmed on real data — it is a code-reading
finding and needs a targeted check** (compare a stored `posted_at` against the real post
page for a creator known to pin).

**Fix options, both needing a decision this round could not make unattended:**
1. Fetch metadata per post from the post page already being opened (the loop opens every
   post anyway) — correct and alignment-proof, but the page must actually expose the date,
   and the test above found **no date on the post page**, so this needs solving first.
2. Raise the listing depth if `instagram user` can be paged beyond 12 — cheapest if possible.

Either way the honest status is: **cause identified precisely, fix not obvious, and the
positional-matching risk should be treated as a live correctness bug regardless.**

## TASK 1 — co-author extraction (PRIMARY) — SCAN COMPLETE

`collab_edges.py --only-new` over the backlog: **245 posts, 0 failures, 51 minutes.**
Throttle verified clear beforehand the correct way — **30 sustained browser fetches, 0
failures**, not a single probe.

| | before | after |
|---|---|---|
| Unscanned posts | 245 | **0 — backlog fully cleared** |
| `creator_related_accounts` | 508 | **567** (+59) |
| Resolved rows | 157 | **163** (+6) |
| Distinct pairs | 152 | **153** (+1) |
| `has_paid_partnership_label` | 12 | **19 (+7)** |
| Caption fixes | — | 15 |

**+7 paid-partnership posts is the most valuable output** — native Instagram sponsorship
declarations, the highest-precision treatment signal available, on creators not previously
known to carry any: **CarryMinati 5, Bhuvan Bam 4, Prajakta Koli 2**. Track C should
re-label; `is_sponsored` is still 18 and is theirs to update.

⚠️ **Immediate pair yield is LOW (+1) and that is NOT a failure.** New co-authors are not
creators yet, and this round is explicitly barred from promoting them (`approval_status` is
the user's column). The payoff is candidates surfaced for the next review pass — precisely
the mechanism that produced **+142 pairs last round from zero new scraping**. Judge this
mechanism on candidates surfaced, not on same-night pairs.

### Candidates pushed — 59, with the category spread that was the point of Task 0

| category | count |
|---|---|
| `other` | **24 (41%)** |
| `fitness_influencer` | 17 |
| `lifestyle_influencer` | 9 |
| `athlete` | 7 |
| `team` | 2 |

`approval_status` blank on all 59 (verified). Grid relevance recorded on 52 of 59, **mean
0.20** — consistent with the 0.30 measured in validation, and further evidence that a hard
majority-relevance gate would reject nearly every candidate.

**Honest read: `other` went 100% → 41% for co-author rows.** Every such row used to be
`other` unconditionally, so this is a real improvement — but the residue is twice the 20%
that held-out validation predicted, because production candidates skew toward small
accounts with emptier bios than the validation sample.

⚠️ **A misclassification found by inspecting the output, not by the tests:**
`@attirebyajaygandhi` — real profile "Attire by Ajay Gandhi / *Stitching dreams into a
gorgeous reality!*" — is a **couture brand**, and it landed as `team`. It is both a missed
BRAND and a wrong category. The brand rules key on legal-entity suffixes and commerce
language, and this bio has neither. Together with `tserieshealthandfitness`, that is **two
brand escapes in one night** — the brand detector's recall is clearly weak on
non-incorporated consumer brands, and human review remains the real gate. Do not treat
write-time brand routing as sufficient on its own.

**Brand routing confirmed working in production**, from the live log:
`BRAND eshviv -> brand_signals of @ballerathletik (written)` — a brand diverted to the
owning creator's `brand_signals` instead of becoming a candidate row, exactly as the
standing rule requires.

Running `collab_edges.py --only-new` over the 248 posts the deepening loop left unscanned.
Throttle was verified clear the correct way first: **30 sustained browser fetches with 0
failures** during Task 0 validation, not a single probe.

Interim, mid-run (incremental flush confirmed working — these are live DB reads while the
process is still going):

| | at launch | mid-run |
|---|---|---|
| Unscanned posts | 245 | **117** |
| `creator_related_accounts` | 508 | **544** (+36) |
| Resolved rows | 157 | **162** (+5) |
| **Distinct pairs** | 152 | **153** (+1) |

⚠️ **Expected-but-important: immediate pair yield is LOW, and that is not a failure.** New
co-authors are not creators yet, and this round is explicitly barred from promoting them
(`approval_status` is the user's column). The +5 resolved rows come from co-authors who
already happened to be creators. **Co-author extraction's payoff is surfacing candidates
whose LATER promotion converts to pairs** — that is precisely the mechanism that produced
+142 pairs last round from zero new scraping. Judge this mechanism on candidates surfaced,
not on same-night pairs.

## TASK 0 — category bug fixed in CODE (was data-only)

### What was actually wrong
Two writers created sheet rows without ever classifying the account:
- `collab_edges.py` — hardcoded `category: "other"` for every co-author pushed.
- `discover_candidates.py` — one `--category` hint for a WHOLE run, no per-account logic.

### ⚠️ Correction to the task framing
The instruction was to reuse "the bio-reading classification logic from
`sheets_sync.update_category()`". **That function contains no classification logic** — it
is a *writer* that takes a `{handle: category}` dict and writes cells. Last round's
categories came from a human reading each bio. There was nothing to reuse, so the missing
piece was built once, in `account_classify.py`, and imported by both call sites. That
serves the intent (one approach, not two) rather than the literal wording.

### Honest accuracy measurement — this is the important part
`account_classify.classify_from_profile()` is a rule-based classifier over name + bio +
handle, word-boundary matched throughout (bare substring matching is this project's
documented P1.3 bug class).

| Measurement | Result |
|---|---|
| 37-case unit suite (`test_account_classify.py`) | **37/37 (100%)** |
| Held-out, 30 accounts never tuned on — bio only | **9/30 (30%)** |
| + affiliation signal (@-mentions of known teams) | **14/30 (47%)** |
| **+ grid enrichment — FINAL** | **17/30 (57%)** |
| Rows landing in `other` | **60% → 20%** |

**The 100% is overfitting and must not be quoted as the classifier's accuracy.** The
held-out number is the real one. Dominant failure: **18 of 21 errors were `-> other`** —
exactly the pileup this task exists to prevent. Cause: real Instagram bios are sparse.
Ishan Kishan's entire bio is "For business enquiries"; Chris Gayle's is a nickname.

Two evidence-driven improvements followed, each measured rather than assumed:

1. **Affiliation signal** — players @-mention their club, and we already know which
   handles are teams/leagues because they are creators in our own DB. Resolving those
   mentions needs no extra fetch. → **14/30 (47%)**.
2. **Grid enrichment** — the routing rules already require opening the grid for the
   relevance check, and post captions carry far more signal than a bio. When the bio is
   inconclusive, the classifier re-runs over bio + grid text.

**Design consequence, stated plainly:** a keyword classifier cannot reliably categorise
sparse Instagram bios, and no amount of further tuning will make it authoritative. The
sheet is a **review queue**, not a source of truth — `approval_status` is the user's
column and every row is human-reviewed before promotion. So the classifier's job is to
give the reviewer a sensible starting point **plus its evidence string**, which is written
into `notes` for every row. Low-confidence guesses are labelled `LOW CONFIDENCE` in that
evidence so a review pass can find them quickly.

**Final honest read: 57%, with 20% landing in `other`.** Good enough to give a reviewer a
useful starting point; **not** good enough to be trusted unreviewed. Remaining errors are
mostly `lifestyle ↔ athlete/fitness` confusions, several genuinely ambiguous (a retired
player who now coaches is defensibly either).

### ⚠️ DEVIATION, deliberate — the grid-relevance gate is RECORDED, not ENFORCED

The routing rules say a candidate needs "a clear majority of recent posts domain-relevant"
before being added. Measured across the 30 held-out accounts, **mean grid relevance is
0.30, and 7 of 30 returned no usable grid text at all.** A hard majority gate on that
metric would reject roughly 80% of co-author candidates — including verified real
collaborators of our own creators.

The metric is not trustworthy enough to auto-reject on: Instagram grid alt-text is often
boilerplate ("Photo by X on <date>"), so a low ratio frequently means *no caption text*,
not *off-domain*. Enforcing it would silently discard real edges, which is the expensive,
hard-to-notice failure. So the ratio **is computed and written into `notes` for every
row**, and the human review pass — the actual gate — can act on it.

**This needs a user decision:** either accept recording-not-enforcing, or have the domain
vocabulary validated properly before it gates anything. Flagged rather than decided
unilaterally, per the round's "conservative, reversible" instruction.

### 🚨 SILENT FAILURE FOUND: the sheet had run out of rows

The first smoke test of the new push path failed with:
`APIError [400]: Range (...!A996:J997) exceeds grid limits. Max rows: 995`

**The sheet had filled its allocated grid exactly — 995 of 995 rows.** An explicit-range
write does not auto-extend a worksheet, so **every candidate push was failing**, and
`push_candidates` catches the exception and logs a warning — so it looked like a transient
network error, not a hard ceiling. Discovery had silently lost the ability to add
candidates at all. Fixed: `push_candidates` now calls `add_rows()` with 500 rows of
headroom.

Worth remembering as a class: the last round's "sheet push failed:
`ConnectionResetError`" warning was read as a network blip. **A warning-and-continue on a
write path hides a permanent failure just as well as a transient one.**

### Verified evidence that Task 0 works end to end

Two co-author rows pushed after the fix (`approval_status` blank, as required):

```
gmogtalk                 category: fitness_influencer   (NOT "other")
  notes: co-author of @gurumann on post DHFdFC4xvJR; grid relevance 4/12 (33%);
         category: fitness/coaching marker 'Fitness'
tserieshealthandfitness  category: fitness_influencer
  notes: co-author of @gurumann on post DK_YDLLSrok; grid relevance 2/8 (25%);
         category: fitness/coaching marker 'Fitness'
```

⚠️ **Known limitation visible in that very sample:** `tserieshealthandfitness` is a
corporate content channel (T-Series), which the brand rules do NOT catch — they key on
legal-entity suffixes and commerce language, and a company's *content* channel has
neither. Corporate channels still depend on the human review pass.

### FINAL candidate output — 231 new rows, real category spread

| category | count | share |
|---|---|---|
| `other` | 76 | **33%** |
| `athlete` | 48 | 21% |
| `lifestyle_influencer` | 41 | 18% |
| `fitness_influencer` | 36 | 16% |
| `team` | 20 | 9% |
| `league` | 10 | 4% |

**`other` for co-author rows went 100% → 33%**, i.e. two thirds of new candidates now carry
a real category with its evidence recorded in `notes`. `approval_status` blank on all 231 —
verified, never written by an agent. Grid relevance recorded on 214 rows, **mean 0.24**.

**Brand routing: 10 creators now carry `brand_signals`, 128 signals total** — e.g.
`ballerathletik` 24, `100.rep` 18. Those are 128 brand accounts that did NOT become
candidate rows, which is exactly the standing rule working at scale rather than by hand.

⚠️ Honest note on the residual 33%: all of those were **reachable** — it is a vocabulary
limit, not a fetch failure. Bios like "Param Daswani" or "Engine Garam, Dil Naram" carry no
usable signal, and no keyword set will extract one. The review pass remains the real gate.

### Brand routing now happens at write time
Both writers now divert brand accounts to `sheets_sync.append_brand_signal()` on the
associated creator instead of creating a candidate row. `collab_edges.py` attributes the
signal to the creator whose post the brand co-authored. On the hashtag path there is no
owning creator, so the brand is skipped and logged (the standing rule's "hold the signal"
case).

---

# PHASE 1G — (2026-08-16)

Scope was category-fix + promotion only; no deepening. **The Phase 1F prediction was tested
and it held decisively.**

## 0. Verified totals at close of round (live DB)

| Thing | Before | After |
|---|---|---|
| `creators` | 63 | **259** (+196 new, 60 enriched, 0 skipped) |
| `creator_related_accounts` | 505 rows | 505 rows (unchanged — no scraping) |
| RESOLVED rows | 15 | **157** |
| **DISTINCT PAIRS** (report this) | 10 | **152** (+142) |
| Resolve rate | 2.4% | **31%** |
| Duplicate handles / names / collisions | — | **0 / 0 / 0** |

## 1. PROMOTION IS THE LEVER — Phase 1F's prediction, now confirmed at scale

Phase 1F found coverage adds no graph structure (7 newly covered creators → **0** new pairs)
and argued the real lever was **creator-set membership of co-authors**, with 385 dangling
handles waiting on promotion. This round promoted 196 of them and **142 dangling rows became
real pairs — with zero new scraping.**

| Action | Distinct pairs added |
|---|---|
| Covering 7 new creators (Phase 1F, 275 posts scraped) | **0** |
| Promoting 196 already-observed co-authors (this round, no scraping) | **+142** |

The pairs are structurally sensible, not artifacts: cricketers ↔ their IPL teams, footballers
↔ `bengalurufc`, `anushkasharma` ↔ Virat Kohli, `balogun` ↔ LeBron James.

**Consequence for planning: the collaboration graph was never sparse for structural reasons —
it was sparse because the endpoints weren't creators yet.** Phase 1F's "2.4% resolve rate is
structural" claim was true *of that creator set* and is now obsolete; do not quote it. Track B
and Track C both recorded the 10-pair figure — **both need telling it is now 152.**

## 2. Category fix — 132 of 146 were misclassified

| accepted by category | before | after |
|---|---|---|
| `athlete` | 17 | **96** |
| `fitness_influencer` | 73 | **81** |
| `lifestyle_influencer` | 4 | **38** |
| `team` | 18 | **21** |
| `league` | 0 | **8** |
| `other` | **146** | **14** |

**132 misclassified, 13 genuinely `other`, 1 excluded as a brand.** `approval_status`
untouched throughout (258/230/506 before and after).

**Root cause, proven not guessed — and it is NOT positional.** `collab_edges.py:320`
hardcodes `"category": "other"` for every co-author it pushes; at push time it has only a
handle scraped from a post header and no bio to classify on.

- **144 of 146** `other` rows carry co-author provenance in `notes` (99%)
- **all 144** accepted co-author-sourced rows are `other` (100%, no exceptions)
- the only 2 exceptions are `athleanx` / `technicalguruji`, original-seed dead handles

So the "~row 140" boundary is a **provenance boundary**, not a row-index one: rows to ~139
came from `discover_candidates.py`, everything after from co-author pushes. Second mechanism
worth fixing: `discover_candidates.py` applies one `--category` hint per **run** (default
`fitness_influencer`) with no per-account classification at all.

Category propagation to the DB is automatic: `get_or_create_creator` refreshes name/category
**only when the existing row is `other`**, so promotion repaired the 10 stale DB rows too.

## 3. Profile fetching needs BOTH paths — they fail independently

`opencli instagram profile` served **111 of 146**; the other **35 fail it persistently**
(`instagram user` fails on them too) yet **load fine via the browser**. That is the exact
inverse of the documented grid stall, which had the browser failing while the adapter worked.
⇒ **Treat adapter and browser as independent fallbacks for each other in both directions.**
Cheap browser probe that avoids a ~10KB page extract:

```
opencli browser <s> eval "JSON.stringify({d:document.querySelector('meta[name=description]')?.content,t:document.title})"
```
returns `"7M Followers, 1,132 Following, 35 Posts - @bronny on Instagram: \"999 LLJW\""`.

⚠️ **Never put `||` in an `eval` argument.** opencli resolves through an npm `.cmd` shim, so
cmd.exe re-parses the argument and treats `||` as its OR operator — it truncated the JS into
`SyntaxError: Unexpected end of input` plus a bogus
`'''' is not recognized as an internal or external command`. Add this to the Windows gotchas
in lesson 7.

⚠️ **Do not unescape `\"` before `json.loads`** on eval output — it is already valid JSON, and
bios legitimately contain quotes. That bug failed 5 handles before the consecutive-failure
abort stopped it, which is the mechanism working.

## 4. Brand accounts caught — 2, excluded and flagged

**`approval_status` is the user's column and agents must never write it**, so a brand found at
promotion time is **excluded and flagged, never auto-rejected.** Both need a user decision:

| Handle | What it is | Status |
|---|---|---|
| `sporting.beyond` | **"Sporting Beyond Pvt Ltd"** — a company | ⚠️ **already a creator** from a Phase 1E targeted promotion, so it predates this rule. Left in place rather than deleted: it carries a resolved edge (`Virat Kohli -> @sporting.beyond`). **User call.** |
| `sportsclaus` | sports content/media company ("we design the fandom") | accepted and miscategorized `athlete`; excluded from promotion |

Recorded against the creator it was observed on, per the standing rule:
`virat.kohli.brand_signals = "sporting.beyond (Sporting Beyond Pvt Ltd) - co-author on Virat
Kohli post; company, not a creator"`.

**Also flagged, outside the fixed scope (rows already had non-`other` categories, so the
user's review had passed them):**
- `mfn_mma` — Matrix Fight Night, an **MMA promotion/league**, categorized `fitness_influencer`. Promoted; category is wrong.
- `sharikfilms` — "Cinematic Storyteller", a filmmaker, categorized `fitness_influencer`.
- `totalcombatfitness` — a gym (institutional), categorized `fitness_influencer`.

## 5. Next steps

1. **Tell Tracks B and C the graph changed**: 10 pairs → **152**, resolve rate 2.4% → 31%.
   Both have the old figure written into their notes as a structural fact.
2. **Deepening loop** (separate prompt) — 228 of 259 creators now have no Instagram content.
3. **Wire the brand rule into code** — `collab_edges.py` still pushes every co-author,
   business or not; `discover_candidates.py` still has no account-type classifier (P1.4).
4. **Fix `collab_edges.py:320`** so co-author pushes stop minting `other` rows; the cheap fix
   is to classify from the bio at push time, since the co-author's profile is one call away.
5. **User decisions:** `sporting.beyond` (a company sitting in `creators` with a live edge),
   and the three miscategorized rows in §4.

---

# STANDING RULE (2026-08-16) — BRANDS NEVER GET A SHEET ROW

Set by the user. Structural, permanent, **not** a one-time cleanup, and it applies at
DISCOVERY time rather than at user-review time.

When discovery meets a brand / business / company account — brand-anchored discovery, a
tagged collaborator that turns out to be a business, an athlete-owned product line:

- **Do NOT create a sheet row / candidate for it.**
- **DO append it to the `brand_signals` column of whichever creator's row it is associated
  with** (e.g. the creator whose post tagged it). That column exists for exactly this and is
  **live on the sheet now** — the plan file still calls it "TO ADD", which is stale.
- If no associated creator row exists yet, **hold the signal** and attach it once one does.

**Athlete-owned businesses are brands, not creators** (a sneaker line, a nutrition brand).
They get no creator category at all — reject the row and record the brand signal instead.

**Category guidance that goes with it** (user, 2026-08-16), against the live CHECK values
`athlete · team · league · fitness_influencer · lifestyle_influencer · other`:

| Real-world thing | Category |
|---|---|
| League | `league` |
| Team / club | `team` |
| **Sports federation** | `league` — closest fit; no dedicated value exists |
| Individual coach/trainer posting own content | `fitness_influencer` / `lifestyle_influencer` |
| **Coaching institution / academy** (organisational, not a person) | `other` — kept for breadth/discovery value (roster-like athlete affiliations), **not** as a standalone recommendation candidate |
| Athlete-owned business / product line | **none — it is a brand.** Reject + `brand_signals` |

⚠️ **Not yet enforced in code.** `collab_edges.py` still pushes every co-author to the sheet
regardless of whether it is a business, and `discover_candidates.py` has no account-type
classifier (P1.4 is still open). Until that lands, this rule is applied by hand each round.
Wiring it in is the natural next step and was deliberately left out of the 2026-08-16 round,
which the user scoped to category-fix + promotion only.

---

# PHASE 1F — READ THIS FIRST (2026-08-15, most recent round)

Supersedes Phase 1E where they disagree. **The square-growth hypothesis is no longer open —
it was tested properly and it FAILED.** Do not re-open it as "untested".

## 0. Verified totals at close of round (live DB, 2026-08-15)

| Thing | Value | Change |
|---|---|---|
| `creators` | **63** | +3 (all targeted promotions) |
| `creator_related_accounts` | **505 rows** | +189 |
| **RESOLVED rows** | **15** | +5 |
| **DISTINCT PAIRS** (report this) | **10** | +3, *all from promotion* |
| `instagram_posts` | **1,092** | +267 |
| Creators with IG content | **31 of 63** | +7 |
| `instagram_comments` | **13,097** | +1,546 |
| Posts unscanned for co-authors | **120** | throttle stopped the scan |
| `has_paid_partnership_label` true | **12** | +1 |

## 1. The throttle test — the correct method, and it passed

Phase 1E's lesson was applied literally: a **sustained 12-request scan**, not a probe.
Result **12/12, `failed=0`, 168s continuous** — past the ~4-request point where sustained
scanning re-tripped the throttle last round. It then held clean across the **full 347-post
run: 0 failures in 70 minutes**. The throttle was genuinely gone, and the sustained test
said so correctly where a probe would have been unfalsifiable.

Worth keeping: the 12 test requests were **real work from the backlog**, not a throw-away
probe. A clearance test costs nothing extra if it is the first slice of the job itself.

## 2. THE HYPOTHESIS TEST — negative, and the mechanism is now understood

| | Before | After |
|---|---|---|
| Posts unscanned | 359 | **0** |
| `creator_related_accounts` rows | 316 | **423** (+107) |
| **RESOLVED** | **10** | **10 (+0)** |

Phase 1E predicted resolved edges grow ~quadratically with coverage, "since each newly
covered creator can pair with every existing one." **That mechanism is empirically false
for this creator set**, and the excuse used last round (unscanned posts) is now gone — every
post is scanned.

The measurements that kill it:

- **407 distinct co-author handles observed; only 9 (2.2%) are creators of ours.**
- 423 edge rows, **10 resolve (2.4%)**. 385 dangling handles are referenced by exactly one
  creator — isolated leaves that add no pair.
- **14 of 24 covered creators have ZERO co-authors inside the creator set.**
- The 11 creators newly covered last round produced **~250 edge rows and 0 resolved edges**.
- 24 covered creators offer 552 possible ordered pairs; **8 are realised** (~1.4%).

**Why:** real Instagram collaborators are overwhelmingly **brands, media orgs, and adjacent
individuals outside the curated set** (`netflix_in`, `starsportsindia`, `primevideoin`,
`battlegroundsmobilein_official`...). Our 60 creators are curated as *people worth
recommending*, not as *a group that collaborates with each other*. Famous creators rarely
co-post with other famous creators; Ronaldo↔LeBron is the exception that made the mechanism
look general.

**⇒ The lever is creator-set MEMBERSHIP of co-authors, not Instagram coverage.** Of the 10
resolved edges before this round, **4 came from targeted promotion**; coverage's contribution
saturated once the mutually-collaborative pairs were found. Scanning more posts from
already-covered creators has a marginal return of ~0 resolved edges.

**Do not spend another round on Instagram coverage expecting resolved edges to move.**
Coverage still has independent value (datapoints, captions, sponsorship events for Track C) —
just not this one.

## 3. Bridge candidates — the ranked, evidence-based promotion queue

Only **13 of 398** dangling handles are referenced by **2+ distinct creators**. These are the
only promotions that create a *bridge* (linking two already-covered creators) rather than a
leaf. Ranked, with the brand exclusions already applied:

| Handle | Referenced by | Promote? |
|---|---|---|
| `@netflix_in` | Bhuvan Bam + Prajakta Koli + worldofsiddharth | ❌ **BRAND** |
| `@starsportsindia` | delhi_cricket + kkriders + Sania Mirza | ❌ **BRAND/media** |
| `@ajinkyarahane` | kkriders + sunrisershyd | ✅ cricketer (`athlete`) |
| `@rohitsaraf` | Bhuvan Bam + Prajakta Koli | ✅ actor |
| `@jimmysheirgill` | Prajakta Koli + worldofsiddharth | ✅ actor |
| `@taarukraina` | Prajakta Koli + worldofsiddharth | ✅ actor |
| `@mansukhmandviya` | MC Mary Kom + Neeraj Chopra | ⚠️ politician — user call |
| `@ptushaofficial` | Neeraj Chopra + Saina Nehwal | ⚠️ unverified |
| `@districtupdates` | Sania Mirza + Virat Kohli | ❌ brand (ticketing) |
| `@jayantireddylabel` | Sania Mirza + worldofsiddharth | ❌ brand (fashion label) |
| `@primevideoin` | Bhuvan Bam + worldofsiddharth | ❌ **BRAND** |
| `@battlegroundsmobilein_official` | Bhuvan Bam + CarryMinati | ❌ **BRAND** (game) |
| `@delhipremierleaguet20` | delhi_cricket + kkriders | ⚠️ a league — `league` IS a valid category and teams are already creators, so defensible; user call |

**These are NOT yet approved on the sheet.** They need user review first — the targeted-
promotion rule draws its candidates from `accepted` rows.

## 4. Promoted this round — 3, each naming the row it resolved (RESOLVED 10 → 13)

| Promoted | Edge it resolved | Verified as |
|---|---|---|
| `@anushkasharma` | Virat Kohli -> @anushkasharma | real person, 67.5M, verified |
| `@choudharyhitesh005` | MC Mary Kom -> @choudharyhitesh005 | "Cricketer/Businessman", 1.9M, verified |
| `@piyush.meghwanshi` | Saina Nehwal -> @piyush.meghwanshi | "Podcaster", real individual (only 1.8k followers) |

Every one checked against its **live bio**, not inferred from the handle.

`promote_candidates.py` now takes `--handles`. It previously had **no way to promote a
subset** — the only mode was "promote every accepted row", exactly what the standing rule
forbids. The rule existed with no tooling to obey it.

## 5. ⚠️ BRAND ACCOUNTS ARE MARKED `accepted` ON THE SHEET — flagged, not promoted

12 accepted candidates met the resolution condition. **At least 7 are brand/product
accounts** and were deliberately left alone:

`@nike` · `@nikebasketball` · `@nikefootball` · `@pumatraining` · `@yonex_sunrise_india` ·
`@duroflexworld` · `@one8world`

`@one8world` is **named as a brand example in CAPSTONE_NEXT_STEPS.md itself.** Two more were
excluded on evidence rather than by name: `@saniamirzatennisacademy` is a **business** (live
bio advertises coaching camps and registrations) and `@neerajchoprafoundation` is an org
(also a new dead handle — HTTP 400).

**This is a live hazard, not a hypothetical.** Under a bulk promotion these seven would have
entered `creators` and resolved into `creator_related_accounts` as fake "collaboration"
edges, corrupting the collaboration-vs-sponsorship distinction GAIL depends on. **User review
is the only safeguard and it did not catch these** — the targeted-promotion rule caught them
only because a human-in-the-loop check was applied per candidate.

## 5b. ⚠️ REPORT DISTINCT PAIRS, NOT RESOLVED ROWS — a new counting trap

Standing rule 8 says "row counts ≠ resolved counts". **There is one more level below that,
and it bit this round:** *resolved rows ≠ distinct pairs.*

After batch 1's scan, RESOLVED rows went **13 → 15** — which reads like coverage finally
producing edges. It did not. Both new rows are the **reciprocal direction** of pairs that
already existed:

- `choudharyhitesh005 -> @mcmary.kom` (reverse of `MC Mary Kom -> @choudharyhitesh005`)
- `piyush.meghwanshi -> @nehwalsaina` (reverse of `Saina Nehwal -> @piyush.meghwanshi`)

Scraping a newly-promoted creator's own grid finds the collaboration from *their* side too.
**Distinct unordered pairs: 10 before, 10 after. Zero new graph structure.**

This round, cleanly attributed:

| Source | Distinct pairs added |
|---|---|
| 3 targeted promotions | **+3** (7 → 10) |
| Covering 7 new creators (275 posts, 147 scanned, 82 new edge rows) | **0** |

That is a second independent confirmation of §2, on a different creator sample — and it was
a **pre-registered prediction**: §2's mechanism analysis predicted ~0 before the batch ran.

**Always compute pairs with `least(name)/greatest(name)` de-duplication before reporting
edge growth.** A bidirectional collaboration is ONE edge to the graph, not two.

## 5c. Batch 1 coverage + the throttle re-trip (2026-08-15)

**Batch 1: 7 of 8 creators, +267 posts.** Coverage **24 → 31 creators**, `instagram_posts`
825 → 1092, `instagram_comments` 11,551 → 13,097. `@anushkasharma` alone failed — grid stall
at **0 links**, per-account not systemic (`choudharyhitesh005` scraped normally seconds
later). The 0-links-at-19s shape suggests the page never finished loading before the scroll
loop gave up; **the isolated-retry test on her is still pending** and was NOT run because the
throttle tripped first.

**The throttle re-tripped at post 148 of 267** (`chrome-error://chromewebdata/`). The
consecutive-failure abort caught it in ~50 seconds. Cumulative Instagram volume for the day
was the cause, and the arithmetic is again clear: **12 + 347 + 147 ≈ 506 post-page fetches
(3 opencli calls each), plus 275 posts scraped with comments in batch 1.**

⇒ **Coverage stopped here deliberately** — the instruction was to continue only *if the
throttle stays clear*, and it did not. **120 posts remain unscanned.** Re-run
`collab_edges.py --only-new` after a real cooldown (hours). Everything is flushed
incrementally and safe.

**Also gained:** +1 native paid-partnership post (**12 total**) and 26 caption fixes — real
new signal for Track C independent of the edge question.

⚠️ The end-of-run **sheet push failed** with `ConnectionResetError 10054`, so batch 1's
co-author candidates are **on disk in `coauthor_checkpoint.json` but not yet on the sheet**.
This is the end-of-run-write fragility this file has flagged twice before; the edges
themselves were flushed incrementally and are safe in the DB.

## 6. New dead handle

`@neerajchoprafoundation` — `HTTP 400 - make sure you are logged in`, while other handles
succeeded in the same session. Add it to the dead list in §6 of Phase 1E.

## 7. NEXT STEPS (supersedes the older "Exact next steps" section further down)

1. **Wait out the throttle — hours, not minutes.** ~506 post fetches went out on 2026-08-15.
   Test clearance with a **sustained 10-15 request scan** (`--only-new --limit 12`), never a
   single probe. The test slice is real backlog work, so it is free.
2. **Finish the 120 unscanned posts** — `python collab_edges.py --only-new`. Resumes safely.
3. **Re-push batch 1's co-author candidates to the sheet** — the end-of-run push died with
   `ConnectionResetError`; the data is in `coauthor_checkpoint.json`, not on the sheet.
4. **Get a user decision on the bridge queue (§3)** — this is now the ONLY lever known to add
   graph structure. Nothing there is `accepted` on the sheet yet, so the targeted-promotion
   rule cannot draw from it. Highest value: `@ajinkyarahane`, `@rohitsaraf`, `@jimmysheirgill`,
   `@taarukraina`.
5. **Get a user decision on the brand accounts marked `accepted` (§5)** — seven of them, and
   a bulk promotion would silently corrupt the collaboration/sponsorship distinction.
6. **Isolated-retry test on `@anushkasharma`** — first call of a fresh session, grid path only,
   per the discriminating test that resolved the last grid stall. 67.5M followers and a
   confirmed real Kohli collaborator, so she is worth the retry.
7. **Do NOT run more Instagram coverage expecting resolved edges.** Tested twice, both
   negative. Coverage is still worth running for datapoints/captions/sponsorship events —
   just do not book it as edge work.

⚠️ **CAPSTONE_NEXT_STEPS.md edits from this round are on `track-a-data-infra`, NOT on `main`.**
Tracks B/C/D pull `origin/main` and will not see the P0.2 correction or the `DATABASE_URL`
fix until someone merges. Given the documented incident about exactly this, flag it rather
than assuming it propagated.

---

# ⚠️ DB CONNECTIVITY — `DATABASE_URL` changed 2026-08-14 (affects ALL FOUR TRACKS)

**Symptom:** every `psycopg2.connect()` fails instantly with
`could not translate host name "db.fhbgbtxdtfluzohxyivg.supabase.co" to address:
Name or service not known`. It looks like a dead project or bad credentials. It is neither.

**Root cause, diagnosed not guessed:**

| Check | Result |
|---|---|
| `getaddrinfo` on other hosts (google.com, `fhbgbtxdtfluzohxyivg.supabase.co`) | ✅ resolves — so DNS/network is fine generally |
| `Resolve-DnsName db.<ref>.supabase.co -Type A` | **no A record** (SOA only) |
| `Resolve-DnsName db.<ref>.supabase.co -Type AAAA` | ✅ `2406:da1a:82a:9d01:...` |
| Direct IPv6 TCP connect to :5432 | ❌ `WinError 10051 — network unreachable` |

⇒ Supabase's **direct** connection host is **IPv6-only**, and this machine lost its IPv6
route. Nothing about the project, password, or Supabase status changed.

**Fix (applied to Track A's `.env`, one-line DSN swap):** use Supabase's **IPv4 session-mode
pooler**. Note the username changes to `postgres.<project-ref>`:

```
DATABASE_URL=postgresql://postgres.fhbgbtxdtfluzohxyivg:<pwd>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

Verified working immediately (`select count(*) from creators` → 60, matching the last
known-good figure). Region `ap-south-1`, port 5432 (session mode; 6543 is transaction mode
and does not support prepared statements the same way). The old direct line is kept
commented in `.env` for when IPv6 returns.

**Why this matters beyond Track A:** B/C/D all connect to the same DB with the same style of
DSN. If any of them reports "database is down" or "host not found", it is almost certainly
this, not an outage — send them here rather than letting them re-diagnose it.

**Generalisable lesson:** "host not found" was NOT a DNS outage and NOT a credentials
problem — the name resolved fine, just to an address family with no route. When a hostname
fails to resolve while everything else resolves, check the *record type* before assuming the
service is gone.

---

# PHASE 1E — READ THIS FIRST (2026-08-14, most recent round)

Supersedes older sections of this file where they disagree. Every figure below was
verified directly against the live DB at the close of the round.

## Verified totals (so the next session doesn't rediscover them)

| Thing | Value |
|---|---|
| `creators` | **60** |
| `creator_related_accounts` | **316 rows / 10 RESOLVED** |
| `instagram_posts` | **825** (24 of 60 creators covered) |
| `instagram_comments` | 11,551 |
| `brands` | **10** |
| `is_sponsored` events | **11** (9 carry `brand_id`) |
| `reddit_post_creators` | 435 |
| Captions | 758 non-null / 754 distinct |

WARNING: "RESOLVED" = rows whose `handle` matches ANOTHER creator's own handle, i.e. what
Track C's resolver can actually turn into an edge. **Always report resolved, not rows.**

WARNING: the 4 duplicate captions are 1-2 char emoji-only (plus one empty). Benign,
re-verified each round. **Interpret the distinctness check with caption LENGTH in mind** —
the real corruption signature was *long* captions repeated across unrelated posts.

## 1. brand_id gap — 1/11 to 9/11 (root cause fixed; 2 deliberately left alone)

`brand_extraction.py` only matched explicit disclosure PHRASES ("in partnership with",
"sponsored by", "joined hands with"). **The dominant disclosure pattern in this dataset is
a BRANDED HASHTAG** (`#Airtel`, `#Milton`, `#CadburyCelebrations`, `#AmazonPrime`,
`#VisitDubai`, `#BGMI`) or an `@mention` (`@ewc_en`) — for which there was no rule at all.
`backfill_brand_ids.py` adds a hashtag/mention proposer ranking candidates by whether the
token is corroborated in the caption BODY, with an auditable stoplist for generic and
campaign tags.

Because `is_sponsored` + `brand_id` is the sole treatment-label source (PROJECT_PLAN calls
it precision-critical), the script PROPOSES but never auto-writes: a reviewed decision
table records what was checked against each full caption. New unreviewed events are logged
for review, never linked silently.

**DO NOT "fix" these two by guessing — they are deliberate, not oversights:**

- **`DWTx3_MERRb`** — full caption is 56 chars: "Take it slow. Go with the Flo #ad". The
  only hashtag is `#ad`; "Flo" may be a brand or wordplay on "flow". The proposer returned
  NOTHING for it, independently confirming it is unextractable from the text.
- **`DUkDWOYiL8x`** — caption is **EMPTY (0 chars)**. Labelled purely from Instagram's
  native paid-partnership label, so there is no disclosure text to extract from at all.

## 2. TARGETED PROMOTION IS A STANDING RULE, NOT A ONE-OFF

**Promote a sheet candidate ONLY if its handle already appears in an unresolved
`creator_related_accounts` row.** Each such promotion immediately converts a dangling row
into a real edge, and you can name exactly which one.

This round: of **116 approved** sheet rows, exactly **4** qualified. RESOLVED went 6 to 10,
precisely +4:

| Promoted | Edge it resolved |
|---|---|
| `@worldofsiddharth` | Prajakta Koli -> @worldofsiddharth |
| `@weareteamindia` | Neeraj Chopra -> @weareteamindia |
| `@sporting.beyond` | Virat Kohli -> @sporting.beyond |
| `@karanaujla` | Virat Kohli -> @karanaujla |

**The other 112 approved rows are deliberately NOT promoted. This is not a backlog and
must not be "caught up".** Bulk-promoting them adds creators without adding training
pairs — the trade the user explicitly does not want made silently.

The check to run (don't eyeball the sheet):

```sql
select lower(x.handle)
from creator_related_accounts x
where not exists (
  select 1 from creators c
  where lower(c.instagram_handle) = lower(x.handle)
    and c.creator_id <> x.creator_id
);
```
Intersect that with sheet rows whose `approval_status` is exactly `accepted`, minus
handles that are already creators.

## 3. Reddit co-occurrence — GENUINE ZERO, not fixable by more of the same

**435 rows across 435 distinct posts — a perfect 1:1 ratio.** Not one post is referenced
by two creators, so there is nothing for Track C's resolver to miss. **A real finding, not
a bug on either side.**

Structural cause: coverage is concentrated in 5 creators — Virat Kohli 150, LeBron 137,
Cristiano 59, CarryMinati 41, Athletics 40 = **427 of 435** — while **8 of 13 creators have
exactly 1 row each**. Each post is discovered via a SINGLE creator's search and attributed
to that creator alone.

**Scraping more per-creator subreddits will NOT create overlap.** Co-occurrence requires
two creators searched in the SAME subreddit both matching the SAME post. If co-occurrence
edges are ever prioritized, that needs a deliberate **shared-subreddit search strategy**,
not more volume.

## 4. THE INSTAGRAM THROTTLE — read this before touching Instagram

Two DIFFERENT failure modes. Do not conflate them:

- **HTTP 429** (2026-08-11) — the platform explicitly saying stop.
- **Network-layer throttle** (2026-08-14) — arrives as
  `page mismatch: got chrome-error://chromewebdata/`, Chrome failing to establish the
  connection. **NO 429 appears anywhere**, so any check keyed on the string "429" misses it
  completely. One run burned **106 consecutive failures** (posts 66-171) before being
  stopped by hand.

**A SINGLE-REQUEST PROBE IS NOT A VALID CLEARANCE TEST. This was proven wrong twice.**
After stopping the burning run, three probes passed — the exact failing post loaded,
`instagram profile nasa` returned real data, a non-Instagram control page loaded — and it
was reported "fully recovered". It was not: resuming sustained scanning re-tripped the
throttle within **4 posts (~45 seconds)**. Single requests are served fine while sustained
request RATE is still blocked. The same flawed method was used on the earlier 429 and
happened to work, which is exactly why it looked trustworthy.

- **Valid test:** sustained scanning surviving past ~4-5 consecutive requests.
- **Cooldown:** hours, not minutes. (The 429 cleared in ~25 min; this one had NOT cleared
  after ~20 min.)
- **Do not probe-and-resume.**

Handling now in `collab_edges.py`: abort after **5 consecutive failures regardless of
error string** (reset on any success), and **8s between posts**. On the re-trip this
aborted in 48s instead of ~54 minutes of guaranteed failures.

**Why this was diagnosable at all:** the URL assertion (`post_id` must appear in the
returned page URL). Without it the extractor would have silently parsed the chrome-error
page into garbage captions — the exact corruption class the assertion was added to
prevent. Keep that assertion anywhere a fetched page is parsed.

## 5. THE OUTSTANDING TASK — resume the co-author scan

**359 of 424 newly-covered posts were never scanned for co-authors** (the throttle blocked
it).

```bash
cd scripts/ingestion
python collab_edges.py --only-new
```

`--only-new` scans only posts with `has_paid_partnership_label IS NULL`. Rows flush
incrementally, so an interruption costs at most the single post in flight, and re-running
resumes rather than repeats.

**RESOLVED has stayed at 10 because those 359 posts are UNSCANNED — not because the
square-growth hypothesis failed.** The hypothesis (resolved edges grow roughly
quadratically with coverage, since each newly covered creator can pair with every existing
one) is **untested, not disproven**. This scan is the test. Supporting evidence so far:
Ronaldo <-> LeBron appeared as an edge the moment both creators' posts were scraped in the
same round.

**Run it only after the throttle has genuinely cleared, verified by sustained scanning.**

## 6. DEAD HANDLES — stop retrying these

Persistent `HTTP 400 - make sure you are logged in` on `instagram profile`, reproduced
live while other handles succeed in the same session:

`athleanx` · `technicalguruji` · `delhicapitals` · `punjabkingsipl` ·
**`weareteamindia`** (new this round) · **`sporting.beyond`** (new this round)

Note: `weareteamindia` and `sporting.beyond` were promoted this round and DO resolve edges
correctly — edge resolution needs only the `creators` row, not scraped content. They are
dead for *scraping*, not for *graph* purposes.

## 7. Confirmed working — don't re-litigate

- **Grid-stall fix holds** — 0 stalls across 26 creators since the tab-lease fix.
  (Causality still confounded with a Chrome restart that morning; the next unattended
  scheduled run is the real test.)
- **Incremental flush** — survived a staged kill AND two real interruptions; 120 rows
  saved in one of them.
- **Captions** — the orchestrator stores full captions automatically now; verified across
  three days of unattended scheduled runs, max 2,222 chars.
