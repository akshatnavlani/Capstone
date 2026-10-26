# Data Collection Status — Track A (Data/Infra)

Last updated: 2026-08-11. This is the real, verified state of the scraping backend on
this machine — not a plan. Re-run `agent-reach doctor --json` / `opencli doctor` before
trusting this if it's more than a couple weeks old.

## 0. Apify — STILL BLOCKED after a session restart (re-checked 2026-08-11)

**Re-checked after the user restarted the session specifically to make Apify
reachable. It is still not reachable.** Verified independently, not assumed:
`ToolSearch` for apify/actor/scraper tools — nothing; `ListMcpResourcesTool` — only
Notion resources; `env | grep -i apify` — nothing; `apify` CLI not on PATH;
`apify_client` Python package not installed; `~/.claude.json` `mcpServers` — empty
list; no apify config anywhere under the home directory.

**The restart did deliver something** — the `claude-in-chrome` browser tools appeared
in this session's deferred-tool list, which weren't there before. So the restart
worked; it just didn't bring Apify. That distinction matters and is exactly the
refined lesson already recorded in memory from Track D's parallel experience:
**don't treat a bundle of "X and Y are now unblocked" as one status to accept or
reject together — verify each claimed unblock independently, since they resolve on
different timelines even when reported together.**

Not pursued further: creating an Apify account/token myself was never the
instruction (which assumed one already existed here) and isn't authorized. Comment
coverage this round therefore continued on the existing OpenCLI/browser-extract path.
**This turned out not to block the round's actual goal** — see Section 9; the volume
gap was closed by the post-cap fix, not by better comment extraction. Apify would
still help with the separate, still-unsolved high-engagement-post truncation cap.

## 1. What's actually installed on this machine

- `pipx` + `agent-reach` v1.5.0 + `yt-dlp` (YouTube supplementary path — transcripts,
  scraped comments, thumbnails; separate from the official YouTube Data API).
- OpenCLI native-messaging host, via `agent-reach install --system --channels opencli`.
- **Real Google Chrome**, installed and logged into Instagram + Reddit, with the OpenCLI
  extension enabled — this is the browser that actually works (see Section 2).

**Re-verified fresh 2026-08-09 (Weeks 5-6 session, not just re-reading this doc):**
re-ran `opencli doctor`, a real `opencli reddit subreddit-info nba` call (subscriber
count differed from the last read — confirms live, not cached), a real
`opencli instagram profile nasa` call (follower count also differed), and a real
YouTube Data API call with the stored key. All still genuinely working — not assumed.

## 2. Both platform blockers are now closed — all three platforms verified working end-to-end

| Platform | Status | Evidence |
|---|---|---|
| YouTube | ✅ working, both paths | yt-dlp confirmed via pilot (Section 4a). **Official Data API also confirmed working** — real `search.list` call against `googleapis.com` returned live results using the key now in `.env`. |
| Instagram | ✅ working | Real `opencli instagram profile` / `opencli instagram user` calls returned live data (Section 4b) — **but see the comment-text gap below, it's a real limitation, not just a speed number.** |
| Reddit | ✅ working | Real `opencli reddit subreddit-info` / `subreddit` / `read` calls returned live data (Section 4b), including real comment threads. |

### Browser choice matters — Arc did not work, Chrome does

First attempt used Arc Browser (Chromium-based, supports the Chrome extension format).
The OpenCLI extension registered successfully in Arc (`opencli doctor` showed
"Extension: connected") but **every actual command timed out with zero response**,
reproducibly, across multiple retries. agent-reach's docs specify Chrome specifically,
not "any Chromium browser" — Arc's tab-suspension behavior and Spaces model are the
likely cause, though the exact mechanism wasn't root-caused since switching to real
Chrome resolved it immediately (`opencli doctor` connectivity test: 0.3s, real commands
work). **Use Chrome for this project, not Arc, if OpenCLI setup is ever redone.**

### A leftover gotcha: multiple connected browser profiles

