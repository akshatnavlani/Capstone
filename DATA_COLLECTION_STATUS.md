# Data Collection Status — Track A (Data/Infra)

Last updated: 2026-08-09. This is the real, verified state of the scraping backend on
this machine — not a plan. Re-run `agent-reach doctor --json` before trusting this if
it's more than a couple weeks old.

## 1. What's actually installed on this machine (this session)

- Installed `pipx`, then `agent-reach` v1.5.0 via pipx (from
  `github.com/Panniantong/agent-reach`).
- Installed `yt-dlp` (supplementary YouTube scraping: transcripts, best-effort scraped
  comments, thumbnails — separate from the official YouTube Data API).
- Configured yt-dlp's JS runtime (`--js-runtimes node`) so it actually works.
- Ran `agent-reach install --system --channels opencli` — installs the local OpenCLI
  native-messaging host. **The Chrome extension itself still needs manual install by a
  human** (Chrome Web Store install can't be scripted) — see Section 3.

## 2. Real `agent-reach doctor --json` results (relevant platforms only)

Re-run 2026-08-09 as part of an adversarial self-check on the Weeks 1-2 work —
**identical to the 2026-08-08 results, no drift, but also no progress**: both
blockers below are still open.

| Platform | Status | Detail |
|---|---|---|
| YouTube | ✅ ok | yt-dlp working (supplementary, confirmed with a real pilot batch — Section 4a). **Primary path is the official YouTube Data API, which is separate and needs a Google Cloud API key — still not provisioned as of 2026-08-09, see Section 3.** |
| Instagram | ⚠️ warn | OpenCLI installed but "未检测到已连接的浏览器扩展" (no connected browser extension detected) — still blocked on the manual Chrome extension step. |
| Reddit | ⚠️ warn | Same as Instagram — OpenCLI installed, extension not connected. |

Facebook/Twitter/etc. are out of scope per PROJECT_PLAN.md and not evaluated.

## 3. What I need from you to unblock Instagram + Reddit + YouTube API

1. **Chrome extension (unblocks both Instagram and Reddit via OpenCLI):**
   - Open `https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk`
   - Click "Add to Chrome"
   - Log into `instagram.com` and `reddit.com` normally in that same Chrome browser
     (whatever account you're comfortable using for this — see Section 4 on account
     strategy before deciding whose account)
   - Tell me when done and I'll re-run `agent-reach doctor --json` / `opencli doctor`
     to confirm it's live.
2. **YouTube Data API key** (this is the *primary* YouTube source per the plan, not
   yt-dlp): go to Google Cloud Console → create/select a project → enable "YouTube
   Data API v3" → Credentials → Create API key. Paste it to me and I'll put it in
   `.env` (never committed — `.env` is gitignored).

Everything else (installing the CLIs, config) is done; these two steps are the only
ones that require a human because they're either an interactive Chrome install/login
or a Google account action.

## 4. Throughput / session ceiling — read this before assuming any parallelism

**The bottleneck is the logged-in session, not the number of sub-agents.** OpenCLI
reuses one Chrome browser's login state — spinning up 5 sub-agents that all call
`opencli instagram ...` still funnels through that same one Instagram session. Calling
faster than the platform's per-session rate limit (~2-3s between calls) just increases
ban risk; it doesn't increase throughput. Same logic applies to Reddit.

**Decision: one shared session per platform (Instagram, Reddit), not multiple
accounts.** Reasoning:
- Running multiple accounts to parallelize means creating multiple real Instagram/Reddit
  accounts, which is more ToS-risk and more manual login/maintenance overhead than it's
  worth for a thesis-scale target.
- Treat this as the Week 1-2 decision; only revisit (and get explicit sign-off from you,
  since it means real new accounts) if the Week 4 checkpoint shows we're materially
  behind the 1,000-datapoints/entity floor.

**YouTube is NOT session-bottlenecked** — it uses the official Data API with a
10,000-units/day free quota (channel/video/comment list calls cost 1 unit each; search
costs 100 units — build the initial target list some other way and conserve quota for
list/comment calls, not search). At that quota, hundreds of channels/day is comfortable;
YouTube is not expected to be the constraint on influencer count.

### 4a. Real pilot batch — YouTube via yt-dlp (2026-08-09)

Instagram/Reddit are still blocked (Section 2), so a real session-throughput pilot for
those platforms literally cannot run yet — see 4b for what that means for the estimate.
What COULD run: real yt-dlp calls against two real channels representative of
PROJECT_PLAN.md's scope (a team/brand account and a personal fitness-influencer
account). Actual measurements, not projections:

