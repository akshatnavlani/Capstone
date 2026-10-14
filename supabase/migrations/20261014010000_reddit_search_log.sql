-- Which Reddit searches scripts/ingestion/reddit_collect.py has already run (2026-10-14).
--
-- WHY: a full run is about 340 searches. Reddit throttles fast scraping, so the run can stop part-way; with this log a
-- re-run skips what was already searched (for 7 days) and carries on, instead of starting again.

create table if not exists reddit_search_log (
  kind         text not null check (kind in ('creator', 'brand')),
  query        text not null,
  subreddit    text not null,
  results      int,
  searched_at  timestamptz not null default now(),
  primary key (kind, query, subreddit)
);
comment on table reddit_search_log is 'Reddit searches already run by reddit_collect.py, so an interrupted run can resume.';
