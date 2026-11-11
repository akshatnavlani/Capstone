-- Per-person Instagram budget, 2026-11-11.
--
-- WHY: the 130-a-day safe limit protects ONE Instagram account, but instagram_daily.done_today counted every Instagram
-- page load in the database, from every laptop. With a second collector (Eesha, 11 Nov) the two accounts shared one
-- budget, so a second laptop added no capacity. Each load now records the database login that wrote it, and
-- done_today counts only the caller's own loads.
--
-- Run once as the database owner. Existing rows keep collected_by NULL (who wrote them is not known); the default is
-- set AFTER the column is added so old rows are not stamped with the owner's name. done_today counts NULL rows for
-- everyone, which only matters on the day this runs (it can only make a budget smaller, never larger).

alter table post_snapshots        add column if not exists collected_by text;
alter table post_snapshots        alter column collected_by set default current_user;
alter table instagram_extra_loads add column if not exists collected_by text;
alter table instagram_extra_loads alter column collected_by set default current_user;

create index if not exists idx_post_snapshots_ig_collector_day
  on post_snapshots (collected_by, fetched_at desc) where platform = 'instagram';

comment on column post_snapshots.collected_by is 'Database login that wrote the row (default current_user). Used for the per-person Instagram budget.';
comment on column instagram_extra_loads.collected_by is 'Database login that logged the loads (default current_user).';
