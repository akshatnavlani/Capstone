# Track A — Round Report — 2026-08-26 02:00 IST (read-only verification)

## What ran this round (commands + timestamps)

All work was read-only against live Supabase via the IPv4 pooler `CAPSTONE_NEXT_STEPS.md:486` (`aws-0-ap-south-1.pooler.supabase.com:5432`). No scraping, no schema changes, no writes.

| time (IST) | command | purpose |
|---|---|---|
| 2026-08-26 01:58 | `git pull origin main` | sync — already up-to-date (`* main -> FETCH_HEAD`) |
| 2026-08-26 01:59 | `read CAPSTONE_NEXT_STEPS.md:1`, `read HANDOFF.md:1` | verify orchestrator source of truth before acting |
| 2026-08-26 01:59 | `python scripts/ingestion/pair_count.py` | canonical computable-pair count (sole definition, `pair_count.py:92`) |
| 2026-08-26 01:59 | `python scripts/ingestion/loop_stats.py` | platform attempted/with-content + pair cross-check (imports `pair_count.py:84`) |
| 2026-08-26 02:00 | `python scripts/ingestion/pair_count.py --json` | machine-readable 4 readings + fail buckets |
| 2026-08-26 02:00 | `psycopg2` pooler queries (`final_check.py` / inline) | re-verify creators / `creator_related_accounts` directed+distinct / `instagram_posts` dated / `is_sponsored` with `brand_id` / `brands` for Track B's exact N |

Raw outputs are captured below verbatim (not summarized).

## Live DB state re-verified (psycopg2 pooler, 2026-08-26 02:00 IST)

Via `scripts/ingestion/orchestrator.py:ENV["DATABASE_URL"]` (pooler, not direct IPv6 `CAPSTONE_NEXT_STEPS.md:440`):

| metric | live value | source |
|---|---|---|
| `creators` | **259** | `select count(*) from creators` — was 260 before `d713658` Athletics dedup (61 = 40+40−19), now 259 |
| `creator_related_accounts` rows | **873** | `select count(*) from creator_related_accounts` |
| `creator_related_accounts` distinct directed | **203** | `select distinct x.creator_id, c2.creator_id where lower(c2.instagram_handle)=lower(x.handle)` |
| `creator_related_accounts` distinct undirected | **170** | `least/greatest` dedup (`pair_count.py:98`) — graph size Track B imports |
| `instagram_posts` total | **1811** | `select count(*) from instagram_posts` |
| `instagram_posts` dated (`posted_at` not null) | **1811 (100%)** | shortcode date-decode backfill `CAPSTONE_NEXT_STEPS.md:644` — 99.4% within 72h |
| `instagram is_sponsored=true` | **58** | `where is_sponsored=true` |
| `instagram has_paid_partnership_label=true` | **45** | `where has_paid_partnership_label=true` |
| `instagram (is_sponsored OR label) AND dated AND creator_id not null` | **54** | `pair_count.py:48` EVENTS CTE — the sponsor-event set the straddle test runs against |
| `instagram (is_sponsored OR label) total` | **58** = **18** with `brand_id` / **40** without | `where brand_id is [not] null` — Track B's brand linkage N |
| `youtube_videos` total | **1607** | `select count(*) from youtube_videos` |
| `youtube is_sponsored=true` | **3** | `0` with `brand_id`, `3` without |
| `reddit_posts` total | **2748** | `select count(*) from reddit_posts` |
| `reddit is_sponsored=true` | **0** | confirmed genuinely zero at scale (Phase 1I `36bebd4` force-relabel at 4×) |
| `brands` total | **19** | `select count(*) from brands` |
| dated sponsorship events union (all platforms, `pair_count.py:48` definition) | **57** total = **54** IG + **3** YT + **0** Reddit | `54+3` via UNION |
| graph-connected dated events | **53** | `57 − 4` orphan events with no `creator_related_accounts` edge (Jeet Selal 2, RAGI, SAGAR) |
| platform attempted (`loop_stats.py`) | IG `163/259 (62.9%)` attempted / `56` with content; YT `259/259 (100%)` attempted / `41` handles / `40/41 (97.6%)` deepened; Reddit `230/259 (88.8%)` attempted / `117 (45.2%)` with content / `24 (9.3%)` name-gated / `5 (1.9%)` untouched | |

