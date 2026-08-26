# HANDOFF — Track A (Data/Infra)

**Start here.** Canonical entry point for a fresh session on this track. Last updated
**2026-08-26 17:41 IST — Review 1 closing; canonical 54 pairs (was 52), 259 creators, 170-edge graph stable, 8 newly-sponsored+connected creators verified, stopping state clean CAPSTONE_NEXT_STEPS.md:690.** Branch: `track-a-data-infra`.
Worktree: `D:\Capstone-worktrees\track-a-data-infra`.

## ⏩ 30-SECOND RESUME — read this before anything else

- **Current canonical: 54 computable pairs** (was 52 `CAPSTONE_NEXT_STEPS.md:641`). Verified 2026-08-26 02:00 IST via `python scripts/ingestion/pair_count.py` (sole definition `pair_count.py:92`) and `loop_stats.py`. `259` creators, `170` undirected edge pairs, `1811/1811` Instagram dated. Report at `report.md` (this round).
- **8 newly-sponsored+connected creators flagged in `track-c:36bebd4` Phase 1I (Prajakta↔Taaruk mutual, karanjohar↔Bhuvan↔Pratibha↔Gurfateh 4-way, Sania) were NOT in the 52. Re-verified live: they now contribute 23 of 54 pairs (42%, 12 distinct directed) — real signal predating 52 — but net delta is only **+2** because 70 of their 93 checks still fail on `BEFORE=0` / silent neighbours (`nikkhiladvani`, `jimmysheirgill` etc). See `report.md` and `## 2026-08-26` below.**
- **No scraping / no schema change this round — read-only.** Instagram adapter still throttled 18h+ (`chrome-error://chromewebdata/`, Reddit via same bridge works); ownership census `690/1752 (39.4%)` remains blocked but durable.
- **Next to do: nothing blocks Track B.** Train on **54-pair** set (not pre-shortcode 10-pair). Track B backlog `CAPSTONE_NEXT_STEPS.md:834`: `co_occurs_with` ~1400 edges not counted by `pair_count.py:65`, per-node `54→10`, propensity saturates.
- **Re-verify before acting on any number:** `python scripts/ingestion/pair_count.py` + `loop_stats.py` reprint the entire state in ~10s against live DB via pooler `CAPSTONE_NEXT_STEPS.md:486`. Instagram+Reddit must run **SEQUENTIALLY** (resource-separation failed — `HANDOFF.md` Phase 1).

Then read `DATA_COLLECTION_STATUS.md`, `ORCHESTRATION.md`, `SCHEMA.md`, and this round's `report.md`.

## 2026-08-26 — Review 1 closing (54 pairs, re-verified 17:41 IST) — Track A — stopping state clean

**Review 1 closing — stopping state clean `CAPSTONE_NEXT_STEPS.md:690`, window capped `1095` `CAPSTONE_NEXT_STEPS.md:614`, census `690/1752` pending throttle — a fresh session resumes without chat by reading this section + `report.md`.**

**Task:** `python scripts/ingestion/pair_count.py:1` + `loop_stats.py:1` (canonical, no hand-roll) against live DB, 4 readings, delta vs 52 `CAPSTONE_NEXT_STEPS.md:587`, cross-check 8 newly sponsored+connected creators `HANDOFF.md:108`/`36bebd4`, re-print creators / `creator_related_accounts` directed+distinct / `instagram_posts` dated / `is_sponsored` with `brand_id` for Track B. No scraping/writes this round.

**Commands + timestamps (IST):**
- `2026-08-26 01:58` `git pull origin main` — already up-to-date
- `2026-08-26 01:59` `python scripts/ingestion/pair_count.py` — 54 pairs (see 4 readings below)
- `2026-08-26 01:59` `python scripts/ingestion/loop_stats.py` — 259 creators, 170 edges
- `2026-08-26 02:00` `psycopg2` pooler queries — live DB state re-verified (see below)
- `2026-08-26 17:41` `git pull origin main` + `pair_count.py:1`/`loop_stats.py:1`/`psycopg2` — re-verified **same 54/23/19/40**, `259`/`873/203/170`/`1811`/`58 (18 brand)`/`1607`/`2748`/`19` — report not stale, no overwrite needed

**4 readings (canonical `pair_count.py:127`):**
- event×neighbor rows (CANONICAL) **54** (was 52, **+2**)
- event×neighbour checks evaluated **138** (was 137, +1)
- dated sponsorship events **53** (was 49, +4) — `57` total dated `54 IG+3 YT` minus 4 orphan (Jeet Selal 2, RAGI, SAGAR)
- events yielding ≥1 pair **40** (was 37, +3)
- distinct directed **23** (was 23, 0)
- distinct undirected **19** (was 20, −1)
- collab edge pairs **170** (was 170, 0)
- fail: `BEFORE 37 / AFTER 9 / silent 38` (was `56/6/48` in older 27-pair era; now tighter)

**Live DB state (pooler, `orchestrator.ENV["DATABASE_URL"]`):**
`creators 259` / `creator_related_accounts 873 rows / 203 directed distinct / 170 undirected` / `instagram_posts 1811 total / 1811 dated (100%)` / `instagram is_sponsored 58 / has_paid_partnership_label 45 / (is_sponsored OR label) dated+creator_id 54 / total 58 = 18 with brand_id / 40 without` / `youtube_videos 1607 / is_sponsored 3 (0 with brand_id)` / `reddit_posts 2748 / is_sponsored 0` / `brands 19`.

**8 creators cross-check (live re-derived via `pair_count.py:86` CANDIDATES):**
All 7 handles exist: `mostlysane`, `taarukraina`, `karanjohar`, `bhuvan.bam22`, `pratibha_ranta`, `gurfatehpirzada`, `mirzasaniar`. Sponsored events among them `22` (Bhuvan 6, karanjohar 6, Prajakta 2, Taaruk 4, Pratibha 2, Gurfateh 1, Sania 1). Resolved edges among them `8` directed rows (Bhuvan→karanjohar/pratibha/gurfateh, Gurfateh→pratibha, karanjohar→pratibha, Prajakta→Taaruk, Pratibha→karanjohar/gurfateh); Sania's outgoing is to family/academy (`parikshitbalochi/nasimamirza/saniamirzatennisacademy/suhan.khnofficial`), not directly to karanjohar — incoming from `saniamirzatennisacademy/nasimamirza`. **93 checks** with an 8-member as owner produce **23 pairs** (12 distinct directed) — i.e. the 8 dominate current `54`. Net `+2` only because many early events still `BEFORE=0` and neighbours `nikkhiladvani/jimmysheirgill/mihirahuja_*` silent.

**Bugs / throttle / verification proof:**
No writes, no throttle hit (read-only). Prior Instagram 18h+ throttle still operative but not exercised. Verification proof: verbatim `pair_count.py` + `loop_stats.py` logs captured 01:59, `psycopg2` counts 02:00, per-check audit re-deriving `CANDIDATES` and mapping `creator_id→handle` captured at 02:00 — all in `report.md`.

**Resolved vs still-open:**
- ✅ This round: canonical pair count re-verified, 8-creator delta quantified, Track B N snapshot produced, durable trail `report.md` written.
- ⏳ Still open (waiting on user/not Track A): ownership census `690/1752`, 95 Instagram-unattempted handles, any window widening beyond `1095` (`CAPSTONE_NEXT_STEPS.md:661` capped), `co_occurs_with` undercount in `pair_count.py:65`.

**Next priority:** Track B trains on **54**; Track C wires `P1.6` spillover; Track A resumes census only after throttle clears (sustained scan). Do not re-run Phase 0 loops.

---

---

---

---

---

---

---

# ⏹️ BACKLOG LOOP STOPPED BY USER DECISION (2026-08-21, 50 cycles)

**This was a decision checkpoint, not a stop-condition exit.** Two of the four items were still
open when the loop was cancelled. Cron `77b2ad16` deleted; `CronList` confirms no scheduled jobs.

## Where the 4 items actually stand

| item | terminal? | state |
|---|---|---|
| 1 — window widening | **YES for Reddit/YouTube, NO for Instagram** | constant 183→1095 shipped; re-verified live; YouTube 41/41 and Reddit ~230/230 re-collected; Instagram re-collection never ran (throttle) |
| 2 — full ownership census | **NO** | 690 of 1,752 (39%). Blocked on a long-lived Instagram throttle |
| 3 — exhaustion bar | **NO** | Reddit arm effectively done (content 22→117); Instagram arm blocked |
| 4 — canonical pair script | **YES** | `pair_count.py` owns the definition, `loop_stats.py` imports it |

## ✅ RESOLVED 2026-08-22 — duplicate `Athletics` creator merged, root cause closed

Was: two `creators` rows named "Athletics" with that creator's Reddit content split across
them (40/40 links on the 2026-08-10 row, 21/40 on the 2026-08-20 row my own run created).

