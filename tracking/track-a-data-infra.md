# Track A — Data / Infra — Change Log (review-1 branch)

Owner: Track A (Scraping, DB population, raw `creator_related_accounts` facts)
Branch: `review-1` (D:\Capstone, currently checked out)
Standing rule: No new scraping for demo polish unless explicitly requested. All changes below are logged so Track A can replay them.

## Change Log

### 2026-08-27 — Initial tracking files created (demo polish phase)
- Created `tracking/` directory and per-track files per user request.
- No functional code changes to Track A ownership in this step.

### 2026-08-27 — Hosting confirmed (review-1)
- Backend env: `D:\Capstone\backend\.env` uses Supabase pooler `aws-0-ap-south-1.pooler.supabase.com:5432` (password in env, do not commit).
- Frontend env: `D:\Capstone\frontend\.env.local` -> `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`.

---

## Master Prompt — Track A (update after each change)

> You are Track A (Data/Infra) on branch `review-1`. Your ownership is `scripts/ingestion/orchestrator.py:1` (1460 lines), `scripts/ingestion/pair_count.py:1` (canonical pair definition), `supabase/migrations/` (7 files), and all raw facts population (`creators`, `creator_related_accounts`, `instagram_profiles`, `youtube_channels`, `youtube_videos`, `instagram_posts`, `reddit_posts`).
>
> **Current state (review-1, 2026-08-27):**
> - DB: Supabase `https://fhbgbtxdtfluzohxyivg.supabase.co` — pooler `DATABASE_URL=postgresql://postgres.fhbgbtxdtfluzohxyivg:<pwd>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`. Live counts verified 2026-08-26: 259 creators, 54 pair rows, 170 edges. Do not widen `DEFAULT_RECENCY_DAYS=1095` without splitting feature pools.
> - Constraints aware: `creators.category` CHECK, `creator_related_accounts.relation_type="frequent_collaborator"`, both endpoints must exist in `creators`, `instagram_profiles.creator_id` nullable, `is_sponsored`/`sponsorship_raw_matches` = Track C, `is_bot_flagged`/`bot_score` = Track B, `brands` only from `source='sponsorship_mention'`, Google Sheet `1UX9K3gQnh4roMgTi0cy3Sxm82kTLDkZI9w4jJELFVPQ` never write `approval_status`.
>
> **Replay instructions:**
> - No Track A code changes required for demo polish yet. If a future entry appears in the Change Log above, apply that exact diff in order.
> - After applying, verify with: `python D:\Capstone\scripts\ingestion\pair_count.py` (expect 4 readings) and REST count queries per `CAPSTONE_NEXT_STEPS.md:259`.