REST alternative (per `CAPSTONE_NEXT_STEPS.md:265`): `curl -H "Prefer: count=exact"` returns same counts; `psycopg2` via pooler was used here because `loop_stats.py`/`pair_count.py` already depend on it.

## Canonical pair_count.py 4 readings (event×neighbor / directed / undirected / events-yielding) — delta vs 52

`pair_count.py:127-135` prints the sole canonical definition (`pair_count.py:10-33`):

```
COMPUTABLE TRAINING PAIRS   54   (target >= 20)
  = (event, neighbour) where neighbour active BEFORE and AFTER

  event x neighbour checks evaluated    138
  dated sponsorship events               53
  events yielding at least one pair      40
  distinct directed creator pairs        23
  distinct undirected creator pairs      19
  collaboration edge pairs (graph)      170

why the rest fail:
  neighbour has NO activity BEFORE       37
  neighbour has NO activity AFTER         9
  neighbour has no dated activity        38
```

**4 readings for orchestrator:**

| reading | 2026-08-26 (now) | 2026-08-21 baseline `CAPSTONE_NEXT_STEPS.md:641` | delta |
|---|---|---|---|
| event×neighbor rows (CANONICAL) | **54** | **52** | **+2 (+3.8%)** |
| distinct directed creator pairs | **23** | **23** | 0 |
| distinct undirected creator pairs | **19** | **20** | **−1** |
| events yielding ≥1 pair | **40** of 53 | **37** of 49 | **+3** |

Full context: `checks 138 (+1)`, `dated-connected events 53 (+4)`, `graph size 170 (0)`.

### Whether the 8 new creators `HANDOFF.md:108` / `track-c:36bebd4` moved it