**Merged** with `merge_duplicate_creator.py`. 19 of the duplicate's links pointed at posts the
canonical row already claimed, so a blind re-point would have violated the PK on
`reddit_post_creators`; those were dropped as redundant and the other 21 (plus 21
`reddit_posts`) moved across. **Result 61/61 — exactly the predicted 40 + 40 − 19.** The
duplicate row was deleted only after all six `creator_id` tables were confirmed empty for it.
Independently re-checked: creators **260 → 259**, one `Athletics` row, **0** orphaned
`reddit_posts`, **0** dangling links.

**Root cause closed.** `get_or_create_creator` keyed identity on `youtube_handle` /
`instagram_handle` only, so a creator with NEITHER had no key at all and was re-created every
run. Added a last-resort name key for exactly that case, guarded on both sides: consulted only
when no handle was supplied, and matching only rows that themselves carry no handles.

**This is not the PV Sindhu / Saina Nehwal collision returning.** That came from matching on
SHARED COMMUNITY MEMBERSHIP — two different people both legitimately in r/badminton. The new
key is the creator's own NAME, and their names differ. Asserted rather than argued:
`test_get_or_create_identity.py` runs against the real DB and passes all three —
Reddit-only creator reused; shared subreddit does NOT merge differently-named creators; a
same-name Reddit-only lookup does NOT absorb a creator that has an Instagram handle. It cleans
up its own rows and verifies the cleanup landed.

## ✅ The two "worst kind" misattributions — STRICTLY RE-EXAMINED 2026-08-22, both CONFIRMED

Challenged on the grounds that LeBron's Nike posts read as genuine first-person endorsement,
and that the audit had an 18% false-positive rate. **The challenge was right about the posts
and wrong about which post was flagged** — and the 18% figure belongs to a different era.

**Provenance first.** Both readings come from `audit_cycle8.log`, the run started AFTER the
page-verification fix. The 18% false-positive rate was measured on the UNVERIFIED era, and
every reading from it was purged. Verification was demonstrably live during this very run —
it discarded 12 pages in it.

**Live strict re-read was attempted and could NOT complete**: 4 reads, all discarded as
`chrome-error://chromewebdata/`. Instagram is still throttled. So the confirmation below rests
on stored evidence, which is a different and weaker instrument than a live og:description read
— stated plainly rather than blurred.

**`DZSLvpKO7fZ` → nike: CONFIRMED misattribution.** The discriminator is voice, and the corpus
settles it. LeBron's grid holds FOUR Nike posts; the audit flagged exactly ONE:

| post | date | caption | still kingjames? |
|---|---|---|---|
| `DV_cx1aDgda` | 03-17 | "…Beats and Nike have been a part of **my** journey…" | ✅ yes |
| `DWG1NxEDoq0` | 03-20 | "Keep your head in the game." | ✅ yes |
| `DZLVfYcEvXU` | 06-04 | "Time to call **your** agent, @cristiano 🤷🏾‍♂️ Watch on @nike!!" | ✅ yes |
| `DZSLvpKO7fZ` | 06-07 | "The GOATs' Goodbye. Coming when **@cristiano and @kingjames** say so." | ❌ → nike |

The three first-person posts were **left untouched**. The one moved refers to LeBron in the
THIRD PERSON via @mention — brand campaign copy, three days after LeBron's own first-person
teaser for the same campaign. The audit discriminated correctly rather than sweeping the topic.

**`DYj0mpNAjZS` → astermedcity: CONFIRMED misattribution.** Caption: *"**Proud to be the
Official Medical Partner for** Kerala Blasters FC during the ISL 2026 season… **our team**
remained committed…"* — sponsor voice announcing its own partnership. Kerala Blasters' own 37
posts from the same week are uniformly club voice (`#KeralaBlasters`, `#YennumYellow`, match
commentary). A club does not announce that it is proud to be its own medical partner.

**Both stand as re-attributed. No further action taken.** They remain the clearest illustration
of why this bug matters for Track B: a sponsor's own post filed as the creator's, sitting
directly on the sponsorship relationship the model is meant to learn.

## Instagram throttle — the operative fact for planning

Probed with a sustained scan after ~18 hours, bridge up, no competing job: **still throttled**,
0 posts verified, 12 consecutive `chrome-error://chromewebdata/`. Ruled out by direct check:
bridge is connected, pacing is already the slow setting, no concurrent job, and Reddit through
the SAME bridge works. It is Instagram-side.

**Realistic time to finish the census: not a same-day task.** 1,062 posts remain at ~10s each =
~3 hours of clean running, but only once Instagram lets us back in, and 18 hours was not enough.

## Final numbers (canonical script + direct DB, 2026-08-21)

| metric | value |
|---|---|
| **COMPUTABLE TRAINING PAIRS** | **52** |
| events yielding ≥1 pair | 37 of 49 dated events |
| distinct directed / undirected creator pairs | 23 / 20 |
| collaboration edge pairs (graph) | 170 |
| creators | 260 (259 real + 1 duplicate, see above) |
| instagram_posts | 1,811 — **100% dated** |
| youtube_videos | 1,594 |
| reddit_posts | 2,698 |
| comments (IG / YT / Reddit) | 24,822 / 52,898 / 53,642 |

| platform | attempted | **with real content** |
|---|---|---|
| Instagram | 163/260 (62.7%) | 56 (21.5%) |
| YouTube | 259/260 (99.6%) | 40 of 41 handle-holders deepened |
| Reddit | 231/260 (88.8%) | **117 (45.0%)** |

---

# BACKLOG LOOP (2026-08-21) — cycles 2-5

## ITEM 1 — the window was widened, and it did NOT move the pair count. Here is why.

YouTube is the one platform that does not need the browser bridge (official API), so it was
re-run against all 41 handle-holders at the new 1095-day window.

| measure | before | after (23/41 creators) |
|---|---|---|
| `youtube_videos` rows | 1,238 | **1,398** |
| oldest video | 2026-02-09 | **2023-09-16** |
| orphaned rows (integrity) | 0 | **0** |
| **computable pairs** | **27** | **27 — unchanged** |
| failure breakdown (before/after/silent) | 56 / 6 / 48 | **56 / 6 / 48 — identical** |

The corpus grew by 160 videos reaching two years further back and *not one straddle check
changed*. That is not a null result to shrug at, it has a specific cause, measured:

| the neighbours that fail | distinct | on YouTube at all |
|---|---|---|
| fail on missing BEFORE (56 checks) | 13 | **2 of 13** |
| neighbour fully silent (48 checks) | 25 | **0 of 25** |

**Widening YouTube's window cannot fix these, because the blocking neighbours are not on
YouTube.** The fix has to come from Instagram and Reddit — both blocked on the bridge.

### ⚠️ The bigger lever is not the window at all: 51% of Instagram posts have no date

`instagram_posts`: **1,802 rows, 881 dated, 921 undated (51%)**. The straddle test needs
`posted_at`; an undated post is invisible to it. There is no unused date column —
`fetched_at`/`created_at` are ingestion timestamps.

| of the 104 checks failing the BEFORE clause | count |
|---|---|
| neighbour **already has undated Instagram posts** (10 distinct neighbours) | **40 (38%)** |
| remaining, genuinely needing collection | 64 |

**893 undated posts are already attached to a creator.** 38% of the pair gap is therefore
*not* a collection problem and *not* a window problem — the data is sitting in the DB
without a date. Dating it needs one `og:description` read per post, i.e. the bridge.

### The 38 creators gating 104 of 137 checks

Highly concentrated, and this is the priority list for the moment the bridge returns —
far higher leverage than working through the generic 95-unattempted list:

| checks gated | creator | ig posts | dated | note |
|---|---|---|---|---|
| **16** | Virat Kohli | 38 | 13 | 25 undated — date-gated, not collection-gated |
| 7 | karanjohar | 40 | 15 | date-gated |
| 7 | Nikkhil Advani | **0** | 0 | never fetched |
| 7 | Gurfateh Singh Pirzada | 9 | 9 | needs older history |
| 6 | Mihir Ahuja | **0** | 0 | never fetched |
| 6 | Jimmy Shergill | **0** | 0 | never fetched |
| 5 | Wamiqa Gabbi / mrbeast | 11 / 37 | 11 / 20 | mixed |

**19 of the 38 blockers have zero Instagram posts** — they are in the 95-unattempted set.

### Yield: the post cap, not the window, now binds

Across the first 14 creators re-run: **10 were cap-bound** (40 kept, 0 stale), 3 window-hit,
1 channel-exhausted. **71% never touched the window.** The historical 27% stale-discard rate
was concentrated in sparse channels, not spread evenly. `--post-cap 40` was left alone — that
is a cost decision for the user, not something to change mid-loop.

## The blocker, and two silent-failure bugs it exposed

**The OpenCLI browser bridge is down** — `opencli profile list` reports no connected profiles,
re-probed at the start of every cycle. **Both Instagram AND Reddit adapters need it** (tested:
`reddit search` fails identically after a 45s connect timeout). Only a human can fix it: open
the Chrome profile with the OpenCLI extension enabled.