| Call type | Real latency | Real yield |
|---|---|---|
| Channel video listing (flat, 20 videos) | 1.2-2.7s | 20 basic-metadata rows |
| Full single-video metadata | ~2.0s | 1 row: views/likes/duration/thumbnail/tags/upload date |
| Comment pull, team/brand channel (Lakers, 1M-view video) | 5.7s | **56 comments** (and only 18 on a lower-view video from the same channel) |
| Comment pull, personal-influencer channel (277K-view video) | 8.5s | **≥100 comments** (hit the request cap — more were available) |

**Real finding: comment yield per video varies by roughly an order of magnitude by
creator type**, not something the Weeks 1-2 estimate accounted for. A high-view
team/brand account can still return under 20 comments on a given video; a
lower-view personal-influencer account can blow past 100. Since PROJECT_PLAN.md's
scope explicitly includes both types (athletes/teams/leagues AND fitness/lifestyle
influencers), the original flat "30-50 calls/entity" assumption undersold how many
calls a low-comment-engagement entity (teams, leagues, brand-run accounts) will
actually need to hit the 1,000-datapoint floor — could be 2-5x higher for that
entity type. Raw pilot output kept in the session scratchpad, not committed (throwaway
verification data, not project data).

### 4b. Re-deriving the Instagram/Reddit estimate from scratch

Re-examined the ~2-3s/call figure the Weeks 1-2 estimate was built on: it is **not**
agent-reach's documented rate limit for Instagram or Reddit. Checked
`.agents/skills/agent-reach/references/social.md` directly — that exact figure
("每次操作间隔 2-3 秒") appears **only in the Xiaohongshu section**. Instagram's section
only says to back off *after* hitting a 429; Reddit's section states no rate-limit
number at all. The Weeks 1-2 doc presented an analogy from a different platform as if
it were a confirmed Instagram/Reddit number — that was an overstatement of confidence,
not a wrong number exactly (2-3s/call is still a reasonable prior for browser-session
scraping generally), but the evidentiary basis was weaker than stated.

**Net result of re-deriving both inputs:**
- The calls/hour ceiling (~600-700/hour) rests on an unconfirmed cross-platform
  analogy, not a documented Instagram/Reddit number.
- The calls/entity figure (30-50) is now shown by real YouTube evidence to likely be
  too low for team/brand-type entities specifically.
- Both effects push the same direction: **less confidence in the 1,500-2,500
  reachable-entities/platform figure than the Weeks 1-2 doc implied — if anything it's
  more likely to be an overestimate than an underestimate**, given calls/entity was
  probably undercounted for a whole entity category in scope. I'm not replacing it with
  a new number, because Instagram/Reddit remain genuinely untestable until unblocked —
  a substitute guess wouldn't be any more trustworthy than the one being corrected.
  **The only way to actually pin this down is the real pilot in Section 5, which is
  still blocked on Section 3.**

## 5. Open items going into Weeks 3-4

- [ ] **User: OpenCLI Chrome extension install + IG/Reddit logins (Section 3)** — asked
  again 2026-08-09, still the single blocker on getting ANY real Instagram/Reddit
  throughput data, not just an estimate refinement.
- [ ] **User: YouTube Data API key (Section 3)** — still not provided as of 2026-08-09;
  yt-dlp remains supplementary-only without it.
- [ ] Real Instagram/Reddit pilot batch — blocked on the item above, not yet possible.
- [ ] Decide whether Reddit runs via OpenCLI (desktop, Chrome must stay open) or
  `rdt-cli` (headless, cookie-based, can run unattended) once we know the operating
  pattern for Weeks 3-4.
- [x] ~~Pilot scraping batch to calibrate throughput~~ — done for YouTube (Section 4a);
  Instagram/Reddit still blocked.
