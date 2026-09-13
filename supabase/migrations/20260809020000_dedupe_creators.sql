-- Fix: `creators` had no unique constraint on youtube_handle/instagram_handle, so the
-- orchestrator's ON CONFLICT DO NOTHING silently had no constraint to trigger on,
-- creating a duplicate creator row on every rerun for the same handle. Found running
-- a real Weeks 5-6 ingestion pilot (2026-08-09) — a single real channel ('athleanx')
-- ended up split across two creator_id rows, with youtube_channels and youtube_videos
-- pointing at different ones. Real data corruption, not hypothetical.

-- Merge duplicate athleanx rows found from this bug before adding the constraint that
-- prevents new ones. Re-point content rows to whichever creator_id the channel row
-- (the "primary" identity anchor) already used, then drop the orphan.
do $$
declare
  keep_id uuid;
  drop_id uuid;
begin
  select creator_id into keep_id from youtube_channels where channel_handle = 'athleanx' limit 1;
  select creator_id into drop_id from creators where youtube_handle = 'athleanx' and creator_id != keep_id limit 1;
  if drop_id is not null then
    update youtube_videos set creator_id = keep_id where creator_id = drop_id;
    delete from creators where creator_id = drop_id;
  end if;
end $$;

create unique index if not exists uq_creators_youtube_handle on creators(youtube_handle) where youtube_handle is not null;
create unique index if not exists uq_creators_instagram_handle on creators(instagram_handle) where instagram_handle is not null;
