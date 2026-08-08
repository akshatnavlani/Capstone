-- Bounded brand-data addition (Weeks 3-4), per user decision 2026-08-09.
-- Resolves Track B's confirmed blocker (GRAPH_SCHEMA.md): GAIL's (brand, sponsors,
-- creator) edge needs an actual brand entity, not just a bare is_sponsored boolean.
--
-- Scope boundary (deliberately narrow, not an open-ended brand-discovery crawl):
-- brands are ONLY added when a name is extracted from sponsorship-disclosure text
-- already present on creator content rows (sponsorship_raw_matches / captions/titles/
-- bodies). No independent brand search/crawl. See ORCHESTRATION.md for the
-- extraction step this feeds.

create table if not exists brands (
  brand_id          uuid primary key default gen_random_uuid(),
  name              text not null,
  category          text,   -- industry/vertical, nullable until scraped/classified
  youtube_handle    text,
  instagram_handle  text,
  reddit_handle     text,
  follower_count    bigint,   -- from whichever official account was found/scraped
  post_count        integer,
  is_verified       boolean,
  source            text not null default 'sponsorship_mention',
  fetched_at        timestamptz,  -- null until the brand's own profile has been scraped
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (name)
);

comment on table brands is
  'Populated only from brand names/mentions found in sponsorship-disclosure text on '
  'creator content rows (see sponsorship_raw_matches) — not an independent brand '
  'discovery crawl. source column exists in case that changes later.';

-- Links each sponsored content row to the brand it names, giving Track B's GAIL
-- graph the (brand, sponsors, creator) edge endpoint it's missing. Nullable: most
-- rows won't be labeled yet (is_sponsored is still null pre-Track-C-pipeline), and
-- even once labeled, not every sponsored post names an extractable brand.
alter table youtube_videos add column if not exists brand_id uuid references brands(brand_id) on delete set null;
alter table instagram_posts add column if not exists brand_id uuid references brands(brand_id) on delete set null;
alter table reddit_posts add column if not exists brand_id uuid references brands(brand_id) on delete set null;

create index if not exists idx_youtube_videos_brand on youtube_videos(brand_id);
create index if not exists idx_instagram_posts_brand on instagram_posts(brand_id);
create index if not exists idx_reddit_posts_brand on reddit_posts(brand_id);

-- Extend the derived sponsorship-events view to carry brand_id through, so Track B
-- can build the sponsors/sponsored_by edges directly from this view.
-- (drop + recreate, not create-or-replace: adding a column that isn't at the end of
-- the column list isn't allowed via create-or-replace in Postgres)
drop view if exists creator_sponsorship_events;
create view creator_sponsorship_events as
  select creator_id, brand_id, 'youtube'::text as platform, video_id as content_id,
         published_at as posted_at, sponsorship_raw_matches
  from youtube_videos
  where is_sponsored is true
  union all
  select creator_id, brand_id, 'instagram'::text, post_id,
         posted_at, sponsorship_raw_matches
  from instagram_posts
  where is_sponsored is true
  union all
  select creator_id, brand_id, 'reddit'::text, post_id,
         posted_at, sponsorship_raw_matches
  from reddit_posts
  where is_sponsored is true;
