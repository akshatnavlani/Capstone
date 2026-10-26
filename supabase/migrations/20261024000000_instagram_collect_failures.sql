-- Creators the daily Instagram job could not collect (2026-10-24).
--
-- WHY: on 24 Oct the job stopped at a creator whose Instagram handle had never been verified ("no post links found"). Nothing was saved
-- for that creator, so it came first again the next day and stopped the run again: one bad handle blocking the whole day's collection.
-- A page problem on ONE creator is now written here and skipped (for 14 days); only a real block (HTTP 429, rate limit, a redirect to
-- an error page) stops the run. The table is also a worklist: handles that fail here are the ones to check by hand in creator_verification.

create table if not exists instagram_collect_failures (
  failure_id  uuid primary key default gen_random_uuid(),
  creator_id  uuid not null,
  handle      text not null,
  failed_at   timestamptz not null default now(),
  reason      text
);
create index if not exists idx_instagram_collect_failures_creator on instagram_collect_failures (creator_id, failed_at desc);
comment on table instagram_collect_failures is 'Creators the daily Instagram job could not collect (no posts found, private page, wrong handle...). Skipped for 14 days.';
