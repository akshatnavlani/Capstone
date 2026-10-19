-- One row per run of the daily Instagram reading (scripts/ingestion/instagram_daily.py), 2026-10-18.
--
-- WHY: the Windows task CapstoneInstagramDaily once ended with result code 1 and left no log file, so nobody could tell
-- why. The script now writes its own outcome here, whichever way it ends, with the error text when something failed.
--
-- status: 'started' (still running or killed), 'ok', 'budget_used', 'chrome_not_connected', 'locked', 'failed'.

create table if not exists instagram_daily_runs (
  run_id      uuid primary key default gen_random_uuid(),
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  status      text not null default 'started',
  detail      text
);
create index if not exists idx_instagram_daily_runs_started on instagram_daily_runs (started_at desc);
comment on table instagram_daily_runs is 'Outcome of each daily Instagram reading run (written by instagram_daily.py).';
