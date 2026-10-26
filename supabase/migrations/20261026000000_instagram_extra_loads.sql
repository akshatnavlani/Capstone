-- Instagram page loads that do not write a post_snapshots row (ownership audits, one-off checks), 2026-10-26.
--
-- WHY: the daily budget (instagram_daily.done_today) counted only post_snapshots rows. On 26 Oct a 38-post ownership audit used page loads that
-- left no snapshot row, so the scheduled 12:00 run would have started from a budget that looked emptier than it was and taken the day to about
-- 170 loads (safe range 100-135). Anything that opens Instagram pages without a snapshot row now logs its loads here, and done_today adds them.

create table if not exists instagram_extra_loads (
  load_id    uuid primary key default gen_random_uuid(),
  logged_at  timestamptz not null default now(),
  loads      integer not null check (loads > 0),
  reason     text
);
create index if not exists idx_instagram_extra_loads_logged_at on instagram_extra_loads (logged_at desc);
comment on table instagram_extra_loads is 'Instagram page loads that left no post_snapshots row (audits, checks). Counted in the daily page-load budget.';
