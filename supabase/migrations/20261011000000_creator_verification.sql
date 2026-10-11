-- Verified creator list for the data-collection plan (2026-10-11).
--
-- WHY: the collection plan needs a list of Indian fitness creators whose YouTube channel and
-- Instagram account are CONFIRMED to be the same person, with the evidence kept next to each
-- link, so a wrong match cannot contaminate the posts, growth numbers and sponsorship labels
-- collected for them. This table is that list. It does not change any existing table.
--
-- One row per creator. `creator_id` is filled when the creator already exists in `creators`
-- (the id that joins YouTube, Instagram and Reddit rows); it is NULL for creators not yet added.
--
-- link_level
--   confirmed  the YouTube channel itself lists the exact Instagram handle, or the Instagram
--              bio links to / names the channel (both_directions = true when both hold)
--   probable   same person very likely (matching name and plausible audience sizes) but no
--              direct link on either side
--   pending    a channel or an account was found but the other side could not be verified yet
--   page       a real account, but a page / media / brand rather than a person
--
-- Counts (yt_subscribers, ig_followers) are as displayed on the day in checked_at, so they are
-- rounded (for example 2.7M is stored as 2700000). yt_last_upload comes from YouTube's own feed.
-- NULL means "not read", never zero.

create table if not exists creator_verification (
  verification_id   uuid primary key default gen_random_uuid(),
  creator_id        uuid references creators(creator_id) on delete set null,
  display_name      text        not null,
  content_type      text        not null check (content_type in ('fitness', 'adjacent', 'brand_like', 'famous_general')),
  size_tier         text        check (size_tier in ('famous', 'mid', 'small')),
  sponsor_group     text        check (sponsor_group in ('A', 'B')),
  yt_handle         text,
  yt_subscribers    bigint,
  yt_last_upload    date,
  ig_handle         text,
  ig_followers      bigint,
  link_level        text        not null check (link_level in ('confirmed', 'probable', 'pending', 'page')),
  both_directions   boolean     not null default false,
  link_evidence     text,
  sponsor_brands    text[]      not null default '{}',
  note              text,
  verified_by       text        not null,
  checked_at        timestamptz not null default now()
);

-- One creator per Instagram handle (or per YouTube handle when there is no Instagram yet).
create unique index if not exists uq_creator_verification_account
  on creator_verification ((lower(coalesce(ig_handle, yt_handle))));

create index if not exists idx_creator_verification_creator on creator_verification (creator_id);
create index if not exists idx_creator_verification_level on creator_verification (link_level);

comment on table creator_verification is
  'Verified Indian fitness creator list: YouTube and Instagram accounts linked per creator, with the evidence for each link.';
comment on column creator_verification.sponsor_group is
  'A = a sponsor discount code or brand tag is visible in the bio (sponsorship-active); B = none seen. Bio signal only, not a post-level sponsorship label.';
