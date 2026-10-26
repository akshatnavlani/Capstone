-- Capstone: influencer-brand matching — initial data-layer schema (Track A: Data/Infra)
-- Design rationale / field-by-field rationale lives in SCHEMA.md at repo root.
-- Target: Supabase (Postgres). Run via `supabase db push` or paste into the
-- Supabase SQL editor. Idempotent: safe to re-run (IF NOT EXISTS everywhere).

create extension if not exists pgcrypto;

-- ============================================================
-- Seed table: one row per tracked entity (athlete, team, league,
-- fitness/lifestyle influencer). This is Table 1 from the original
-- Capstone doc: unique_id, name, cross-platform handles, prior endorsements.
-- ============================================================
create table if not exists creators (
  creator_id     uuid primary key default gen_random_uuid(),
  name           text not null,
  category       text not null check (category in (
                   'athlete', 'team', 'league',
                   'fitness_influencer', 'lifestyle_influencer', 'other'
                 )),
  youtube_handle    text,
  instagram_handle  text,
  reddit_handles    text[] not null default '{}',  -- often multiple (personal + team/fan subreddits)
  notes             text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

comment on table creators is
  'Seed table. "prior endorsements" from the original doc is NOT a column here — '
  'per PROJECT_PLAN.md Section 1, it is derived from is_sponsored-tagged posts '
  'across platform tables. See the creator_sponsorship_events view below.';

-- Accounts related to a creator that are not the creator's own official
-- handle (team pages, family, frequent collaborators, fan pages) — needed
-- for cross-platform linking / spillover-graph edges (GAIL branch input).
create table if not exists creator_related_accounts (
  id             uuid primary key default gen_random_uuid(),
  creator_id     uuid not null references creators(creator_id) on delete cascade,
  platform       text not null check (platform in ('youtube', 'instagram', 'reddit')),
  handle         text not null,
  relation_type  text,  -- e.g. 'team', 'league', 'frequent_collaborator', 'fan_page', 'family'
  created_at     timestamptz not null default now(),
  unique (creator_id, platform, handle)
);

create index if not exists idx_related_accounts_creator on creator_related_accounts(creator_id);

-- ============================================================
-- YouTube (official Data API — primary source)
-- ============================================================
create table if not exists youtube_channels (
  channel_id         text primary key,
  creator_id         uuid references creators(creator_id) on delete set null,
  channel_handle     text,
  title              text,
  description        text,
  subscriber_count   bigint,
  view_count         bigint,
  video_count        integer,
  channel_created_at timestamptz,
  country            text,
  is_bot_flagged     boolean,   -- populated by Track B's bot-detection heuristics
  bot_score          real,
  fetched_at         timestamptz not null default now(),
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create index if not exists idx_youtube_channels_creator on youtube_channels(creator_id);

create table if not exists youtube_videos (
  video_id                 text primary key,
  channel_id               text not null references youtube_channels(channel_id) on delete cascade,
  creator_id               uuid references creators(creator_id) on delete set null,  -- denormalized for join-free queries
  title                    text,
  description              text,
  published_at             timestamptz,
  thumbnail_url            text,
  duration_seconds         integer,
  view_count               bigint,
  like_count               bigint,
  comment_count            bigint,
  tags                     text[],
  is_sponsored             boolean,  -- null = not yet labeled; populated by Track C's disclosure-tag pipeline
  sponsorship_raw_matches  jsonb,    -- matched disclosure phrases, for validating the labeler (load-bearing per plan)
  fetched_at               timestamptz not null default now(),
  created_at               timestamptz not null default now()
);

create index if not exists idx_youtube_videos_channel on youtube_videos(channel_id);
create index if not exists idx_youtube_videos_creator on youtube_videos(creator_id);
create index if not exists idx_youtube_videos_published on youtube_videos(published_at);
create index if not exists idx_youtube_videos_sponsored on youtube_videos(is_sponsored) where is_sponsored is not null;

create table if not exists youtube_comments (
  comment_id     text primary key,
  video_id       text not null references youtube_videos(video_id) on delete cascade,
  author_handle  text,
  text           text,
  published_at   timestamptz,
  like_count     integer,
  fetched_at     timestamptz not null default now()
);

create index if not exists idx_youtube_comments_video on youtube_comments(video_id);

-- ============================================================
-- Instagram (agent-reach / OpenCLI — session-based)
-- ============================================================
create table if not exists instagram_profiles (
  username         text primary key,
  creator_id       uuid references creators(creator_id) on delete set null,
  full_name        text,
  bio              text,
  follower_count   bigint,
  following_count  bigint,
  post_count       integer,
  is_verified      boolean,
  is_bot_flagged   boolean,
  bot_score        real,
  fetched_at       timestamptz not null default now(),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists idx_instagram_profiles_creator on instagram_profiles(creator_id);

create table if not exists instagram_posts (
  post_id                  text primary key,
  username                 text not null references instagram_profiles(username) on delete cascade,
  creator_id               uuid references creators(creator_id) on delete set null,
  caption                  text,
  posted_at                timestamptz,
  thumbnail_url            text,
  media_type               text,  -- photo | video | carousel | reel
  like_count               bigint,
  comment_count            bigint,
  hashtags                 text[],
  is_sponsored             boolean,
  sponsorship_raw_matches  jsonb,
  fetched_at               timestamptz not null default now(),
  created_at               timestamptz not null default now()
);

create index if not exists idx_instagram_posts_username on instagram_posts(username);
create index if not exists idx_instagram_posts_creator on instagram_posts(creator_id);
create index if not exists idx_instagram_posts_posted on instagram_posts(posted_at);
create index if not exists idx_instagram_posts_sponsored on instagram_posts(is_sponsored) where is_sponsored is not null;

create table if not exists instagram_comments (
  comment_id       text primary key,
  post_id          text not null references instagram_posts(post_id) on delete cascade,
  author_username  text,
  text             text,
  posted_at        timestamptz,
  like_count       integer,
  fetched_at       timestamptz not null default now()
);

create index if not exists idx_instagram_comments_post on instagram_comments(post_id);

-- ============================================================
-- Reddit (agent-reach / OpenCLI or rdt-cli — session-based, login-gated)
-- ============================================================
create table if not exists reddit_profiles (
  username             text primary key,
  creator_id           uuid references creators(creator_id) on delete set null,  -- nullable: most reddit accounts are fans/mods, not the creator
  account_created_at   timestamptz,
  comment_karma        integer,
  link_karma           integer,
  is_bot_flagged       boolean,
  bot_score            real,
  fetched_at           timestamptz not null default now(),
  created_at           timestamptz not null default now()
);

create table if not exists reddit_posts (
  post_id                  text primary key,
  subreddit                text not null,
  creator_id               uuid references creators(creator_id) on delete set null,
  author_username          text references reddit_profiles(username) on delete set null,
  title                    text,
  body                     text,
  posted_at                timestamptz,
  score                    integer,
  num_comments             integer,
  is_sponsored             boolean,
  sponsorship_raw_matches  jsonb,
  fetched_at               timestamptz not null default now(),
  created_at               timestamptz not null default now()
);

create index if not exists idx_reddit_posts_subreddit on reddit_posts(subreddit);
create index if not exists idx_reddit_posts_creator on reddit_posts(creator_id);
create index if not exists idx_reddit_posts_posted on reddit_posts(posted_at);
create index if not exists idx_reddit_posts_sponsored on reddit_posts(is_sponsored) where is_sponsored is not null;

create table if not exists reddit_comments (
  comment_id       text primary key,
  post_id          text not null references reddit_posts(post_id) on delete cascade,
  author_username  text references reddit_profiles(username) on delete set null,
  body             text,
  posted_at        timestamptz,
  score            integer,
  fetched_at       timestamptz not null default now()
);

create index if not exists idx_reddit_comments_post on reddit_comments(post_id);

-- ============================================================
-- Derived "Historical Data - Partnerships/Collaborations"
-- Per PROJECT_PLAN.md Section 1: this is NOT a separately-maintained table —
-- it's the union of is_sponsored=true posts across all three platforms.
-- This is the sole source of GAIL treatment-event labels.
-- ============================================================
create or replace view creator_sponsorship_events as
  select creator_id, 'youtube'::text as platform, video_id as content_id,
         published_at as posted_at, sponsorship_raw_matches
  from youtube_videos
  where is_sponsored is true
  union all
  select creator_id, 'instagram'::text, post_id,
         posted_at, sponsorship_raw_matches
  from instagram_posts
  where is_sponsored is true
  union all
  select creator_id, 'reddit'::text, post_id,
         posted_at, sponsorship_raw_matches
  from reddit_posts
  where is_sponsored is true;
