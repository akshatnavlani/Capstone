# AGENTS.md

## 0. Read first — every session

Read `CAPSTONE_NEXT_STEPS.md:1` top-to-bottom before proposing anything. It is the orchestrator's single source of truth for live DB state, ranked problems, phased plan, track ownership, and standing rules. It supersedes memory. Two habits go with it:
- **Re-verify before acting on a number** — data changes daily; see `CAPSTONE_NEXT_STEPS.md:259` for REST query pattern.
- **Update + commit + push it when something changes** — a stale plan is worse than none. Track sessions `git pull origin main` to see it.

`CLAUDE.md:1` holds the behavioral contract (think before coding, simplicity first, surgical changes, goal-driven execution). Honor it.

## 1. Repo layout — main is docs-only

```
D:\Capstone\                                  main  a4b3bed — docs + plans only
D:\Capstone-worktrees\track-a-data-infra\     track-a  8429d97
D:\Capstone-worktrees\track-b-ml-core\        track-b  69157df
D:\Capstone-worktrees\track-c-fusion-backend\ track-c  deaf630
D:\Capstone-worktrees\track-d-frontend-app\   track-d  eb8dc98 (12d behind main — rebase before work)
```

`main` has no `supabase/`, `scripts/`, `backend/`, `ml/`, or `frontend/`. All code lives in worktrees (each is a separate git branch + worktree). Check `git worktree list`. No `opencode.json` exists.

Untracked on `main`: `.obsidian/`, `kickbacks-v2.vsix`, `tools/sheet_review/sheet_review.py:1` — `.gitignore:1` only covers `.agents/` and `.claude/settings.local.json`.

## 2. Track ownership — don't blur

| Track | Owns | Entrypoints |
|-------|------|-------------|
| **A Data/Infra** | Scraping, DB population, raw `creator_related_accounts` facts | `track-a:scripts/ingestion/orchestrator.py:1` (1460 lines), `track-a:scripts/ingestion/pair_count.py:1` (canonical pair definition), `track-a:supabase/migrations/` (7 files) |
| **C Fusion+Backend** | Edge resolution, disclosure labeling, feature store, fusion, API | `track-c:backend/app/feature_store.py:1`, `track-c:backend/app/fusion.py:57`, `track-c:backend/app/routers/scores.py:1`, `track-c:API_CONTRACTS.md:1` |
| **B ML-Core** | Graph construction (PyG HeteroData), GAIL, bot detection, CLIP/BERT | `track-b:ml/schema.py:1`, `track-b:ml/gail_model.py:1`, `track-b:ml/training.py:1`, `track-b:GRAPH_SCHEMA.md:1`, `track-b:scripts/train_holdout_round3.py:1` |
| **D Frontend+App** | UI, explainability graph, Docker, browser verification | `track-d:frontend/src/app/` (5 routes), `track-d:frontend/src/lib/api.ts:1`, `track-d:WIREFRAMES.md:1`, `track-d:HANDOFF.md:1` |

Track A writes facts, C resolves them to edges, B builds tensors and trains, D visualizes. See `CAPSTONE_NEXT_STEPS.md:480`.

## 3. Live DB & env — verified source

- **Supabase** `https://fhbgbtxdtfluzohxyivg.supabase.co` — credentials in each worktree's gitignored `.env` (not on `main`). Password was pasted in chat 2026-08-11 — rotate before submission `CAPSTONE_NEXT_STEPS.md:920`.
- **Orchestrator has no `psycopg2`** — query via REST (`CAPSTONE_NEXT_STEPS.md:259`):
  ```powershell
  $K="sb_publishable_l-j6rKSWn4DuT2lCJHB1zA_8T1XbUvV"
  curl -s "https://fhbgbtxdtfluzohxyivg.supabase.co/rest/v1/creators?select=creator_id&limit=5" -H "apikey: $K"
  # count: -H "Prefer: count=exact" -H "Range: 0-0" -D - | grep content-range
  ```
  Read-only — never write from orchestrator.
- **Inside worktrees with `psycopg2`:** direct host `db.fhbgbtxdtfluzohxyivg.supabase.co` is **IPv6-only** — fails with `WinError 10051` if no IPv6 route. Use the pooler `CAPSTONE_NEXT_STEPS.md:440`:
  ```
  DATABASE_URL=postgresql://postgres.fhbgbtxdtfluzohxyivg:<pwd>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
  ```
- **Docker** at `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe` (non-standard path) `CAPSTONE_NEXT_STEPS.md:461`.

## 4. Constraints that silently fail

Full schema `CAPSTONE_NEXT_STEPS.md:359` / `track-a:SCHEMA.md:1`. The ones that hard-fail or silently drop rows:

