# Track D (Frontend+App) — Handoff

Last updated: 2026-08-10, end of Weeks 11-13 round. Written for a fresh
session with no memory of prior conversations — start here before reading
anything else, including your own memory files (which are scattered across
many small entries and easy to piece together wrong).

Worktree: `D:\Capstone-worktrees\track-d-frontend-app`, branch
`track-d-frontend-app`, off `github.com/akshatnavlani/Capstone`. Frontend
code lives in `frontend/` (not repo root). `WIREFRAMES.md` at repo root is
the living wireframe/API-contract doc — read it alongside this file, don't
duplicate it here.

## Current state (one paragraph)

Next.js 16 + TypeScript + Tailwind v4 app with 5 routes (`/`, `/brand-input`,
`/dashboard`, `/monitoring`, `/explainability`), all wired to Track C's real
backend API (no mock data in the frontend code itself — `is_mock_data` is a
real field Track C returns and the UI surfaces it honestly). Docker
build/run is fully verified for real (not just `next build` succeeding —
actual `docker build` + `docker run` + curl against all 5 routes, 200s with
real content). The full brand-input → dashboard → explainability →
monitoring flow has been real-browser-tested twice against the live
Supabase DB (once against athlete creators, once against a diversified set
including content creators with different data-completeness shapes), with
zero console errors both times. Monitoring resolves creator names
client-side with a graceful fallback for orphaned references. What's *not*
built: the explainability network-graph/causal-insights view is still an
explicit, honest placeholder — correctly so, see open items below, not an
oversight.

## Open items

- **Explainability network-graph view — not started, blocked on real graph
  edge data.** Two edge types matter: `collaborates_with`
  (`frequent_collaborator` relations) has **no producer at all** anywhere
  in Track A's pipeline — not just empty, structurally not built.
  `co_occurs_with` (via Track A's `reddit_post_creators`) has real
  *infrastructure* and was briefly populated, but as of the last check is
  back to zero — a side effect of Track A's own necessary Reddit
  relevance-gating fix (it correctly purged the noisy shared-subreddit
  links that co-occurrence depended on). **Re-verify this fresh every
  round** — it has already flipped from real-and-populated to empty once
  within a single round; do not trust a prior round's "it's real now"
  claim without re-querying the live DB.
- **Kohli/Agilitas sponsorship labeling — blocked, needs Track A to
  actually re-run collection.** Track A's caption-truncation fix is
  shipped in their scraper code, but as of the last direct DB check the
  stored row is still exactly 100 characters (the fix hasn't been
  re-applied to already-collected data). No frontend action needed either
  way — `is_sponsored` isn't part of `InfluencerRecommendation`, this only
  matters for the network-graph sponsorship edges above.
- **`product_category`/`platform_preference` filtering — not started,
  Track C's stated open item, not frontend's.** No action needed from this
  track; just don't assume it's implemented when testing.
- **Real Fusion Layer scores — blocked on Track B/C.** Every real creator
  currently gets a flat placeholder `spillover=sentiment_risk=
  creator_feature=0.5` (`final_score=50`) because the GAIL/Temporal
  branches aren't trained yet. Dashboard/explainability already label this
  correctly as placeholder/mock data — no frontend change needed until
  Track B/C wire real scoring (weeks 11-13+ per timeline, still pending as
  of last check).

## Non-obvious lessons (the kind you can't get from reading the code)

1. **"Tool X is now enabled/available" is a claim about the user's/other
   session's actions, not a guarantee this session picked it up — always
   verify directly, and if it's genuinely not reachable, a session
   restart (not a workaround) is usually what actually fixes it.** This
   happened twice for this track alone (Docker Desktop, the
   `claude-in-chrome` browser tool) — both were confirmed unreachable via
   direct checks (`docker --version`, process list, `Skill`/`ToolSearch`)
   across multiple sessions until an actual restart, at which point they
   worked immediately. Don't spend time on workarounds when the fix is
   "ask the user to restart."
2. **`curl`-based "verified end-to-end" is not real verification for
   anything user-facing.** `curl` doesn't enforce CORS, cookie
   `SameSite`, or other real-browser security behavior. This exact gap
   caused an *8-week*, project-wide blind spot: Track C's backend had zero
   CORS middleware from Weeks 1-2 onward, and every track's curl-based
   "it works" checks were structurally incapable of catching it. It only
   surfaced the first time this track got a real browser tool working and
   tried the actual flow. Lesson generalizes: use the real browser for
   anything user-facing, reserve curl strictly for backend-only sanity
   checks (row counts, endpoint shapes, preflight headers as a
   *secondary* confirmation after a real browser check, not instead of
   one).
3. **Track C's API contract has broken more than once *on the same day*
   — always re-fetch fresh (`git show origin/track-c-fusion-backend:
   backend/app/schemas.py`) rather than trusting even a same-session
   reconciliation table.** Re-diff field-by-field before touching any
   frontend code that consumes the API, every single round, no exceptions.
4. **Real infrastructure existing (an endpoint, a schema field) is not
   the same as real data existing behind it — check row counts on the
   live DB, don't infer from the endpoint's presence or a prior round's
   memory note.** The `co_occurs_with` endpoint is real and correctly
   built, and was genuinely populated for one round, then genuinely empty
   the next, because of an upstream data-quality fix elsewhere in the
   pipeline. Treat "is there real data right now" as a question to
   re-answer every round, not a fact that persists once true.
5. **Verifying code works is not the same as it being safe — always
   explicitly decide whether to commit, don't let a clean `git status`
   (no stray files) stand in for "committed and pushed."** This is the
   lesson that prompted writing this handoff doc in the first place: real,
   browser-verified, working code (the monitoring creator-name-resolution
   feature) sat uncommitted in this worktree for two full rounds because
   no one — including this agent — ever explicitly asked "should this be
   committed?" A `git status` check that shows only your own intentional
   edits is not the same claim as "this is safely persisted." **Before
   ending any round from now on: run `git status`, and if anything is
   uncommitted, make an explicit, stated decision (commit + push it, or
   explain plainly why not) rather than leaving it ambiguous.**
6. **When real Supabase DB access is needed, ask the user for the
   connection string fresh each time — it is never persisted.** Write it
   only to `backend/.env` in Track C's worktree (already gitignored,
   confirmed before writing), never to memory or any tracked file, and
   delete it the moment the check is done. This has been asked for and
   handled this way multiple times already; it's the expected pattern, not
   something to second-guess.

## Exact next steps for the next round

1. **Run `git status` first, before anything else** — confirm clean, or
   resolve explicitly per lesson #5 above.
2. Re-fetch Track B and Track C's branches fresh (`git fetch origin` +
   `git log`/`git show`, not memory) and check: has real GAIL training
   started, do real collaboration/co-occurrence edges exist now, has the
   Kohli/Agilitas post been re-labeled. If yes to any of the graph-edge
   questions, re-verify by querying the live DB directly (ask the user for
   the connection string) before deciding whether the explainability
   network-graph view is now honestly buildable — don't build it on faith
   that a memory note from another track is still current.
3. Check whether Track A's target list has grown further or added new
   creator "shapes" (different platforms, different completeness
   patterns) — if so, re-run the real browser click-through against it,
   watching specifically for field combinations not yet seen (the pattern
   so far: every new creator batch has surfaced at least one genuinely new
   null/empty-field combination worth confirming the UI handles).
4. If nothing above has moved, this track is genuinely light on
   non-data-dependent work right now — check with the user before
   inventing scope (per this track's own project-wide risk note: don't
   manufacture busywork to look thorough).
