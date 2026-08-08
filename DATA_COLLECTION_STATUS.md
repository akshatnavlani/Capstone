# Data Collection Status — Track A (Data/Infra)

Last updated: 2026-08-08. This is the real, verified state of the scraping backend on
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

| Platform | Status | Detail |
|---|---|---|
| YouTube | ✅ ok | yt-dlp working (supplementary). **Primary path is the official YouTube Data API, which is separate and needs a Google Cloud API key — not yet provisioned, see Section 3.** |
| Instagram | ❌ off | No backend active. Needs OpenCLI Chrome extension + logged-in instagram.com session. |
| Reddit | ❌ off | No backend active. No zero-config path exists for Reddit at all (anonymous `.json` endpoints are blocked platform-wide; official API needs manual approval agent-reach says is largely not being granted currently). Needs OpenCLI + logged-in reddit.com session, **or** `rdt-cli` with a manually-provided session cookie for headless/server use. |

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

### Instagram / Reddit throughput estimate (order-of-magnitude — validate empirically)

- Session rate ceiling: ~2-3s/call → ~20-24 calls/min theoretical max.
- Recommended sustained rate: ~half of theoretical (leaves room for retries/backoff,
  reduces ban/CAPTCHA risk) → **~10-12 calls/min, ~600-700 calls/hour sustained.**
- Calls needed per entity to reach the ~1,000 combined-datapoints floor (posts +
  comments + metrics): rough estimate **30-50 calls/entity** — 1 profile call + ~15-20
  post-listing calls + comment-fetch calls on the most-engaged posts. This varies a lot
  by how popular the account is (a viral post can supply hundreds of comments in one
  call; a niche account needs many more calls to accumulate the same count) — **treat
  this number as unvalidated until we run a real pilot batch in Week 3.**
- At ~40 calls/entity average and 600 calls/hour: **~15 entities/hour/platform.**
- Operating window: OpenCLI needs Chrome open, so realistically an 8-12hr/day window on
  a desktop machine (not true 24/7) unless we switch Reddit to the headless `rdt-cli`
  backend with a manually-stored session cookie, which *can* run unattended overnight.
- **Weeks 3-4 (14-day) estimate: roughly 1,500-2,500 reachable entities per platform**
  (Instagram, Reddit), at 8-12hr/day sustained scraping under the single-session ceiling.

**This is a planning estimate, not a promise.** First real scraping day in Week 3
should be treated as a calibration run — measure actual calls/entity and actual
sustainable rate before CAPTCHA/rate-limit pushback, then recompute this range and
update this file.

## 5. Open items going into Weeks 3-4

- [ ] User completes OpenCLI Chrome extension install + IG/Reddit logins (Section 3)
- [ ] User provisions YouTube Data API key (Section 3)
- [ ] Pilot scraping batch to calibrate the throughput estimate in Section 4
- [ ] Decide whether Reddit runs via OpenCLI (desktop, Chrome must stay open) or
  `rdt-cli` (headless, cookie-based, can run unattended) once we know the operating
  pattern for Weeks 3-4