Arc's old Browser Bridge connection stayed live even after switching to Chrome (both
show "connected" in `opencli doctor`), which makes every OpenCLI command ambiguous and
fail with `Multiple Browser Bridge profiles are connected` unless a profile is pinned.
Fixed by setting `OPENCLI_PROFILE=s8h98tr4` (Chrome's profile ID) in `.env` — the
orchestrator and any manual `opencli` calls need this env var set, or pass
`--profile s8h98tr4` explicitly (as a *global* flag, before the subcommand — passing it
after the subcommand fails with `unknown option`).

## 3. YouTube Data API key type

User asked which Google Cloud credential type to create: **public data → API key**
(not the OAuth "user data" option) is correct — everything scraped here (channel
stats, video metadata, public comments) is public content, never tied to acting on
behalf of a specific signed-in Google user. Key received and verified working
2026-08-09, stored in `.env`.

## 4. Real pilot results (2026-08-09) — replacing the Weeks 1-2 estimate with measurements

### 4a. YouTube (yt-dlp)

| Call type | Real latency | Real yield |
|---|---|---|
| Channel video listing (flat, 20 videos) | 1.2-2.7s | 20 basic-metadata rows |
| Full single-video metadata | ~2.0s | 1 row: views/likes/duration/thumbnail/tags/upload date |
| Comment pull, team/brand channel (Lakers, 1M-view video) | 5.7s | 56 comments (only 18 on a lower-view video, same channel) |
| Comment pull, personal-influencer channel (277K-view video) | 8.5s | ≥100 comments (hit the request cap) |

Comment yield varies ~10x by creator type (team/brand accounts get disproportionately
few comments relative to views) — PROJECT_PLAN.md's scope includes both types, so
calls/entity should be budgeted per-category, not as one flat number.

### 4b. Instagram + Reddit (OpenCLI + Chrome) — first real numbers, not estimates

Pilot targets: `r/lebron` (niche fan subreddit, 20K subscribers) and `@kingjames`
(LeBron James's real Instagram — chosen to match PROJECT_PLAN's own worked example).

| Platform | Call | Real latency | Real yield |
|---|---|---|---|
| Reddit | `subreddit-info` (profile-equivalent) | 8.6s | 1 profile row |
| Reddit | `subreddit` (hot listing) | 5.7s | ~15 posts w/ metrics |
| Reddit | `read` (post + comments, bundled in one call) | 5.5s | 1 post + up to ~68 comments (truncated — "[+124 more top-level comments]" on a 338-comment post; full retrieval needs pagination) |
| Instagram | `profile` | 5.1s | 1 profile row |
| Instagram | `user` (recent posts) | 8.4s | 12 posts w/ captions + like/comment **counts** |

**Measured average across 5 real calls: 6.68s/call** (range 5.1-8.6s) — this is real
OpenCLI-via-Chrome-automation latency, not the ~2-3s/call figure the Weeks 1-2 estimate
borrowed from Xiaohongshu's documented limit (see prior adversarial self-check —
that figure was never actually confirmed for Instagram/Reddit, and now there's a real
number instead of an analogy).

**Naive back-to-back ceiling: 60/6.68 ≈ 9 calls/min ≈ ~540 calls/hour.** That's with
*zero* safety margin — every pilot call above had a 3s gap deliberately inserted before
it (ban-risk caution on freshly-created accounts), which if kept as standing practice
puts sustained throughput closer to **~370 calls/hour**. Both numbers are lower than
the Weeks 1-2 doc's "~600-700/hour" — that figure turns out to have been roughly in the
right neighborhood by coincidence (it was derived by halving a wrong theoretical
ceiling), not because the reasoning behind it was sound.

**Instagram comment-text gap — RESOLVED 2026-08-09.** There's no dedicated
`opencli instagram comments`-style command (confirmed via `--help`, `user` only
returns aggregate counts), but per your instruction, tried OpenCLI's generic browser
automation before reaching for Apify — and it works. `opencli browser <session>
extract` on an *opened post page* returns the rendered page as markdown, and
Instagram's comment section IS present in that render: author, comment text, like
count, and a permalink containing a real comment ID.