It exposed two bugs of the same class — a dead channel indistinguishable from a real result:

1. **`measure_reddit_recency.oc_search` returned `[]` on any failure.** With the bridge down
   every search "succeeds" with zero results, so the script would have printed a confident
   **0%-relevance table for every age bucket** — a fabricated measurement, and I would have
   reported it as ITEM 1's re-verification. Now raises on the disconnect signature. Verified.
2. **The audit's strike budget was not a time budget** (see cycle 1 above).

A third, flagged but not yet fixed: YouTube comment fetching logs `HTTP Error 403` (comments
genuinely disabled) and `WinError 10054` / SSL timeouts (transient, data silently lost) under
one message, *"Comments disabled or unavailable"*. Roughly 5 of 8 observed failures were
retryable losses being written off as permanent states.

---

# BACKLOG LOOP (2026-08-20) — cycle 1

## 🛑 THE ONE THING BLOCKING TWO OF FOUR ITEMS

**The OpenCLI browser bridge is disconnected.** `opencli profile list` → *"No Browser Bridge
profiles connected."* Every browser call fails after a 45-second connect timeout with
`Browser profile "s8h98tr4" is not connected`.

**This is not the Instagram throttle.** The throttle from last round may well have expired —
we cannot tell, because nothing has reached Instagram to find out. Only a human can fix this:
open the Chrome profile with the OpenCLI extension enabled. ITEMs 2 and 3 resume the moment
it reconnects; the audit checkpoint (240) is intact and nothing was lost.

Two defects in the abort logic surfaced here and are fixed:
- **A strike budget is not a time budget.** The 12-strike abort was documented as catching a
  bad run "in ~2 minutes" — true only when reads fail *fast*. At 45s per failed call one post
  costs ~141s, so twelve strikes is **28 minutes**. Measured: the audit sat 8 minutes without
  recording or printing anything. `MAX_STALL_SECONDS = 180` now runs alongside the strike count.
- **A disconnect is not a throttle.** Identical from inside the loop, opposite responses
  (back off later / nothing will ever work until a human acts). The project already confused
  these once in the other direction. Now matched explicitly. Verified: aborts at 45s with the
  right diagnosis, checkpoint untouched.

## ITEM 1 — window widened, 183 → 1095 days ✅ code done, live yield pending browser

The size was **derived, not chosen**. Relevance rises with age (0-90d 22% on-topic → 2y+ 100%),
so relevance imposes *no* upper bound anywhere measured — it refuses to cap the window, it does
not pick a number. The number comes from the straddle requirement, which is measurable:

