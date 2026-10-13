-- YouTube growth snapshots run INSIDE Supabase, on the database's own timer (2026-10-13).
--
-- WHY: the same job on GitHub Actions' schedule ran only 4 times in 24 hours (about every 7-9 hours instead of every 2),
-- which is too coarse for first-24-hours growth curves. pg_cron is the database's own clock, so it fires on time.
--
-- WHAT public.snapshot_youtube_run() does (the SQL twin of scripts/ingestion/snapshot_youtube.py):
--   1. for every row in youtube_channels, reads the latest 10 uploads (playlistItems, 1 quota unit) and notes uploads we have
--      never stored;
--   2. reads views/likes/comments (videos.list, 1 unit per 50 videos) for every stored video younger than max_age_days plus
--      the new uploads;
--   3. stores the new uploads in youtube_videos, refreshes the latest counts on the video rows, and appends one
--      post_snapshots row per video (its age is fetched_at minus published_at).
-- About 150-170 YouTube quota units per run. New uploads get no brand match or sponsorship label here: run
-- scripts/ingestion (apply_sponsorship) afterwards, as for any newly collected video.
--
-- The YouTube API key is NOT in this file. It lives in the encrypted vault under the name 'youtube_api_key'
-- (select vault.create_secret('<key>', 'youtube_api_key', 'YouTube Data API key for the snapshot timer')).
-- Anyone who can read vault.decrypted_secrets can read it, so keep the key restricted to the YouTube Data API v3.

create extension if not exists http with schema extensions;
create extension if not exists pg_cron;

create table if not exists snapshot_job_log (
  run_id            bigint generated always as identity primary key,
  started_at        timestamptz not null default now(),
  seconds           numeric,
  channels_checked  int,
  new_uploads       int,
  videos_snapshotted int,
  errors            int,
  first_error       text
);
comment on table snapshot_job_log is 'One row per run of snapshot_youtube_run(): what it checked and wrote.';

-- 'PT1H2M3S' -> 3723 (YouTube durations have no month/year part)
create or replace function iso8601_duration_seconds(d text) returns integer
language sql immutable as $$
  select case when d is null then null else
    coalesce(substring(d from '(\d+)D')::int, 0) * 86400 + coalesce(substring(d from '(\d+)H')::int, 0) * 3600
    + coalesce(substring(d from '(\d+)M')::int, 0) * 60 + coalesce(substring(d from '(\d+)S')::int, 0) end
$$;

create or replace function public.snapshot_youtube_run(max_age_days int default 7) returns jsonb
language plpgsql
set search_path = public, extensions
as $$
declare
  k            text;
  t0           timestamptz := clock_timestamp();
  base         constant text := 'https://www.googleapis.com/youtube/v3/';
  chan         record;
  resp         extensions.http_response;
  items        jsonb;
  new_map      jsonb := '{}'::jsonb;      -- video_id -> channel_id for uploads we have never stored
  vid          text;
  targets      text[];
  chunk        text[];
  i            int;
  n_channels   int := 0;
  n_new        int := 0;
  n_snap       int := 0;
  n_err        int := 0;
  first_err    text;
  n            int;
