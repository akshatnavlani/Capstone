-- Reddit strategy change (Weeks 11-13, 2026-08-10): split a creator's Reddit sources
-- into two kinds that must be collected DIFFERENTLY.
--
-- Why: measured on real collected data, general/topic subreddits produce ~0% creator
-- relevance when their feed is taken broadly. Verified directly before making this
-- change: of 41 r/tennis posts credited to Sania Mirza, 0 mentioned her; 40 r/Boxing
-- posts credited to MC Mary Kom, 0 mentioned her; 41 r/badminton posts credited to
-- PV Sindhu, 0 mentioned her. That is ~3,000 datapoints of topically-adjacent noise
-- attributed to specific creators — the same class of error as the earlier
-- shared-subreddit bug, arrived at from a different direction.
--
--   reddit_handles     -> CREATOR-SPECIFIC subs (r/viratkohli, r/kingkohli).
--                         Most content is naturally about the creator, so the feed
--                         can be taken broadly, as before.
--   reddit_topic_subs  -> GENERAL/TOPIC subs (r/ipl, r/indiacricket, r/tennis).
--                         The feed must NOT be taken broadly. Collect via
--                         subreddit-scoped SEARCH for the creator's name, and
--                         additionally verify each hit actually mentions them.

alter table creators add column if not exists reddit_topic_subs text[] not null default '{}';

comment on column creators.reddit_handles is
  'Creator-SPECIFIC subreddits only (mostly about this creator) — safe to take the feed broadly.';
comment on column creators.reddit_topic_subs is
  'General/topic subreddits — must be searched for the creator by name, never taken as a whole feed.';