Pipeline, all real commands, all tested against live posts:
1. `opencli browser <s> open <profile_url>` → `find --css 'a[href*="/reel/"], a[href*="/p/"]'` to get real post URLs (the `user`/`profile` commands don't expose these — had to get them a different way).
2. `opencli browser <s> open <post_url>` → `extract` → markdown with comments embedded.
3. Parse with `scripts/ingestion/instagram_comment_extract.py::parse_comments()`.

Validated against 2 real posts (`/reel/` and `/p/` — different post types), 30 total
comments parsed correctly, including multi-paragraph text and heavy emoji use. Two
real regex bugs found and fixed during testing (markdown escapes underscores in
usernames like `kozmo\_spacely`; an over-restrictive end-of-string anchor) — first
draft parsed 0 comments despite the permalinks matching fine. **Apify wasn't needed —
this path worked on the first real attempt once the regex bugs were fixed.**

### Pagination-past-truncation gap — scoped and quantified 2026-08-09, not solved

Re-tested against a 3rd real post (`@cristiano` — Cristiano Ronaldo, chosen deliberately
as a worst-case: one of the highest-engagement accounts on the platform) to find out how
bad the initial-render truncation actually is. Parser worked correctly (no crash, no new
bugs), but only **9 comments** were extracted from a post with **352,130 total comments**
(per `opencli instagram user`'s comment-count field) — a **0.0026% coverage ratio**.

Tried to actually fix this, not just note it: searched the page for a "load more
comments" control (`browser find --text`/`--role`) — none found; tried scrolling
further — no additional comments appeared after 2 extra scrolls; inspected
`browser network` capture for a comments-pagination API call to potentially replicate
directly — nothing usable surfaced in the capture without deeper reverse-engineering of
Instagram's private GraphQL endpoints. **Deliberately stopped there** — calling a
private API directly outside the browser-automation path is a materially different (and
higher ban-risk) approach than everything else in this pipeline, and the team already
treats ban risk as a hard constraint (see the throughput/session-ceiling decision). Not
worth it for comment pagination specifically without your sign-off.

**Scoped, not solved:** this method captures Instagram's algorithmically-surfaced "top
comments" from the initial page render only, full stop. Coverage ratio is
worst-case-negligible for mega-celebrity posts (Ronaldo: 0.0026%) but PROJECT_PLAN.md's
actual target entities are 5k-follower-and-up creators, not global icons with 650M
followers — a realistically-scoped entity's posts will have far fewer total comments
(dozens to low thousands, not hundreds of thousands), so the *same* ~9-15
comments-per-post ceiling should cover a much larger fraction there. That's a reasoned
hypothesis, not yet measured — haven't tested a genuinely mid-tier (5k-500k follower)
account's coverage ratio specifically; `@kingjames` (LeBron, still a global mega-star)
gave ~15/1802 ≈ 0.8% earlier, so even a "normal" superstar is low. **Recommend
validating coverage ratio against 2-3 real mid-tier target entities before the Weeks
5-6 bulk run, so the team knows the actual signal density going in, not an
extrapolation from two extreme examples.**

### 4c. Re-estimating reachable entities with real numbers (both platforms have real
yield-per-call data now, but they're structurally different, so one flat number
across both isn't honest)

- **Reddit**: efficient — comments bundle into the same `read` call as the post. For a
  moderately-active community like r/lebron (comparable to a mid-tier fitness/lifestyle
  subreddit): ~1 listing call + ~15 `read` calls ≈ 16 calls yielded roughly 15 posts +
  hundreds of comments (real range seen: 18-338 comments/post before truncation) —
  plausibly reaches the 1,000-datapoint floor in the 20-30 call range for an
  entity/community with this level of activity. Lower-activity subreddits would need
  more calls per datapoint, same caveat as YouTube's team-account finding.
- **Instagram**: now that the comment-extraction pipeline exists (see above), the
  per-post cost changed shape: `user` listing (1 call → 12 posts) + `browser open` +
  `browser extract` per post of interest (2 calls → up to ~15 comments/post from the
  first pilot posts, real range seen 15/post so far) — i.e. ~3 calls to get 1 post +
  ~15 comments ≈ 16 datapoints, comparable in shape to Reddit's efficiency now, not the
  80+-calls/entity worst case from before this was resolved. Still needs a real
  multi-entity pilot to confirm this holds beyond the 2 posts tested.
- At ~370-540 calls/hour (Section 4b) and an 8-12hr/day operating window (Chrome must
  stay open — true for both platforms), **both Reddit and Instagram now look
  plausibly capable of reaching the 1,000-datapoint floor per entity without needing an
  order-of-magnitude more calls than Reddit** — a meaningful improvement over the
  pre-comment-extraction estimate. Still order-of-magnitude and still not load-tested
  across many entities, but the earlier concern that Instagram would structurally fall
  short is no longer the leading risk.

## 5. Real bulk collection — Weeks 5-6, first live run (2026-08-09)

`scripts/ingestion/orchestrator.py` is no longer a skeleton — it wrote real rows to
the production Supabase DB. Getting there surfaced 7 real bugs (data corruption from a
missing unique constraint, subprocess/encoding issues, wrong assumed YAML shapes,
inconsistent lazy-load timing, an undocumented missing comment-ID field, no
follower-floor check) — full list with fixes in `ORCHESTRATION.md`. None of these were
visible from the Weeks 3-4 pilot testing (single ad-hoc commands, not a real pipeline
run) — worth remembering that a working manual command and a working automated
pipeline calling the same command are not the same claim.

**Real row counts after this run:**

| Table | Rows |
|---|---|
| creators | 3 |
| youtube_channels / videos / comments | 1 / 10 / 200 |
| instagram_profiles / posts / comments | 59 / 5 / 71 |
| reddit_profiles / posts / comments | 113 / 6 / 135 |
| brands | 0 |

**Brand extraction: 0 real hits so far, and that's a real (if inconclusive) finding,
not a bug.** Tried 3 real entities (`athleanx`'s YouTube descriptions, `kingjames`'s
Instagram captions, `r/lebron`'s posts) — none matched the explicit disclosure
phrasing (`sponsored by`, `in partnership with`, `#ad`) the extractor looks for.
Checked real description text directly: `athleanx`'s videos link to the creator's own
product (self-promotion, not third-party sponsorship) — a legitimately negative case,
not a miss. The extraction module itself is unit-tested correct (see `SCHEMA.md`'s
adversarial self-check). **Not yet proven against a real positive case** — should
deliberately find a known-sponsored post (verified via `opencli instagram search`
first, not guessed from training knowledge — see the handle-guessing lesson below)
before trusting the brands pipeline end-to-end, not just the regex in isolation.

**Real lesson: don't guess handles from training knowledge.** Tried `whitneysimmons`
expecting the well-known fitness influencer; got a real but unrelated 460-follower
personal account instead (below PROJECT_PLAN.md's 5k-follower floor). Cleaned up
manually. The orchestrator has no handle-verification or follower-floor check yet —
real open item, not fixed here (`ORCHESTRATION.md` "What's NOT built yet").

## 6. Throughput / session ceiling — still true, now with real numbers behind it

**The bottleneck is the logged-in session, not the number of sub-agents** — unchanged
from Weeks 1-2, now confirmed: `OPENCLI_PROFILE` pins to one Chrome profile, and every
call funnels through that one browser instance regardless of how many callers there are.

**Decision unchanged: one shared Chrome session per platform, not multiple accounts.**
Real accounts now exist and are logged in — reinforces, not changes, the original
reasoning (see prior memory) not to add more accounts unless the Week 4 checkpoint
shows a material shortfall.

**YouTube remains not session-bottlenecked** — official Data API confirmed working,
quota-based (10k units/day default), independently re-verified via web search in the
last self-check.

## 7. Open items going into Weeks 7-8

- [x] ~~OpenCLI Chrome extension + IG/Reddit logins~~ — done 2026-08-09 (real Chrome,
  not Arc — see Section 2).
- [x] ~~YouTube Data API key~~ — received and verified working 2026-08-09.
- [x] ~~Pilot batch~~ — done for all three platforms (Section 4).
- [x] ~~Instagram comment-text gap~~ — resolved via `opencli browser extract` +
  `scripts/ingestion/instagram_comment_extract.py` (Section 4b).
- [x] ~~Wire the orchestrator~~ — done and run for real (Section 5).
- [x] ~~Prove the brands pipeline against a real positive case~~ — done 2026-08-10,
  see Section 8 (Virat Kohli / Agilitas).
- [ ] Follower-floor enforcement + handle verification before ingestion — still open.
- [ ] Pagination past truncation (Reddit `read`'s ~68-90 comment cap, Instagram
  `browser extract`'s initial-render cap) — scoped, not solved.
- [ ] Decide whether Reddit runs via OpenCLI (desktop, Chrome must stay open) or
  `rdt-cli` (headless, cookie-based, unattended) — OpenCLI is now proven to work, so
  this is a convenience/uptime tradeoff, not a functionality question anymore.
- [ ] Real load test — Section 8's run got up to ~35 min continuous for Reddit before
  finishing; still short of true sustained/multi-hour operation. CAPTCHA/ban
  thresholds still unknown in practice.
- [ ] **Raise the hardcoded 5-post-per-creator cap** (`orchestrator.py`, both
  `InstagramWorker` and `RedditWorker`) — see Section 8, this is the real lever for
  closing the 1,000-datapoints/entity gap, not more accounts.

## 8. Weeks 7-8 real bulk run (2026-08-10) — volume-vs-floor, honestly

Dispatched 3 model:sonnet sub-agents (one per platform, per this week's orchestrator
architecture) against the curated target list (`target_list.json`). All three
genuinely completed (see `ORCHESTRATION.md` for the real bugs found running them).

### Real per-creator datapoint totals (posts + comments, all platforms)

| Creator | YT posts/comments | IG posts/comments | Reddit posts/comments | **Total** |
|---|---|---|---|---|
| LeBron James | 0/0 | 6/122 | 6/158 | **292** |
| Sania Mirza | 0/0 | 5/70 | 5/184 | **264** |
| Virat Kohli | 0/0 | 5/149 | 5/63 | **222** |
| MC Mary Kom | 0/0 | 5/97 | 5/140 | **247** |
| Ranveer Allahbadia | 10/50 | 5/130 | 0/0 | **195** |
| Cristiano Ronaldo | 0/0 | 0/0 (failed, see below) | 5/201 | **206** |
| PV Sindhu | 0/0 | 5/67 | 5/59 | **136** |
| Neeraj Chopra | 0/0 | 5/71 | 5/43 | **124** |
| Saina Nehwal | 0/0 | 5/33 | 5/59 (via junction table fix) | **102** |

**Honest assessment: every real creator is well below the 1,000-datapoint floor —
highest is LeBron at 292 (~29%), lowest is Saina Nehwal at 102 (~10%).**

**But this is NOT primarily a session/throughput-ceiling problem.** Checked directly:
both `InstagramWorker` and `RedditWorker` hardcode `posts[:5]` / `post_paths[:5]` —
this pilot run only ever fetched 5 posts/platform/creator by design, not because the
account/session ceiling was hit. Real call volume this run was well within the
~370-540 calls/hour sustained figure from the Weeks 5-6 pilot, and none of the
sessions ran anywhere near continuously for an hour. **The real lever for closing this
gap is raising the per-creator post-fetch cap, not the multi-account fallback held in
reserve since Weeks 1-2.** Recommend trying that first (a config change, zero new
account/ban risk) before considering multi-account, which the original plan explicitly
gated on user sign-off. Not raised in this session — flagging for a decision, not
deciding unilaterally to change scraping volume this far into the run.

### Real bugs found running the actual bulk collection

1. **Reddit shared-subreddit data loss (serious, fixed):** `reddit_posts.creator_id`
   is single-valued, but `creators.reddit_handles` is often a generic subreddit
   (r/badminton) shared by multiple creators. PV Sindhu and Saina Nehwal both map to
   r/badminton; since `post_id` is a global PK, Sindhu's worker won the upsert and
   Saina Nehwal got **zero** reddit posts credited — not duplicates, actual silent
   data loss. Fixed with a `reddit_post_creators` many-to-many junction table,
   backfilled from existing data and wired into the orchestrator going forward. See
   `ORCHESTRATION.md`.
2. **Instagram `selector_not_found` at broader scale than previously seen:** 5 of 9
   creators failed with the same error this run (neeraj____chopra, pvsindhu1,
   mirzasaniar, kingjames, cristiano) — worse than the earlier single-creator
   (cristiano-only) flakiness from Weeks 5-6. Sustained-load reliability degrading
   over a long run is a real, still-open concern (see open items).
3. Two of the sub-agents' own process-exit monitors were themselves buggy (a
   PowerShell profile banner made a `grep -q .` liveness check always true) — caught
   and self-corrected by the Reddit sub-agent mid-run, not something I had to fix.

### Cross-track note
Confirmed via read-only queries: no evidence of Instagram/Reddit data
cross-contaminating each other despite both routing through the same underlying
OpenCLI/Chrome daemon (a risk flagged before dispatching sub-agents) — row ownership
by platform/creator checked out cleanly.

## 9. Weeks 9-10 — VOLUME round (2026-08-11). Cap raised 5 -> 40, NOT freezing v1.

PROJECT_PLAN.md's Week 9-10 row says "freeze v1 dataset". **Deliberately not doing
that this round** — at 10-29% of the 1,000-datapoint floor, freezing would lock in a
dataset too thin for real GAIL training. Volume first; freeze once the floor is
actually reachable.

### The fix: post cap was the whole problem, exactly as diagnosed

Raised `DEFAULT_POST_CAP` 5 -> 40 (user sign-off), now configurable via `--post-cap`.
Added a rolling recency window (`--recency-days`, default 183 ≈ 6 months) so the extra
budget pulls *more recent* posts instead of padding with stale ones — the original
doc's "last 6 months" treated as rolling relative to today rather than its literal
Jan-Jun 2026 dates, per its own stated principle "the newer the data the better".

Per-platform specifics:
- **YouTube**: filters on `publishedAt`; also raised `commentThreads` `maxResults`
  20 -> 100. That's a 5x comment-yield increase for **zero** extra quota cost, since
  `commentThreads.list` costs 1 unit regardless of page size.
- **Instagram**: filters on the listing date; the grid scrape now scrolls until it has
  `post_cap` links instead of taking the first screenful (~8-12 links), with a
  stall-detector so a profile with fewer posts doesn't loop forever.
- **Reddit**: switched to `--sort new`. With a recency window in play, the default
  `hot` surfaces high-scoring posts of *any* age which the filter then discards — new
  makes the cap and the window pull in the same direction.

### Adversarial self-check — the filter genuinely applies, verified 3 ways

Not assumed from "0 skipped" on the first run (which is ambiguous — could equally mean
a broken filter):
1. **Deliberate tight-window test**: same creator (BeerBiceps), `--recency-days 14` —
   skipped 10 of 40 videos. A no-op filter would have skipped 0.
2. **Real-data variation**: across the full run, per-creator skips varied exactly as
   the creators' real posting histories predict — Neeraj Chopra kept only 11 of 40
   (posts infrequently), Cristiano 17, while BeerBiceps/Sania kept all 40 (post daily).
3. **Independent DB check**: `select count(*) from youtube_videos where published_at <
   '2026-02-07'` -> **0**.

Also found and fixed a real reporting bug while reading the run output: `skipped_stale`
was an instance counter never reset between creators, so the per-creator log line was
printing a running batch total ("29 skipped" for creators that skipped nothing).

### Real YouTube yield (before -> after)

| | Before (cap 5) | After (cap 40) |
|---|---|---|
| Channels | 2 | 5 |
| Videos | 20 | **119** |
| Comments | 250 | **2,746** |

Per-creator: Cristiano Ronaldo 17 videos/1,616 comments (**1,633 datapoints — over the
1,000 floor from YouTube alone**), Ranveer Allahbadia 41/461, Sania Mirza 40/258,
Neeraj Chopra 11/211. Yield scaled better than linearly with the cap because the
comment-page increase compounds with it.

### YouTube handle coverage: 1/9 -> 4/9, and an honest limit

Verified every candidate against the real API rather than guessing — **4 of 5 guessed
handles resolved to unrelated or fan channels** (same failure mode as the
`whitneysimmons` and `neeraj_chopra1` incidents in prior rounds; the pattern is now
thoroughly established: never trust a handle from training knowledge).

Added: Neeraj Chopra `@neerajchopra1` (274K subs; corroborated by a management contact
email matching the one in his already-verified Instagram bio), Sania Mirza
`@servingitupwithsania` (68K, her real show channel), Cristiano Ronaldo `@cristiano`
(82.9M).

**Not added, and this is a real finding rather than a search failure:** Virat Kohli,
PV Sindhu, Saina Nehwal, and LeBron James genuinely appear to have **no official
personal YouTube channel** — searches surface only fan channels (15-20K subs, a
handful of videos) and, for LeBron, org channels (his foundation, his podcast) rather
than a personal one. Indian cricket/badminton stars are Instagram-first; their YouTube
presence lives on broadcaster channels (BCCI, Star Sports) that aren't creator-owned
and would misattribute engagement. MC Mary Kom had a plausible `@marykomofficial`
(5,020 subs) but with zero corroborating evidence, so it was **left out rather than
guessed at** — the cost of a wrong handle (polluting a real creator's data with a
stranger's) is much higher than the cost of a missing one.