| input | value | source |
|---|---|---|
| oldest dated sponsorship event | 2024-09-18 = **701 days** old | live DB |
| events predating the old 183d cutoff | **24 of 55 (44%)** | live DB |
| before-gap of the 27 pairs that DO work | median **8d**, p90 **48d** | live DB |
| ⇒ floor today | 701 + 48 = **749 days** | |
| ⇒ adopted | **1095** (a year of headroom so it needn't be re-derived monthly) | |

**Corroboration that the window was truncating, not filtering:** `youtube_videos`' oldest row
is 2026-02-09 and `reddit_posts`' is 2026-02-22 — both sitting exactly on the 183-day cutoff
(2026-02-18). Neither corpus holds *anything* older, because the window never let any be written.

### What the old window actually discarded — counted from real run logs, not sampled

| platform | kept | discarded as stale | share discarded |
|---|---|---|---|
| **Reddit** | 468 | **976** | **68%** *(all of it had already passed the relevance gate)* |
| **YouTube** | 1,153 | **417** | **27%** |
| Instagram | 862 | 22 | **2%** |

⚠️ **Instagram's widening recovers almost nothing** — its grid is newest-first and hard-capped
at 12 posts, so what it fetches is recent by construction. The brief expected gains on Reddit
and Instagram; the real gains are **Reddit and YouTube**. YouTube was not named in the decision
but shares the constant and is the second-biggest winner.

### The "does this reopen the 88% noise purge?" check — run, and the assumption was wrong

Not assumed. **11 of 229 creators configured for Reddit topic search still query a
handle-shaped name** — the exact cause of the old purge, still present. But widening is still
safe, for a more precise reason than "that's fixed":

- **9 of the 11 have zero Reddit rows.** `mentions_creator` substring-matches the whole handle
  token (`rohitsharma45`), which never appears in prose, so the gate **fails closed**.
- **The 2 with rows are `CarryMinati` (62) and `shubmangill` (40), and every row comes from
  that creator's own dedicated subreddit** (r/CarryMinati, r/shubmangill), where relevance is
  structural and the gate correctly does not apply.

### ⚠️ The Instagram throttle is long-lived, and that is the finding (2026-08-21)

Probed with a real sustained scan (not a single request) after **~18 hours** of cooldown, with
the browser bridge confirmed up and no other job holding the tab lease. Still throttled:
12 consecutive `chrome-error://chromewebdata/` loads, 0 posts verified, aborted in ~2 minutes.

That changes the planning assumption. Earlier rounds treated this as a short cooldown; two
probes 18 hours apart say it is not. **The ownership census (690/1,752) and the Instagram arm
of the exhaustion bar cannot be finished on a same-day timescale.** Neither is at risk -- the
audit checkpoint is durable and resumes exactly where it stopped -- but they need either a
much longer wait or a different access path.

What is NOT the cause, each ruled out by direct check rather than assumption: the bridge is
connected (`opencli profile list` names the profile); the pacing was already reverted to the
slow setting; no concurrent Instagram job exists; and Reddit through the SAME bridge works
fine, so this is Instagram-side, not local.

### The Reddit run ended by aborting loudly, which is the fix working

`psycopg2.OperationalError: could not translate host name` -- the local network dropped, so the
cycle-7 reconnect could not reconnect. It logged `reconnect failed -- aborting batch with 10
creators unprocessed rather than reporting a false completion` and stopped. Before that fix the
same event would have logged "skipping, continuing batch" 10 times and reported success.

195 of 230 creators were searched; the true unsearched remainder is 36 (the 10 in the message
were only those still queued at the moment of abort). Re-running those 36 from
`reddit_finish.json`.

### Live collection results at the widened window (2026-08-21, in progress)

| platform | rows before | rows now | oldest before | oldest now | creators w/ content |
|---|---|---|---|---|---|
| YouTube | 1,238 | 1,398+ | 2026-02-09 | **2023-09-16** | 39 → 39 |
| Reddit | 822 | **1,005** | 2026-02-22 | **2023-11-29** | 22 → **35** |
| Instagram | 1,802 | — | — | 2016-08-25 (all dated) | blocked on throttle |

**Computable pairs: 27 → 46 (date backfill) → 52 (Reddit collection, 329/460 calls in).** 50 is the bottom
of the ~50-100 thesis-defensible tier the plan file names as the next milestone; the loop
started this round at 27. The Reddit arm is the
first time COLLECTION rather than re-dating moved the number.

⚠️ **The window is still binding on Reddit even at 1095 days**: 45-54% of relevance-passing
results are still discarded as stale, and the live measurement scored the excluded 3y+ band at
**100% on-topic (n=31)**. A further widening is data-supported and cheap -- Reddit search
already RETURNS those results, so the only extra cost is comment fetches on the additional kept
posts, not extra searching. Left for the user: this is a cost/scope call, same class as
`--post-cap`, and this loop has already taken the one widening it was asked to take.

Instagram is unaffected by any further widening -- only 4 of its 1,802 posts fall beyond 1095
days.

### ITEM 1 re-verification: RUN LIVE 2026-08-21, the noise problem is NOT reopened

The brief asked for one real check rather than an assumption. This is it, measured against
live Reddit search with the same word-boundary relevance test the collector applies:

| age bucket | results | on-topic | relevance |
|---|---|---|---|
| 0-90d | 8 | 1 | **12%** |
| 90-183d (just outside the old window) | 22 | 11 | 50% |
| 183-365d | 33 | 28 | 85% |
| 1-2y | 29 | 29 | **100%** |
| **2-3y — the band the widening ADMITS** | **36** | **36** | **100%** |
| 3y+ — still excluded at 1095d | 31 | 31 | **100%** |

Inside the old window: 30 results at **40%** on-topic. Outside it: 129 at **96%**.

Two conclusions, both worth stating separately:
1. **The widening admits clean data.** The 2-3y band it newly allows is 100% on-topic across
   36 results. The 88% purge is not reopened.
2. **1095 days is conservative, not aggressive.** The 3y+ band is also 100% on 31 results, so
   relevance still imposes no ceiling even beyond the new window. 1095 was derived from the
   straddle requirement (oldest event 701d + p90 before-gap 48d), not from relevance, and it
   can be raised further if the pair count ever needs it.

## ITEM 3 — the reachable set, enumerated

| platform | not attempted | structurally unreachable | **reachable, still to do** |
|---|---|---|---|
| Instagram | 97 | 2 (`Athletics`, `Mumbiker Nikhil` — no handle at all) | **95** |
| Reddit | 29 | 5 (Ohio State ×2, E1 Series, ATHLEAN-X, Etaki) | 24 name-gated |

**A lever inside the name-gate, found this cycle:** of the 24 name-gated creators, **20 already
had an Instagram profile fetched and it returned no `full_name`** — genuinely exhausted for that
source. The other **4 have never had one fetched at all**: `ashwani__42`, `gkgurpreet`,
`rinkukumar12`, `sivasakthi_ss11`. They also sit inside the 95 Instagram-unattempted, so one
profile fetch each serves both items. Not a retry of anything confirmed unreachable.

## ITEM 4 — canonical pair count ✅ TERMINAL

`scripts/ingestion/pair_count.py` now owns the single definition; `loop_stats.py` imports it
instead of keeping a second copy. Both print **27**.

It also prints the four other plausible readings, which is where the 38-vs-37 and 30-vs-27
disagreements came from — none of them was an error, they were different questions:

| reading | value |
|---|---|
| **(event × neighbour) rows — CANONICAL** | **27** |
| distinct directed creator pairs | 17 |
| distinct undirected creator pairs | 16 |
| events yielding ≥1 pair | 17 |
| collaboration edge pairs (graph only) | 170 |
| event × neighbour checks evaluated | 137 |

# ATTRIBUTION / COVERAGE LOOP (2026-08-19, in progress)

## 🚨 READ THIS BEFORE TRUSTING ANY OWNERSHIP-AUDIT NUMBER

`audit_post_ownership.py` produced **provably wrong readings** for its first ~310 posts, and I
re-attributed 54 real posts on them before catching it. What the numbers actually are:

| measure | value |
|---|---|
| audit false-positive rate (flagged misattributions that were fine) | **~18%** (10 of 57) |
| verified contamination rate | **~15%** (44 confirmed of ~294 resolvable) |
| rate as first reported | 19-25% — **inflated, do not quote** |

**Root cause.** `real_owner()` called `open` then `eval` and trusted whatever page was loaded.
`open` is not guaranteed to have completed, or to have landed anywhere in particular, by the
time `eval` runs, so a read can describe a **different page entirely**. Fixed: og:url and
og:description are now read in ONE eval, and the read is DISCARDED unless the url contains the
requested post_id. A discarded read is simply re-checked later, which always beats recording a
confident wrong owner.

**How it was caught.** `DC_DLAuzLnl` had two different "real owners" across two runs — its live
og:description says `anushkasharma` on two consecutive reads while the audit had recorded
`virat.kohli`. The checkpoint also held **five consecutive misattributions, each pointing at a
different well-known creator in our set**, which is not something real collab data produces.

**A theory that was tested and DISPROVEN:** that each bad read returned the *previous* post's
page. 0% of misattributions matched the preceding audited post's owner. The exact mechanism is
still unidentified; the verification is correct regardless of which page was being described.

**Recovery performed.** All 57 flagged misattributions were re-read with verification on
(44 confirmed / 10 refuted / 3 other), all 16 affected posts were set to their VERIFIED owner,
and the checkpoint was pruned from 310 to 56 — every reading taken without verification was
dropped so it gets re-checked rather than silently trusted.

## Computable pairs — tracked, and one figure retracted

| stage | pairs |
|---|---|
| uncorrected, start of loop | 37 |
| after the 3 user-approved re-attributions | 31 |
| after bulk re-attribution | 41 — **RETRACTED, rested on bad readings** |
| **after verification and correction** | **26** |

**Two mechanisms move this number, and only the first is obvious:**
1. A misattributed post **fabricates an event** the creator never had.
2. A misattributed post **widens the wrongful owner's ACTIVITY window**, so *other* creators'
   straddle checks falsely pass against it. This is why Task 1's three posts cost 6 pairs rather
   than the 5 predicted from removing the events alone: one of them extended Kohli's window
   almost six months earlier than his real 2026-01-21 start, and he is the neighbour in 16
   event-slots.

## Task 1 — DONE (user-approved, verified)
| post | was | now |
|---|---|---|
| `DLrSRdqTcEQ` | virat.kohli | **anushkasharma** (real creator) |
| `DUkDWOYiL8x` | virat.kohli | **duroflexworld** — creator_id NULL + brands row |
| `DW3hIgJDI3P` | pratibha_ranta | **reliancejewels** — creator_id NULL + brands row |

Brand-owned posts carry **no** creator attribution, matching how the schema already represents
brand content. `reattribute_posts.py` applies the same rule to anything the audit finds, and
deliberately does **not** invent brands rows for ordinary accounts — a NULL creator_id already
says the whole truth, and guessing which owners are "brands" would fabricate a classification.

⚠️ `instagram_posts.username` has an FK to `instagram_profiles`, so an owner must be inserted
there first. That does **not** make them a creator.

## Task 4 — the exhaustion bar has a principled floor
"100% attempted on all 3 platforms" is likely **unreachable by design**. Five creators cannot be
meaningfully attempted on Reddit:
- `Ohio State Football`, `Ohio State Buckeyes`, `E1 Series` — no proven in-repo sub exists for
  US college sports or powerboat racing, and inventing one would inflate "attempted" with a
  guaranteed non-attempt.
- `ATHLEAN-X™`, `Etaki` — rejected by the no-space rule in `looks_like_real_name`. Only **3**
  creators project-wide have a single-word name differing from their handle, which is far too
  few to justify loosening a guard that exists because of the 88% noise purge.

## Task 3 — the recency window is discarding the GOOD Reddit data and keeping the noise

Measured, not assumed — this project already purged 88% of Reddit data as noise after widening
reach on an assumption. 164 results across 10 creators, relevance scored per age bucket with a
word-boundary, all-tokens-present gate (`measure_reddit_recency.py`):

| age bucket | results | on-topic | relevance |
|---|---|---|---|
| 0-90d | 9 | 2 | **22%** |
| 90-183d (just outside) | 22 | 11 | 50% |
| 183-365d | 33 | 28 | 85% |
| 1-2y | 29 | 29 | **100%** |
| 2y+ | 71 | 71 | **100%** |

**Inside the 183-day window: 13 of 31 on-topic (42%). Outside it: 128 of 133 (96%).**

Relevance RISES with age, so the window is doing the opposite of its job — excluding 133 results
that are 96% on-topic while keeping 31 that are 42% on-topic. The noise sits in the RECENT
results, consistent with Reddit search falling back to loose partial matches when exact recent
matches are scarce.

⇒ **Widening recovers real signal and does not reopen the noise problem.** The earlier purge was
caused by handle-shaped name queries matching unrelated posts — a different mechanism, already
fixed by the real-name backfill.

⚠️ **Not applied.** It is a collection-policy change that interacts with the still-open user
decision on out-of-window Instagram posts; the two should be settled together.

## Stop-condition clause: cross-platform straddle check — SATISFIED, and it explains the 27

Every connected, dated sponsorship event is checked against every graph neighbour, on all three
platforms, on both sides of the event date:

| | count |
|---|---|
| dated sponsorship events | 53 |
| graph-connected (checkable) | **49** |
| orphan, no neighbour at all | 4 |
| **event × neighbour checks performed** | **137** |

| outcome | count |
|---|---|
| **straddle satisfied = computable pair** | **27** |
| neighbour has no **BEFORE** activity | **56** |
| neighbour has no AFTER activity | 6 |
| neighbour has no dated content at all | 48 |

**The dominant failure is missing BEFORE activity — 56 of 137 checks.** That is the recency
window, not a graph problem: collection starts 2026-02-17, so for any event early in that
window a neighbour simply has no earlier content to corroborate with.

⇒ This joins Task 3 to the headline metric. Widening the window adds exactly the thing 56 checks
are missing. It is not a promise of +56 pairs — some neighbours will still be silent — but the
binding constraint on pair count is now identified and it is the same constraint Task 3 measured
independently on relevance grounds.

The other 48 (neighbour has no dated content at all) need coverage, not window.

## Task 4 — Instagram attempted 52.9% -> 62.5% with NO Instagram calls

`ig_attempted` counts creators with an `instagram_profiles` row tied to them via
`ip.creator_id`. The name backfill and the bio backfill both matched profiles by USERNAME and
never set `creator_id`, so 40 profile rows sat unlinked — creators whose profile had genuinely
been fetched (name and bio present) were reported as never attempted.

Linked them, guarded on handle uniqueness: only where exactly ONE creator owns that handle,
because the kingjames/lebron collision incident is what happens when a shared handle is linked
to the wrong creator. Zero duplicate handles exist right now, so nothing was skipped, but the
guard belongs in the query rather than in anyone's memory of the incident.

**Instagram attempted 137 -> 162 (52.9% -> 62.5%).** Not a metric game — the work had been
done and the missing FK was hiding it.

Remaining 97 unattempted split cleanly:
- **2** have no `instagram_handle` at all — cannot be attempted, another principled floor
- **95** have a handle and need one profile fetch each (blocked on the Instagram throttle)

## Found but not finished
1. **The audit needs ~1,500 more posts** — 240 verified of 1752, and Instagram is currently
   throttled, so it needs a cooldown before resuming.
2. **27 is the current honest pair count.**
3. **Instagram: 95 creators need one profile fetch each**, blocked on the throttle. 2 more have
   no handle and can never be attempted.
4. **Instagram was throttled at ~14:10** (1,496 consecutive chrome-error page loads). This
   project's history says these last hours — 3.5h was once not enough. The audit's new 12-strike
   abort makes resuming cheap once it has genuinely cooled; re-probing early just adds load.

---

# ✅ TECH-DEBT LOOP COMPLETE — CYCLES 3-5 (2026-08-19)

**All 3 items terminal. 5 cycles. Loop closed.** Cycles 1-2 are recorded below this section.

## ITEM 1 — TERMINAL: verified end-to-end on a live creator

Cycle 1 fixed the code; cycle 3 closed the "verify against a real sample, not just unit tests"
gap by running the fixed worker against @mostlysane, the creator already proven to have foreign
posts in its grid:

| check | result |
|---|---|
| owner filter | 8 links found, 6 kept — **none** of netflix_in's 3 or exhibitmagazine's 1 appear |
| dates | **6/6** (the old positional code wrote NULL past index 11) |
| comment counts | **6/6 exact** |
| like counts | only on joined posts — by design; og abbreviates large counts and `_og_exact_int` refuses to overwrite a real value with a rounded one |

**The run exposed a defect in my own matcher.** The page caption is MARKDOWN (it comes from
`browser extract`), so a mention is `[@handle](/handle/)` while the listing has plain `@handle`.
Stripping punctuation without collapsing the link first left the handle DUPLICATED, breaking the
join on exactly the posts that mention someone — the collab posts that matter most for the
graph. 1 of 6 joined; collapsing links first → 2 of 6. A failed join now only costs the exact
like_count, since date and comment count come from og regardless.

### The bug's real damage was MISSING metadata, not wrong metadata
| signature | count |
|---|---|
| posts sharing an identical (likes, comments, date) triple | **1 group** |
| posts with no likes AND no date | **1041 of 1751 (59%)** |

Past index 11 the old code wrote `{}`, so posts got NULL rather than another post's values.

**Negative result that prevents wasted work: backfilling those 1041 would add ZERO computable
pairs.** 0 creators have all-undated posts and 0 event-neighbours are dark, so every straddle
check already has the dated activity it needs. That is ~3 hours of browser time not worth
spending.

## ITEM 2 — TERMINAL: four held-out sets, and the answer is "mostly overfitting"

The bio-capture pass (see ITEM 3) lifted profiles-with-a-bio **26 → 151**, which is what made a
real held-out set possible at all — the earlier "bio-only ceiling" was measured on 17 cases
*because of our own discard bug*, not because bios are scarce.

**First-exposure scores, taken BEFORE any tuning against that set:**

| set | n | first exposure | after being tuned against |
|---|---|---|---|
| set1 | 17 | 52.9% | 76.5% |
| set2 | 18 | 33.3% | 38.9% |
| set3 | 27 | **55.6%** | **81.5%** |
| set4 | 23 | **47.8%** | 60.9% |

**Mean first-exposure ~45%. Each tuning round buys ~25-30pp on its own set and ~5-13pp on fresh
data.** ⇒ **A keyword/lexicon classifier plateaus near 50% on these bios.** More keywords will
not break that; real improvement needs embeddings/LLM classification, which is outside Track A's
lane. The tuned suite stayed 42/42 throughout — it measures nothing about generalization.

⚠️ **All four sets have now been tuned against. Build set5 before quoting a new number.**
`heldout_accounts.json` holds the labelled sets; `eval_account_classify.py` re-derives any
number in seconds and prints "TUNED ON — optimistic" against every set that is no longer clean.

### Two rules REMOVED because measurement showed they are net-harmful
- **`_ATHLETE_CLASS`** (added by me in cycle 1) fixed 1 case and broke 3: `"drop 10-30kg+"` is
  weight loss, `"40 Under 40"` is an award, `"RFDL U21"` is a youth team. Adding exceptions to it
  is how this module overfits, so it is gone and @ravinderdahiya61kg is misclassified again.
- **`"use code"` as a strong BRAND marker.** An affiliate code is what a SPONSORED CREATOR posts,
  not what a brand says about itself — which matters doubly here, since finding sponsored
  creators is the project's whole purpose. Both corpus occurrences were creators, none were
  brands, and both were being dropped as brands (this module's worst error class).

Also fixed from set3: a club listing its leagues is still a club; "Official Handle"; inflected
"coached"/"coaching"; endurance sports; and product-category nouns demoted below the individual
checks, since `Fashion | Fitness | skincare | travel` is a topic list, not commerce.

⚠️ **Harness flaw caught before use:** `--propose` excluded the stored sets but NOT the tuned
suite, and offered @technicalguruji and @ajinkyarahane. Labelling those into "set3" would have
produced a clean-looking number that was not clean.

## ITEM 3 — TERMINAL (closed in cycle 2, verified in cycles 3-4)

See the cycle-2 section below for the full per-method table. Headline: name-gated **200 → 24**,
creators with a real name **43 → 211**, Reddit attempted **54 → 230 (20.8% → 88.8%)**.

## Corrections issued across this loop (all mine, all measured)
1. **"reddit search is flaky" — RETRACTED.** 0 empties in 36 paced calls, including the two
   queries that had failed. Burst-induced, not a defect.
2. **"bios are scarce" — was OUR BUG.** `fetch_profile()` returns the bio; the backfill discarded
   200 of them. That discard capped ITEM 2's held-out set at 17 cases.
3. **The shubmangill duplicate was mine, minutes old** — not a pre-existing bug of the Mumbiker
   Nikhil class, as I first read it.
4. **My sport-routing "fix" was wrong and was reverted.** I narrowed no-signal athletes from
   `["india","Cricket"]` to `["india"]` because cricket looked like a guess. Measured:
   Shane Watson r/Cricket **20** / r/india **0**; Leander Paes r/Cricket **0** / r/india **20**.
   A wrong sport sub returns *nothing*, not wrong data, because the relevance gate verifies every
   hit — so the omission cost ~20 real posts per cricketer and bought no correctness. 65 athletes
   restored; creators routed to r/Cricket 29 → 94.
5. **The first Reddit yield sample was contaminated by me.** I ran a 2-call Instagram dry-run
   while a Reddit job was live and starved 6 of 10 creators. **Two adapter calls were enough** —
   the rule is not "avoid sustained parallel jobs", it is *don't touch the browser at all while a
   browser job runs*.

## Other real bugs fixed this loop
| bug | evidence |
|---|---|
| a single failed comment read killed the whole creator | Tyrese Maxey collected 17 posts / 718 comments over 5 min, then one `reddit read` returned UNKNOWN and the creator was skipped with **no summary line at all** — so a productive run read as a total failure. Writes are incremental, so the loss is the *remaining* work, silently. |
| `clean_name` destroyed every non-Latin name | Python's `\w` does not match Unicode combining marks: `'नितिन चतुर्वेदी'` → `'न त न चत र व द'`. Now category-based; 4 names repaired. |
| `--handles` minted duplicate creators | `--platform reddit --handles <ig_handle>` keyed `get_or_create_creator` on NAME and searched `r/<ig_handle>`. My own test runs created 8 junk rows (259 → 267); cleaned up by re-pointing 40 real posts then deleting only rows verified empty across all 11 `creator_id` tables. |
| `--dry-run` wrote the checkpoint | a rehearsal marked creators as already-attempted |
| Wikipedia gate manufactured names | the reverse-prefix direction accepted @sagarliftz → "Sagar" |

## Found but not finished (handing over)
1. **The 3 misattributed sponsorship events are still in the DB** — `DLrSRdqTcEQ` (really
   anushkasharma), `DUkDWOYiL8x` (duroflexworld), `DW3hIgJDI3P` (reliancejewels). Re-attributing
   changes the graph Track B trains on, so it is a **user decision**. 32 of 37 pairs are
   independent of them. `audit_post_ownership.py --sponsored-only` re-checks in ~6 min.
2. **set5 for account_classify** — all four existing sets are now tuned against.
3. **Reddit yield rate is still not cleanly measured.** Three separate errors distorted it
   (contention I caused, silent creator aborts, and my bad sport routing). The 65 repaired
   athletes were searched with the wrong sub set and their yield is understated.
4. **Recency window is now Reddit's binding constraint**, not names — the same open decision as
   the out-of-window Instagram posts.
5. **Full-DB ownership audit not run** — 1,751 posts at ~10s each is ~5h. Only the sponsored
   subset (52) and a 15-post random sample were checked.

---

# TECH-DEBT LOOP — CYCLE 2 (2026-08-19)

**ITEM 3 closed. All three items now terminal.** ITEM 1 and ITEM 2 closed in cycle 1.

## ITEM 3 — Reddit real-name backfill: TERMINAL

### Resolved per method, against the 200 name-gated creators

| method | resolved | ceiling | note |
|---|---|---|---|
| **live Instagram profile fetch** | **168** | ~200 | 0 fetch failures |
| **Wikipedia (verified)** | **8** | — | of the 32 the Instagram pass could not resolve |
| YouTube channel *description* | 0 applied | **5** | see below — real but structurally capped |
| YouTube channel *title* | 0 applied | 5 | glued; 1 usable only after cleaning |
| `instagram_profiles.full_name` | — | 8 | a storage gap, not an availability gap |
| **genuinely unresolvable** | **24** | — | handle-only personas; an acceptable outcome |

Every DB-side source was bounded BEFORE any network time was spent, which is what showed the
live fetch was the only lever worth pulling.

**The YouTube about-text source works and is still not worth much.** It genuinely carries names
the title cannot — `@jumper_aj_`'s title is the useless "jumperAj" while its description reads
*"this is abhishek narayan jha"*, and `@corysmithhoops` names "Cory Smith" in prose. But only
**5** of the 200 name-gated creators have a YouTube channel at all, so the method's total reach
is 2-3 creators. Confirmed-but-capped, not unfixable.

### Outcome

| metric | before | after |
|---|---|---|
| creators with a real name | 43 | **211** |
| name-gated | 200 | **24** |
| Reddit-eligible (real, searchable name) | ~5 | **176 assigned topic subs** |
| **Reddit attempted** | 54 (20.8%) | **230 (88.8%)** |
| Reddit with content | 18 (6.9%) | 22 (8.5%) |
| computable pairs | 37 | 37 (unchanged) |

**Verified end-to-end, not assumed.** r/india search for "Sunil Chhetri" returns **40 results,
0 off-topic** — the orchestrator's own relevance gate passed all 40 — where the handle
`chetri_sunil11` previously returned pure noise. All 40 were then dropped as **stale**.

⇒ **The name was the precondition; the recency window is now the binding constraint.** Search is
unblocked, `attempted` moves hugely, and *collected volume* barely moves. Both halves are true
and reporting only one would be misleading.

## Corrections issued this cycle

1. **RETRACTED: "reddit search is flaky."** Cycle 1 inferred that part of the 77% no-content
   population might be flakes. A follow-up could not reproduce it: **0 empties in 36 paced
   calls** (20 subreddit-scoped, 16 site-wide), including the two exact queries that had failed.
   Those zeros came inside a 12-query burst at ~4s spacing, so they look burst-induced. The
   retry-on-empty is kept as a cheap safety net that makes any recurrence visible in the log —
   not as a fix for a proven bug.
2. **"Bios are scarce" was OUR BUG, not a fact about the data.** `fetch_profile()` returns name
   and bio in one call; the backfill stored only the name and discarded 200 bios. That discard
   is the direct cause of both "only 26 of 16,815 rows have a bio" (which capped the
   account_classify held-out set at 17 cases) and "sport is not in the schema, so athletes
   cannot be routed". Now persisted; 133 rows are re-fillable at zero extra network cost.
3. **The shubmangill duplicate was mine, minutes old.** I first read it as a pre-existing bug of
   the same class as the Mumbiker Nikhil incident. It was created by my own test run.

## Bugs found and fixed this cycle

| # | bug | evidence |
|---|---|---|
| 1 | `clean_name` destroyed every non-Latin name | Python's `\w` does not match Unicode combining marks, so Devanagari matras were stripped: `'नितिन चतुर्वेदी'` → `'न त न चत र व द'`. Not a worse name — an unsearchable one. Now category-based (L/M/N). 4 names repaired. |
| 2 | `--dry-run` wrote the checkpoint | a rehearsal marked creators as already-attempted |
| 3 | cricket asserted on no evidence | **41 of 44** eligible athletes (93%) routed to r/Cricket with no sport signal — Leander Paes (tennis), Sunil Chhetri (football), Ravinder Dahiya (wrestling), Manush Shah (table tennis). Now returns r/india: generic but true. |
| 4 | `--handles` minted duplicate creators | `--platform reddit --handles <ig_handle>` keyed `get_or_create_creator` on NAME and set `reddit_handles=[<ig handle>]`, so the worker searched `r/<ig_handle>` — a subreddit that does not exist. **My two test runs created 8 junk rows (259 → 267)** and split shubmangill's Reddit data onto a row its Instagram data could never reach. |
| 5 | Wikipedia gate manufactured names | the "title prefixes handle" direction accepted `@sagarliftz` → "Sagar". Removed; no genuine case needed it. |

**Cleanup of bug 4 was done the Gujarat Titans way**: re-point, then delete. The 40 real
r/shubmangill posts were moved onto the genuine creator, and the junk rows deleted only after
each was verified empty across all 11 `creator_id` tables. Back to 259, 40 posts preserved.

## ⚠️ Contention is sharper than previously recorded

The first 10-creator yield sample failed on 6 of 10 creators with `TypeError: Failed to fetch` —
the documented Instagram/Reddit contention signature. **I caused it** by running a 2-call
Instagram dry-run while the Reddit job was live.

That is a stronger result than the original incident: **two adapter calls were enough to starve
a running Reddit job.** The rule is not "don't run sustained parallel jobs" — it is
**don't touch the browser at all while a browser job is running.** The clean re-run showed 0
such failures.

## Found but not finished
1. **Bio-capture pass over the 133 bio-less rows** — coded, dry-run verified, not yet run.
2. **`account_classify` set #3** — worth building only AFTER the bio pass, which will finally
   supply a real corpus instead of 17 cases. Until then 44.4% is not a clean number.
3. **The 3 misattributed sponsorship events** (ITEM 1) remain in the DB, awaiting the user's
   call. 32 of 37 pairs do not depend on them.
4. **Sport still absent from the schema** — the fix stops the wrong guess but does not recover
   the right sport. The bio names it; the bio pass above is the unlock.
5. **Recency window is now Reddit's binding constraint**, not names. Whether to widen it is the
   same open user decision as the out-of-window Instagram posts.

---

# TECH-DEBT LOOP — CYCLE 1 (2026-08-19)

Scope: the 4 open technical items in CAPSTONE_NEXT_STEPS.md P0.4, folded into 3 numbered
ITEMs (ITEM 1 covers two of them). **ITEM 1 and ITEM 2 are terminal. ITEM 3 is partially
done.** The loop continues.

## ITEM 1 — orchestrator position-matching: TERMINAL (fixed + verified on real data)

### 1.1 Adapter retry — done, but its benefit is currently UNMEASURABLE
`run_opencli` had no retry at all: one shot, raise, caller falls back to browser-only. It now
retries 3x with 5s/15s backoff. **A 429 is deliberately never retried** — that is a real
throttle, and hammering it is how the multi-hour blocks in this file were earned.

Honest caveat: the adapter succeeded on **every** call this cycle (9/9 limit tests, 20/20
held-out fetches), against ~4-of-6 last round. Retry recovered **0** calls — not because it
does not work, but because nothing failed. Unproven, not disproven.

### 1.2 The `--limit` mystery — SOLVED
`--limit` **does** reach the call. It works downward and clamps upward:

| `--limit` | 3 | 5 | 12 | 15 | 20 | 25 | 40 |
|---|---|---|---|---|---|---|---|
| rows returned | 3 | 5 | 12 | 12 | 12 | 12 | 12 |

Verified on `mostlysane`; 40 to 12 reproduced on `carryminati` and `taarukraina`.
**Cause: `--limit` truncates an already-scraped set, and the adapter only ever scrapes
Instagram's 12-post first-paint grid. It has no pagination.** Not fixable adapter-side; the
browser path already scrolls, which is why it reaches 40 and the adapter cannot. Closed.

### 1.3 Structured date metadata on the permalink page — CONFIRMED, now used per post
`og:description` carries date, likes, comments AND the owning username, keyed to the post url
itself. Parser unit-tested 4/4 including the abbreviated-count case. Counts are written ONLY
when Instagram did not abbreviate them (a "1M" for a true 1,416,111 would corrupt a real value).

### 1.4 The fix — could NOT be done as literally specified
`opencli instagram user --help` documents its output columns as
`index, caption, likes, comments, type, date`. **There is no url, shortcode or id** — a
`post_id` join against the listing is impossible, there is nothing to join on. Confirmed
against real json, not just the help text.

Implemented instead, same goal (metadata provably belongs to its post):
- **`match_listing_meta()`** joins by caption content (symmetric prefix, since the listing
  truncates at 100 chars while the page has the full text) and **refuses ambiguous matches**
  rather than guessing. A missing date is recoverable; a confidently wrong one is not.
- **`og:description` per post**, fetched from the post's own url, so it cannot be
  misattributed, and it reaches posts past the 12-row ceiling that were permanently NULL.
- Recency filtering now uses the post's own date, not a positionally guessed one.

### 1.5 — the verification found something WORSE than misalignment
A profile grid mixes in posts owned by **other accounts**. On `mostlysane`, 4 of 12 grid links
belonged to `netflix_in` and `exhibitmagazine`, interleaved from position 2:

```
 1 /mostlysane/reel/DcLAofft5_h/      own
 2 /netflix_in/reel/Db-JzrUGjyB/      FOREIGN
 3 /netflix_in/p/Db72ic4kQiM/         FOREIGN
 4 /exhibitmagazine/p/Db3BGJgsSnp/    FOREIGN
 5 /mostlysane/p/Db2norRjVTl/         own
 6 /netflix_in/reel/Db2nGH6FaO6/      FOREIGN
```

The old selector took every `/p/` and `/reel/` link and wrote them all with
`username=<handle>, creator_id=<this creator>`. Two consequences:
1. **Another account's post, and its engagement counts, recorded as this creator's.**
2. It **proves** positional matching was wrong — the listing holds only her own posts by
   recency, so from grid #2 on every pairing was offset. At most **1 of 12** was correct.
   That is the confirmation three rounds of flagging never produced.

`own_post_paths()` now filters foreign links before they consume the post cap.

**Measured contamination in data already stored** (`audit_post_ownership.py`, new, read-only):

| sample | resolvable | misattributed | rate |
|---|---|---|---|
| random posts | 14 | 2 | **14.3%** |
| sponsorship events | 52 | 3 | **5.8%** |

| post | stored as | real owner |
|---|---|---|
| `DLrSRdqTcEQ` | virat.kohli | anushkasharma |
| `DUkDWOYiL8x` | virat.kohli | **duroflexworld** (brand) |
| `DW3hIgJDI3P` | pratibha_ranta | **reliancejewels** (brand) |

Two of three are brand-owned — a brand's own ad recorded as a creator's sponsorship event.
That is a label error, not an attribution nit.

**Reach into the objective: 5 of 37 computable pairs (13.5%) depend on one of these events.
32 survive, still above the 20 floor.** A correctness problem, not a go/no-go one.

**Left for the user, deliberately not actioned:** re-attributing a sponsorship event changes
the collaboration graph and the pair count Track B trains on. `--fix` is intentionally absent.

## ITEM 2 — account_classify: TERMINAL (characterized, fixed, honestly re-measured)

**The first finding is about the measurement, not the classifier:** only **26 of 16,815**
`instagram_profiles` rows carry any bio (0.15%), 22 over 25 chars — so a DB-sourced held-out
set caps at 17 usable cases. And **no held-out set was ever stored**; the 57% was a one-off
nobody could reproduce. Both sets are now committed as `heldout_accounts.json`.

**The failure pattern (set #1, 17 hand-labelled real bios, 52.9%):** every error was "to other"
— the classifier fails by *abstaining*, never by confusing two real categories. Even split:
- **Group A, fixable (4):** the occupational word is present but missing from the lexicon —
  "I act...at the movies", "one shuttle at a time", "In Cinemas now", and `tennis` glued inside
  `@saniamirzatennisacademy` (word boundaries cannot see inside a handle).
- **Group B, unrecoverable (4):** no occupational signal at all — "Proud parent and Blessed
  son", "we're all just walking each other home".

Honest bio-only ceiling: **13/17 = 76.5%, not 100%**. Fixing Group A hit exactly 76.5%, the 4
remaining misses being precisely the 4 Group-B cases predicted.

**Does it generalize? Only weakly — that is the real answer:**

| | pre-fix | post-fix |
|---|---|---|
| set #1 (the set the fix came from) | 52.9% | **76.5%** (+23.6pp) |
| **set #2 (fresh, live-fetched, never tuned on)** | **33.3%** | **44.4%** (+11.1pp) |
| tuned suite | 42/42 | 42/42 |

Most of the set-#1 gain was overfitting. Real generalization is +11.1pp.

**Set #2 exposed an error class set #1 never showed — CONFIDENT wrong answers, worse than
abstaining**, contradicting the "all errors abstain" pattern:
- `"world championship"` in `_LEAGUE` caught an athlete listing events he **won**.
- bare `"cf"` in `_TEAM` caught `"CF Coach"` (CrossFit) on a fitness creator.
- a leading trademark-symbol test dropped `@athleanx`, a real creator who trademarked his own
  programme name — this module's **worst** error class (a false BRAND silently discards a
  person instead of sending them to review).

Fixed by moving the symbol test below the individual checks, dropping `"cf"`, and separating
leagues from athletes on weight-class/age-group markers (`U-23`, `61kg`) — no league is named
after a weight class. **Scoping "world championship" by field was tried first and does NOT
work**: `@e1series` has it in the bio too, exactly like the athlete.

**Set #2 has now been tuned against as well. A clean number needs a set #3** — build one the
same way rather than re-quoting 44.4% as if it were untouched.

## ITEM 3 — Reddit real-name backfill: IN PROGRESS (step 1 done, and it inverts the premise)

**Step 1 as specified. Handle-as-is search does NOT fail by returning zero — and "does it
return results" is the wrong test.**

Population first: of 205 name-gated creators, **200 have `name == handle`**, 5 are gated for
other reasons. But the 200 are mostly not famous people with a recoverable name — the list is
dominated by small accounts, orgs and handle-only personas (`sultaan_pahalwan`, `jumper_aj_`,
`fyxscasts`, `sofii_flow_`, `totalcombatfitness`).

Site-wide search on real handles returns plenty of results, and they are **noise**:

| query | results | actually relevant |
|---|---|---|
| `jumper_aj_` | 15 | **0/5** — r/nba "jumper" plus a player called "AJ", matched separately |
| `fit_boult` | 15 | **0/5** — Trent Boult the cricketer plus "fit" |
| `sunrisershyd` | 15 | **4/5** — a real, recognizable abbreviation |

**Reddit tokenizes on `_` and `.`, so a handle-shaped name returns plausible-looking garbage
rather than nothing.** Worse than failing, and exactly the false-positive mechanism that
previously forced purging 10 posts and 67 comments. So `name = handle` IS genuinely blocking,
but the recorded reason ("returns 0 results") is wrong.

**Second finding: `reddit search` is FLAKY, and a flake is indistinguishable from a real
negative.** `"Sunrisers Hyderabad"` and `"Royal Challengers Bengaluru"` each returned **0** on
first run and **15** on retest, query unchanged. `run_opencli`'s new retry does **not** cover
this — a search that exits 0 with an empty list counts as success. **Any past conclusion of the
form "creator X has no Reddit presence" may be a flake, including part of the 77% figure.**

### Still to do on ITEM 3 (cycle 2)
- Retry-on-empty for `reddit search`, then re-measure how much of the 77% survives.
- The two untried name sources: the YouTube channel **description/about** text (a distinct
  field from the title already checked), and a lightweight Wikipedia/web lookup for well-known
  figures.
- Report resolved-per-method and how many are genuinely unresolvable — a legitimate outcome for
  handle-only personas, not a failure.

## Found but not finished (cycle 1)
1. **The 3 misattributed sponsorship events are still in the DB** — awaiting the user's call,
   since fixing them changes Track B's graph. 32 of 37 pairs are independent of them.
2. **Full-DB ownership audit not run** — 1,751 posts at ~10s each is roughly 5h. Only the
   sponsored subset (52) and a 15-post random sample were checked.
3. **`account_classify` set #3 not built** — 44.4% is no longer a clean number.
4. **Taxonomy gaps found while labelling**: a football club's assistant coach, and a marathon
   *event*, have no correct category. Both excluded from set #2 rather than force-labelled.
5. **Retry's real-world benefit unmeasured** — the adapter never failed this cycle.

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

# ✅ LOOP COMPLETE (2026-08-18) — STOPPED ON "SUFFICIENT": 37 computable pairs

**13 cycles. Stop condition: Sufficient (pairs ≥ 20) — reached 37.** Both cron jobs cancelled:
`225af3a3` (the post-crash re-creation) and `8b00cead` (the ORIGINAL, created before the
laptop crash — it survived and re-fired the loop once after completion, which is why a
loop prompt may appear in the transcript after the final report). `CronList` now reports
no scheduled jobs. **A fresh session does NOT need to resume this loop.**

## Where the loop stopped, phase by phase

**Not mid-phase. All three phases ran to completion and the loop body then hit its stop
condition.** A fresh session has nothing to pick up here.

| Phase | Status | What it left behind |
|---|---|---|
| **Phase 0 — baseline stats** | ✅ complete, cycle 0 | The baseline column of the table below. Reproducible any time via `loop_stats.py`; do **not** hand-derive it again. |
| **Phase 1 — parallelization hypothesis test** | ✅ complete, and the hypothesis **FAILED** | Instagram and Reddit run **sequentially**. See below. |
| **Loop body** | ✅ 13 full cycles, stopped on "Sufficient" | 37 computable pairs (target ≥ 20). |

**Phase 0 baseline, exactly as measured (259 creators, cycle 0):** Instagram attempted
**121 / 259 = 46.7%**; YouTube attempted **259 / 259 = 100%**; Reddit attempted
**36 / 259 = 13.9%**. Computable pairs at baseline: **3**. `loop_stats.py` deliberately
measures *attempted*, not *succeeded* — a creator scanned and found empty is progress, and
counting successes would have made the loop chase the same dead accounts forever.

### Phase 1 — the resource-separation hypothesis did NOT hold

The hypothesis was that the original contention incident came from two *site adapters*
sharing one tab lease, and that a **site adapter (Instagram) + a named browser session
(Reddit)** would touch different resources and so run concurrently.

- **First measurement said clear — and it was wrong.** A 3-call burst showed no contention.
  I reported it clear.
- **Sustained load reproduced the original incident exactly.** Roughly **4 minutes** after
  the concurrent Instagram job started, Reddit queries began failing; the *same* queries
  succeeded immediately once Instagram stopped. Same signature as the first incident.
- **Retracted.** The burst test was too short to reach the starvation point. Lesson recorded:
  concurrency clearance requires a *sustained* test, never a burst — the same lesson the
  Instagram-throttle probe taught earlier in this file.

**Fallback state right now: sequential, and that is the committed configuration.** YouTube
remains safe to run alongside either (verified: it makes zero browser calls, `urllib`
straight to `googleapis.com`). Do not re-open this without a sustained test of ≥ 10 minutes.

### Kerala Blasters — yes, connected

It was an orphan (0 graph edges) with 2 sponsorship events living on **YouTube**
("brought to you by"), invisible to an Instagram-only event query. Roster extraction found
co-authors via **rival clubs**, giving it **2 resolving edges** and the loop's first
YouTube-sourced event pair. Two fixes were required and both are in code: the roster
extraction itself, and the `loop_stats.py` event query, whose *event* side was
Instagram-only and silently hid these events (the neighbour side had already been fixed —
the same blind spot, twice).

### The 5 priority Instagram creators — all five now have real content

Verified live at handoff (`instagram_posts`, 2026-08-18):

| creator | handle | posts | sponsored | undated sponsored | dated posts | resolving edges |
|---|---|---|---|---|---|---|
| CarryMinati | `carryminati` | 40 | 6 | **0** | 21 | 1 |
| Ajinkya Rahane | `ajinkyarahane` | 39 | 1 | **0** | 20 | 4 |
| KKR | `kkriders` | 40 | 1 | **0** | 18 | 16 |
| Prajakta Koli | `mostlysane` | 40 | 2 | **0** | 29 | 8 |
| Taaruk Raina | `taarukraina` | 34 | 4 | **0** | 26 | 2 |

(The brief spelled it `kkirders`; the real handle is `kkriders`.) All five were blocked at
loop start — the Instagram adapter was returning `chrome-error://chromewebdata/`. They were
collected via the **browser-only** path, and every one of their sponsored posts is now dated,
which is what made them usable as pair endpoints. `kkriders` at 16 resolving edges is the
densest node in the priority set and the best target for any further deepening.

### Found but NOT finished investigating

Ranked by how much they could still bite:

1. **`orchestrator.py:447` positional metadata matching.** `meta = posts_meta[i] if i <
   len(posts_meta) else {}` pairs a post with metadata **by list position**, against a
   listing that caps at 12 items. If the two lists ever diverge, metadata silently attaches
   to the wrong post. I audited 15 caption-verified comparisons and found **0 conflicts** —
   but 15 is a small sample and it is **not proof of safety**. Fix is to match on `post_id`.
2. **Instagram adapter intermittency, never root-caused.** `opencli instagram user` succeeds
   roughly **4 of 6** attempts with no pattern I could isolate; the browser-only path is the
   working substitute, not a diagnosis. Phase 1L settled that it is *not* pacing.
3. **`account_classify.py` held-out accuracy is 57%** (30% bio-only → 47% +affiliation →
   57% +grid). The 42/42 on the tuned suite is **overfit — do not quote it**. ~43% of
   categories are still wrong, which matters for Reddit sub-routing.
4. **The 12-post listing ceiling itself.** `--limit 40` returns exactly 12, verified on two
   creators at both values. My earlier claim that `--limit` was "very likely the entire
   cause" was **wrong**. Root cause unknown; it caps every Instagram creator at 12 fresh
   posts per pass.
5. **Out-of-window posts** — dating exposed content back to **2024-09**. Not a bug; undated
   posts could never be evaluated by the recency filter. Needs the user's keep-or-purge call
   (item 1 below) and some of the 37 pairs depend on those events.
6. **Reddit's 200 name-gated creators.** The gate is a missing real name, not a failed
   search. A better name source would unlock them in bulk; scraping more Reddit will not.

## Baseline → final

| | baseline | final |
|---|---|---|
| Instagram attempted | 121 (46.7%) | **130 (50.2%)** |
| Instagram with content | 36 (13.9%) | **47 (18.1%)** |
| YouTube attempted | 259 (**100%**) | 259 (**100%**) |
| YouTube handles / deepened | 41 / 39 (95.1%) | 41 / 39 (95.1%) |
| Reddit attempted | 36 (13.9%) | **54 (20.8%)** |
| Reddit with content | 16 (6.2%) | 18 (6.9%) |
| Reddit name-gated | 215 (83.0%) | **200 (77.2%)** |
| Reddit untouched | 8 (3.1%) | **5 (1.9%)** |
| **COMPUTABLE PAIRS** | **3** | **37** |
| Collaboration edge pairs | 161 | **170** |
| Sponsored posts still undated | 25 | **0** |

## What actually moved the number

1. **`og:description` date backfill (decisive)** — pairs 14 → 37 in one run, 46/46 filled,
   0 failures. Every other date source failed on sponsored posts specifically.
2. **Deepening contentless neighbours of dated events** — +4 pairs in one run (Bhuvan Bam's).
3. **Kerala Blasters roster extraction** — connected an orphaned creator via rival-club
   co-authors, giving the first YouTube-sourced event pair.

## ⚠️ Open items for the user (none actioned unilaterally)

1. **Out-of-window posts are now visible.** Dating revealed content back to **2024-09**, and
   several pairs rest on events dated **2025-07-03 / 2026-01-21 / 2026-02-09** — outside the
   183-day rolling window. Cause: undated posts could never be evaluated by the recency
   filter. **Decide: keep (they supply scarce "before" data) or purge (honour the window).**
   Some of the 37 pairs depend on those events.
2. **Dates carry ±1 day** (timezone boundary; 3 of 6 off by one in validation). Immaterial for
   straddle analysis, must not be presented as exact.
3. **3 handles were wrongly routed to brand_signals** before the grid-BRAND bug was fixed
   (`brisonfernandes17_`, `duamirzaasad`, `abhishekganguly`) — re-run
   `push_checkpoint_candidates.py --from-db` to surface them as candidates.
4. **Reddit remains weak**: 77% of creators are name-gated, and of 38 searched only one
   produced posts (which were false positives). Not a productive lever on this set.

## (historical cycle detail below)

**A fresh session resuming this loop should read THIS section first — it is the live state.**

## ✅ CYCLE 12 — THE DATE BLOCKER IS SOLVED. Pairs 14 → 16 and climbing

`backfill_dates_from_og.py` is running against the 46 dateless sponsored posts with a
**100% hit rate so far (0 failures)**, and pairs moved **14 → 16 on the first 4 dates alone**.
This is the constraint cycle 10 quantified as worth 50-70 pairs.

Source: the post page's `<meta property="og:description">`, which carries a date for ANY post
including captioned/sponsored ones — the exact gap every other mechanism had. Validated 6/6
against DB ground truth (3 exact, 3 off-by-one from the known timezone boundary). **Date
only** — the like/comment counts in that string are abbreviated ("1M" for 1,416,111) and
drift with engagement, so writing them would corrupt real values.

### ⚠️ SIDE-FINDING: undated posts BYPASSED the recency filter, so the backlog skews OLD
`anushkasharma`'s newly-dated posts run back to **2024-09-18**, far outside the 183-day
rolling window (cutoff 2026-02-15). Cause: the recency filter compares a post's date to the
cutoff, so a post with **no date could never be filtered** and was stored regardless of age.

Already surfaced: **21 posts now dated before the cutoff, 5 of them sponsorship events.**

Two consequences, neither yet decided:
1. **Data hygiene** — the dataset contains out-of-window content that the rolling-window
   policy would have excluded. Now visible for the first time *because* dating works.
2. **Pair impact is mixed, not purely good** — an old *event* is unlikely to straddle
   (neighbours' collected posts are recent), but old *neighbour* posts are exactly the
   "before" side that was missing. Both effects are live in the current count.

**Needs a user decision:** keep the pre-cutoff posts (they supply scarce "before" data) or
purge them to honour the rolling window. Not actioned unilaterally — it is a policy call, and
deleting real scraped data is not reversible.

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