- `creators.category` CHECK `athlete|team|league|fitness_influencer|lifestyle_influencer|other` — any other value hard-fails insert `CAPSTONE_NEXT_STEPS.md:366`.
- `creator_related_accounts.relation_type` must be exactly `"frequent_collaborator"` — C's resolver filters on that literal, else row is silently ignored `CAPSTONE_NEXT_STEPS.md:375`.
- Both endpoints of a `creator_related_accounts` row must already be `creators` — unresolvable rows are silently skipped until the co-author is promoted `CAPSTONE_NEXT_STEPS.md:377`.
- `instagram_profiles.creator_id` is nullable (holds comment authors too) — don't clobber `creator_id=null` rows `CAPSTONE_NEXT_STEPS.md:399`.
- `is_sponsored`/`sponsorship_raw_matches` = Track C writes; `is_bot_flagged`/`bot_score` = Track B writes `CAPSTONE_NEXT_STEPS.md:401`.
- `brands` populated only from disclosure extraction (`source='sponsorship_mention'`) — brand-discovery crawls must use a distinct `source` `CAPSTONE_NEXT_STEPS.md:386`.
- Google Sheet `1UX9K3gQnh4roMgTi0cy3Sxm82kTLDkZI9w4jJELFVPQ` — **never write `approval_status`** (user's column: `accepted`/`rejected`/blank) `CAPSTONE_NEXT_STEPS.md:417`. Promote is an upsert (sheet may have handles DB lacks) `CAPSTONE_NEXT_STEPS.md:424`. Bulk-promote only if handle appears in an unresolved `creator_related_accounts` row (targeted-promotion rule) `CAPSTONE_NEXT_STEPS.md:311`.

## 5. Commands — use the executable source

**Canonical pair count** (sole definition — don't hand-roll):
```powershell
python D:\Capstone-worktrees\track-a-data-infra\scripts\ingestion\pair_count.py
# imported by loop_stats.py; prints 4 readings: event-neighbor rows / directed / undirected / events-yielding
```

**Track B (ML)** — `.venv` with CUDA 12.4 wheels `track-b:requirements.txt:1`:
```powershell
# setup: uv pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124; uv pip install -r requirements.txt
pytest tests/ -q                          # 69 tests
python scripts/build_real_hetero_data.py  # HeteroData, co_occurs_with 0->1,414
python scripts/compute_training_pair_deltas.py
python scripts/train_holdout_round3.py    # LOO over N=10, throwaway models — no checkpoint
```

**Track C (Backend)** — FastAPI+SQLModel `track-c:backend/requirements.txt:1`:
```powershell
uvicorn app.main:app --reload            # from track-c:backend/
pytest backend/tests/ -q                 # 49 tests
# migrations: backend/migrations/0001_init_fusion_alerts.sql etc. — create_all() never ALTERs; add a numbered .sql for schema changes
```

**Track D (Frontend)** — Next 16 + Tailwind v4 `track-d:frontend/package.json:1`:
```powershell
npm run dev     # next dev
npm run build   # next build (verify before claiming deployable)
npm run lint    # eslint
```

**Sheet review tool** (local curation helper, not CI):
```powershell
python D:\Capstone\tools\sheet_review\sheet_review.py  # then http://localhost:8765 — Shift+Y/R/N
# hardcodes KEY_PATH to track-a's google-service-account.json:37 — set GOOGLE_APPLICATION_CREDENTIALS on other machines
```

**Scraping parallelisation** `CAPSTONE_NEXT_STEPS.md:465` — YouTube (HTTP API) ∥ anything is safe. Instagram ∥ Reddit starves Reddit (same OpenCLI daemon/tab-lease). Safe: one sub-agent for YouTube, one doing Instagram→Reddit **sequentially**.

## 6. Workflow rules — hard-earned

From `CLAUDE.md:24` + `CAPSTONE_NEXT_STEPS.md:963`:

- **Think before coding** — state assumptions, surface tradeoffs, ask if unclear. Push back if a simpler path exists.
- **Simplicity first** — minimum code that solves the asked problem. No speculative flexibility.
- **Surgical changes** — touch only what the request requires; match existing style; clean up only your own orphans (`CLAUDE.md:48`).
- **Goal-driven** — define verifiable criteria (`"fix bug → write failing test → make it pass"` `CLAUDE.md:64`); loop until verified.
- **Verify the consumer, not just the writer** — silent-zero failures came from string/table mismatches (e.g. `relation_type`) `CAPSTONE_NEXT_STEPS.md:965`.
- **"Enabled" ≠ reachable** — restart then verify by *using* it (Docker, claude-in-chrome, Apify) `CAPSTONE_NEXT_STEPS.md:965`.
- **Never trust a guessed handle** — 4/5 guessed handles mapped to fan accounts `CAPSTONE_NEXT_STEPS.md:965`.
- **Re-derive, don't re-assert** — adversarial self-check every round has found real bugs `CAPSTONE_NEXT_STEPS.md:965`.
- **Commit as you go + report deviations in chat** — `CAPSTONE_NEXT_STEPS.md:965`.

**Hard caps & quirks:**
- `DEFAULT_RECENCY_DAYS=1095` (3y) is a ceiling — do not widen without splitting historical-context vs current-status feature pools `CAPSTONE_NEXT_STEPS.md:614`.
- Instagram adapter hard-caps at 12-post first-paint grid (no pagination) + `opencli instagram user` truncates captions at 100 chars; caption-content join + `og:description` is the verified workaround `CAPSTONE_NEXT_STEPS.md:645`.
- Shortcode is base64 media ID — high bits encode timestamp (99.4% <72h, median 0.5d) — zero-network date backfill `CAPSTONE_NEXT_STEPS.md:594`.
- `track-d` deleted `CAPSTONE_NEXT_STEPS.md` locally and is 12d behind — must `git pull origin main` before any cross-track work.
