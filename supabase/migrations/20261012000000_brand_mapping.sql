-- Creator-to-brand mapping and the YouTube channel id on the verified list (2026-10-12).
--
-- WHY: GAIL reads sponsorship events from the creator_sponsorship_events view, whose brand_id was empty
-- for about two thirds of the 66 sponsored posts, and `brands` held no fitness, supplement or footwear
-- brands (and a few junk rows such as 'Delhi' and 'gmail'). This migration adds
--   1. creator_verification.yt_channel_id: YouTube's permanent channel id (it never changes when a
--      creator renames the channel), the stable key for the YouTube side of each creator;
--   2. creator_brand_links: one row per (verified creator, brand) with the evidence, so the
--      brand-to-influencer mapping exists at creator level before any post-level labels do.
-- The brand rows themselves are data and are loaded by a one-off script from
-- scripts/ingestion/known_brands.py. Junk brands are FLAGGED (category = 'not_a_brand'), never deleted,
-- because existing posts still point at them.

alter table creator_verification add column if not exists yt_channel_id text;
create index if not exists idx_creator_verification_yt_channel on creator_verification (yt_channel_id);

create table if not exists creator_brand_links (
  link_id          uuid primary key default gen_random_uuid(),
  verification_id  uuid not null references creator_verification(verification_id) on delete cascade,
  creator_id       uuid references creators(creator_id) on delete set null,
  brand_id         uuid not null references brands(brand_id) on delete cascade,
  platform         text not null default 'unspecified'
                   check (platform in ('instagram', 'youtube', 'both', 'unspecified')),
  evidence         text not null,
  source           text not null,
  first_seen       date not null default current_date,
  unique (verification_id, brand_id)
);

create index if not exists idx_creator_brand_links_brand on creator_brand_links (brand_id);
create index if not exists idx_creator_brand_links_creator on creator_brand_links (creator_id);

comment on table creator_brand_links is
  'Which brand a verified creator promotes, with the evidence. Creator-level mapping; post-level labels live in instagram_posts / youtube_videos (brand_id) and the creator_sponsorship_events view.';
