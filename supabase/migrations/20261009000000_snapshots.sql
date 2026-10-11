-- Append-only snapshots of post and account counts (2026-10-09).
--
-- WHY: every collector run UPSERTED view/like/comment/follower counts over the previous
-- values, so the database only ever held the latest number and no history. Growth over the
-- first hours and days of a post, and any lead-lag between YouTube and Instagram, cannot be
-- measured from a single number. These tables keep one row per observation instead.
--
-- Each row stores WHEN it was observed (fetched_at, UTC). The age of a post at that moment is
-- fetched_at minus the post's own timestamp, so observations do not need to happen at exact
-- ages; the analysis reads the curve and interpolates.
--
-- NULL means "not available from this source" (for example Instagram does not give view
-- counts for photos), never zero.
--
-- The collector writes these inside a savepoint and carries on if the tables do not exist yet,
-- so applying this migration is not a prerequisite for running the collector.

create table if not exists post_snapshots (
  snapshot_id    bigserial primary key,
  platform       text        not null check (platform in ('youtube', 'instagram')),
  post_id        text        not null,   -- youtube_videos.video_id or instagram_posts.post_id
  creator_id     uuid,
  fetched_at     timestamptz not null default now(),
  view_count     bigint,
  like_count     bigint,
  comment_count  bigint
);

create index if not exists idx_post_snapshots_post
  on post_snapshots (platform, post_id, fetched_at);
create index if not exists idx_post_snapshots_creator_time
  on post_snapshots (creator_id, fetched_at);

create table if not exists profile_snapshots (
  snapshot_id     bigserial primary key,
  platform        text        not null check (platform in ('youtube', 'instagram')),
  account_id      text        not null,  -- youtube_channels.channel_id or instagram_profiles.username
  creator_id      uuid,
  fetched_at      timestamptz not null default now(),
  follower_count  bigint,                -- subscribers on YouTube
  post_count      bigint,                -- videos on YouTube
  view_count      bigint                 -- channel total views (YouTube only)
);

create index if not exists idx_profile_snapshots_account
  on profile_snapshots (platform, account_id, fetched_at);
create index if not exists idx_profile_snapshots_creator_time
  on profile_snapshots (creator_id, fetched_at);

comment on table post_snapshots is
  'Append-only counts for a post at the moment we fetched it. Never updated; one row per observation.';
comment on table profile_snapshots is
  'Append-only follower/subscriber counts for an account at the moment we fetched it.';
