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