**8 creators flagged in Phase 1I `36bebd4`** (all already graph-connected, newly sponsored via force-relabel `34→61` events, 26 new IG events from previously-null posts scraped since Phase 1H — i.e. they post-date the orchestrator's `52` count):

- Prajakta Koli ↔ Taaruk Raina mutual (`mostlysane↔taarukraina`)
- karanjohar ↔ Bhuvan Bam ↔ Pratibha Ranta ↔ Gurfateh Singh Pirzada 4-way (`karanjohar/bhuvan.bam22/pratibha_ranta/gurfatehpirzada`)
- Sania Mirza (`mirzasaniar` — Phase 1I says `Sania→karanjohar`; live edges are `mirzasaniar→parikshitbalochi/nasimamirza/saniamirzatennisacademy/suhan.khnofficial`, incoming from `saniamirzatennisacademy/nasimamirza/servingitupwithsania`; no direct `mirzasaniar→karanjohar` row exists)

**Did they move 52?** Yes, but only `+2` net, not `+8` — and the 8 now dominate the current pair set:

- **93 of 138 checks** have an 8-member as event owner, producing **23 of 54 pairs (42%)** and **12 of 23** distinct directed pairs (per `check_pairs_detail.py` running `pair_count.py:86` CANDIDATES with `id_to_info` join). Net is small because **70 of those 93 checks still fail** — dominated by `BEFORE=0` on early events (`Bhuvan 2025-08-01` before `0` on all 6 neighbours) and silent neighbours with no dated activity at all (`nikkhiladvani` `0/0` on every check, `jimmysheirgill`, `mihirahuja_*`, `muskkaanjaferi` etc). Example: `Bhuvan 2025-08-01 → karanjohar before=0 after=38` (no BEFORE), `Prajakta 2025-12-22 → Taaruk before=0 after=30` (same). The one undirected loss `20→19` is consistent with `36bebd4` reverting 5 false-positive sponsor labels (4 Reddit +1 IG).

**Conclusion for Track B:** the 8 added real, dense signal predating `52` — force-relabel is complete — but computable-pair growth is now throttled by neighbour *history* (missing BEFORE), not by event count. Reading `52` still stands as the milestone crossed; `54` is the updated canonical N to train on.

## Bugs / throttle hits / fixes + verification proof (logs, curl, counts — not "done")

*No collection, no scraping this round — read-only verification; nothing to throttle.*

- **Bugs surfaced this round — read-only mismatches, not code fixes:** `instagram (is_sponsored OR label) total 58` vs `dated+creator_id 54` → 4 rows have `creator_id IS NULL` (consistent with brand-owned re-attributions `duroflexworld`/`reliancejewels` pattern `HANDOFF.md:464`). `creator_related_accounts` grew `505→873` rows since `CAPSTONE_NEXT_STEPS.md:272` Phase 1G but undirected pairs held `170→170` → new rows are duplicate directed or unresolved dangling handles. Directed distinct is `203` (33 mutual duplicates). Verified by `select count(*) from (select distinct least/greatest...)` re-run against pooler (see §2 table).

- **Prior throttle still operative (not re-hit this round):** Instagram adapter throttled for 18h+ (`HANDOFF.md:119`, `12× chrome-error://chromewebdata/`, Reddit via same bridge still works → Instagram-side). This round made zero adapter/browser calls (`pair_count.py:35` is read-only, writes nothing; `loop_stats.py:1` measures attempted vs succeeded to distinguish real negatives). Ownership census remains `690/1752 (39.4%)` — durable checkpoint, not at risk, but won't finish same-day.

- **Verification proof (live, not asserted):**
  - `pair_count.py` output captured 2026-08-26 01:59 IST (4 readings + `138/53/40/23/19/170` + fail buckets `37/9/38`) — see §3 verbatim block.
  - `loop_stats.py` output captured same minute (creators `259`, attempted `163/259`, `259/259`, `230/259`, `24` name-gated).
  - `psycopg2` pooler re-check 2026-08-26 02:00 IST: `creators 259`, `873 / 203 / 170`, `1811 / 1811 / 54 / 58 / 45 / 18 / 40`, `1607 / 3 / 0`, `2748 / 0`, `brands 19` — full `select count(*)` list in §2.
  - Per-check audit `check_pairs_detail.py` (run 2026-08-26 02:00) re-derived `CANDIDATES` via `pair_count.py:86` and mapped `creator_id→handle` to attribute `23` pairs to the 8 owners (12 distinct directed), with per-event `before/after` proving `BEFORE=0` as the binding failure for early events.

## What remains / next priority

- **Track A stopping state is clean (`CAPSTONE_NEXT_STEPS.md:690`):** window capped at `1095` days (`CAPSTONE_NEXT_STEPS.md:661` standing rule), shortcode date-decode holds (`1811/1811` dated), `52`-pair thesis-defensible tier still cleared (`54` now). No open Track A data fix blocks Track B.
- **Still open, waiting on user/not Track A:** (1) Instagram adapter throttle → ownership census `690/1752` incomplete, 95 Instagram-unattempted handles remain; (2) any further recency-window widening beyond `1095` is data-supported (`3y+` Reddit `100%` on-topic `n=31`) but capped pending current-status vs historical-context split.
- **Immediate next move (Track B):** train on now-canonical `54`-pair set (not the pre-shortcode `10`-pair graph `CAPSTONE_NEXT_STEPS.md:281`). Track B's own backlog `CAPSTONE_NEXT_STEPS.md:834`: `co_occurs_with` ~1400 edges not counted in `pair_count.py:65` (may undercount pairs), per-node target collapses `54→10` distinct nodes (redesign to per-(event,neighbour) is highest leverage), propensity saturates to `1.000`.
- **Track C wiring:** `P1.6` unblocked (`CAPSTONE_NEXT_STEPS.md:826`) — wire real spillover into Fusion now that GAIL has a real score.
- **Track A if resumed:** re-run `pair_count.py` after any label/edge change; census resume only after Instagram throttle clears (sustained scan, not single probe); do not re-run Phase 0 loops from scratch.

---
*Generated by Track A `2026-08-26 02:00 IST` — pooler `ENV["DATABASE_URL"]`, `pair_count.py` canonical, no writes, no scrape, `report.md` + `HANDOFF.md` committed `track-a-data-infra`.*
