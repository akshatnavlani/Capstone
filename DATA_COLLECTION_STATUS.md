# Data Collection Status — Track A (Data/Infra)

Last updated: 2026-08-09. This is the real, verified state of the scraping backend on
this machine — not a plan. Re-run `agent-reach doctor --json` / `opencli doctor` before
trusting this if it's more than a couple weeks old.

## 1. What's actually installed on this machine

- `pipx` + `agent-reach` v1.5.0 + `yt-dlp` (YouTube supplementary path — transcripts,
  scraped comments, thumbnails; separate from the official YouTube Data API).
- OpenCLI native-messaging host, via `agent-reach install --system --channels opencli`.
- **Real Google Chrome**, installed and logged into Instagram + Reddit, with the OpenCLI
  extension enabled — this is the browser that actually works (see Section 2).

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

Caveats, real not hypothetical: this captures what's rendered on first page load, not
guaranteed complete — Instagram truncates long comment threads ("View all N replies",
"[+N more]") in the initial render, so very high-engagement posts will need pagination
(not built) to get everything. Not yet load-tested across many posts/rate-limit
behavior under this generic-browser-automation path specifically (may differ from the
dedicated `instagram user`/`profile` commands' rate characteristics — untested).

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

## 5. Throughput / session ceiling — still true, now with real numbers behind it

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

## 6. Open items going into Weeks 3-4

- [x] ~~OpenCLI Chrome extension + IG/Reddit logins~~ — done 2026-08-09 (real Chrome,
  not Arc — see Section 2).
- [x] ~~YouTube Data API key~~ — received and verified working 2026-08-09.
- [x] ~~Pilot batch~~ — done for all three platforms (Section 4).
- [x] ~~Instagram comment-text gap~~ — resolved via `opencli browser extract` +
  `scripts/ingestion/instagram_comment_extract.py` (Section 4b). Not yet: pagination
  past Instagram's initial-render truncation, and a real multi-entity load test.
- [ ] Wire the orchestrator's platform-call TODOs using the now-confirmed-working real
  commands, including the new Instagram comment-extraction pipeline (`ORCHESTRATION.md`).
- [ ] Decide whether Reddit runs via OpenCLI (desktop, Chrome must stay open) or
  `rdt-cli` (headless, cookie-based, unattended) — OpenCLI is now proven to work, so
  this is a convenience/uptime tradeoff, not a functionality question anymore.