begin
  select decrypted_secret into k from vault.decrypted_secrets where name = 'youtube_api_key';
  if k is null then
    raise exception 'snapshot_youtube_run: no secret named youtube_api_key in the vault';
  end if;
  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT', '25');

  -- 1. discovery: the latest 10 uploads of every channel; remember the ones we have never stored
  for chan in select channel_id from youtube_channels where channel_id like 'UC%' loop
    n_channels := n_channels + 1;
    begin
      resp := extensions.http_get(base || 'playlistItems?part=contentDetails&maxResults=10&playlistId=UU'
                                  || substr(chan.channel_id, 3) || '&key=' || k);
      if resp.status = 200 then
        for vid in select e->'contentDetails'->>'videoId'
                   from jsonb_array_elements(coalesce((resp.content::jsonb)->'items', '[]'::jsonb)) e loop
          if not exists (select 1 from youtube_videos where video_id = vid) then
            new_map := new_map || jsonb_build_object(vid, chan.channel_id);
          end if;
        end loop;
      else
        n_err := n_err + 1;
        first_err := coalesce(first_err, 'playlistItems ' || chan.channel_id || ' http ' || resp.status || ': ' || left(resp.content, 120));
      end if;
    exception when others then
      n_err := n_err + 1;
      first_err := coalesce(first_err, 'playlistItems ' || chan.channel_id || ': ' || sqlerrm);
    end;
  end loop;
  n_new := (select count(*) from jsonb_object_keys(new_map));

  -- 2. every stored video younger than max_age_days, plus the new uploads
  select coalesce(array_agg(video_id), '{}') into targets
  from (select video_id from youtube_videos where published_at >= now() - make_interval(days => max_age_days)
        union select jsonb_object_keys(new_map)) t;

  i := 1;
  while i <= coalesce(array_length(targets, 1), 0) loop
    chunk := targets[i : i + 49];
    i := i + 50;
    begin
      resp := extensions.http_get(base || 'videos?part=snippet,statistics,contentDetails&id='
                                  || array_to_string(chunk, ',') || '&key=' || k);
      if resp.status <> 200 then
        n_err := n_err + 1;
        first_err := coalesce(first_err, 'videos http ' || resp.status || ': ' || left(resp.content, 120));
        continue;
      end if;
      items := (resp.content::jsonb)->'items';
      if items is null or jsonb_array_length(items) = 0 then continue; end if;

      -- new uploads first, so the update and the snapshot below can find their rows
      insert into youtube_videos (video_id, channel_id, creator_id, title, description, published_at, thumbnail_url,
                                  duration_seconds, view_count, like_count, comment_count, tags)
      select e->>'id', e->'snippet'->>'channelId',
             (select yc.creator_id from youtube_channels yc where yc.channel_id = e->'snippet'->>'channelId'),
             e->'snippet'->>'title', e->'snippet'->>'description', (e->'snippet'->>'publishedAt')::timestamptz,
             e->'snippet'->'thumbnails'->'high'->>'url', iso8601_duration_seconds(e->'contentDetails'->>'duration'),
             (e->'statistics'->>'viewCount')::bigint, (e->'statistics'->>'likeCount')::bigint,
             (e->'statistics'->>'commentCount')::bigint,
             case when e->'snippet' ? 'tags' then array(select jsonb_array_elements_text(e->'snippet'->'tags')) end
      from jsonb_array_elements(items) e
      where new_map ? (e->>'id') and exists (select 1 from youtube_channels yc where yc.channel_id = e->'snippet'->>'channelId')
      on conflict (video_id) do nothing;

      -- latest counts on the video row (and the length, if an older collector never stored it)
      update youtube_videos y set
        view_count = (e->'statistics'->>'viewCount')::bigint, like_count = (e->'statistics'->>'likeCount')::bigint,
        comment_count = (e->'statistics'->>'commentCount')::bigint,
        duration_seconds = coalesce(y.duration_seconds, iso8601_duration_seconds(e->'contentDetails'->>'duration')),
        fetched_at = now()
      from jsonb_array_elements(items) e where y.video_id = e->>'id';

      -- one snapshot row per video, the counts at this moment
      insert into post_snapshots (platform, post_id, creator_id, view_count, like_count, comment_count)
      select 'youtube', e->>'id', y.creator_id, (e->'statistics'->>'viewCount')::bigint,
             (e->'statistics'->>'likeCount')::bigint, (e->'statistics'->>'commentCount')::bigint
      from jsonb_array_elements(items) e join youtube_videos y on y.video_id = e->>'id';
      get diagnostics n = row_count;
      n_snap := n_snap + n;
    exception when others then
      n_err := n_err + 1;
      first_err := coalesce(first_err, 'videos chunk: ' || sqlerrm);
    end;
  end loop;

  insert into snapshot_job_log (seconds, channels_checked, new_uploads, videos_snapshotted, errors, first_error)
  values (round(extract(epoch from clock_timestamp() - t0)::numeric, 1), n_channels, n_new, n_snap, n_err, first_err);
  return jsonb_build_object('channels', n_channels, 'new_uploads', n_new, 'snapshots', n_snap, 'errors', n_err, 'first_error', first_err);
end;
$$;

comment on function public.snapshot_youtube_run(int) is
  'Appends YouTube growth snapshots (SQL twin of scripts/ingestion/snapshot_youtube.py). Reads the API key from vault secret youtube_api_key. Scheduled by pg_cron job youtube_snapshots.';

-- Only the database owner (and the cron job, which runs as the owner) may call it: it spends API quota and reads the vault.
revoke all on function public.snapshot_youtube_run(int) from public, anon, authenticated;
revoke all on table snapshot_job_log from anon, authenticated;
