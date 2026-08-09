-- Fix: reddit_posts.creator_id is a single FK, but a Reddit post can legitimately
-- be relevant to MULTIPLE creators — most commonly because creators.reddit_handles
-- is often a generic community subreddit (r/badminton), not a creator-exclusive one,
-- and multiple target creators can share the same subreddit.
--
-- Found running a real Weeks 7-8 bulk collection (2026-08-10): PV Sindhu and Saina
-- Nehwal both map to r/badminton. Since reddit_posts.post_id is a global primary key,
-- whichever creator's worker ran first (Sindhu) "won" the ON CONFLICT upsert, and
-- Saina Nehwal ended up with ZERO reddit posts credited — not duplicates, an actual
-- silent data loss for the second creator sharing a subreddit. This will recur for
-- every future creator pair sharing a generic sport subreddit.
--
-- Fix: a proper many-to-many junction table. reddit_posts.creator_id is kept as-is
-- (whichever creator's worker first wrote the post — harmless as a "first seen by"
-- marker) but is no longer the source of truth for "which creators does this post
-- relate to" — query reddit_post_creators for that.

create table if not exists reddit_post_creators (
  post_id     text not null references reddit_posts(post_id) on delete cascade,
  creator_id  uuid not null references creators(creator_id) on delete cascade,
  primary key (post_id, creator_id)
);

create index if not exists idx_reddit_post_creators_creator on reddit_post_creators(creator_id);

-- Backfill: associate every existing reddit_posts row with EVERY creator whose
-- reddit_handles includes that post's subreddit — not just whichever creator_id
-- happens to be stored on the row today (that's exactly the data the bug lost).
insert into reddit_post_creators (post_id, creator_id)
select rp.post_id, c.creator_id
from reddit_posts rp
join creators c on rp.subreddit = any(c.reddit_handles)
on conflict do nothing;
