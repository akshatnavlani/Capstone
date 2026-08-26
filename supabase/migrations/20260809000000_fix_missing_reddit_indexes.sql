-- Fix: reddit_profiles.creator_id, reddit_posts.author_username, and
-- reddit_comments.author_username are FK columns but were missing indexes
-- (inconsistent with youtube_channels.creator_id / instagram_profiles.creator_id,
-- which are indexed). Found via adversarial self-check of the live schema
-- against the migration file on 2026-08-09, before any real data landed.
-- Without these, ON DELETE SET NULL on reddit_profiles requires a sequential
-- scan of reddit_posts/reddit_comments to find rows to null out.

create index if not exists idx_reddit_profiles_creator on reddit_profiles(creator_id);
create index if not exists idx_reddit_posts_author on reddit_posts(author_username);
create index if not exists idx_reddit_comments_author on reddit_comments(author_username);
