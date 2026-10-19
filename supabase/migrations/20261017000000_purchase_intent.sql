-- Purchase-intent comments (2026-10-17): an outcome PROXY, not sales.
--
-- WHY: the project has no real campaign outcomes (sales, conversions); only brands hold those. A comment such as
-- "ordered", "code worked" or "kahan se milega" is a visible audience reaction to a promotion, so counting them per post
-- gives a measurable proxy outcome that the fusion score and the spillover score can be compared against.
-- It must always be called a PROXY in reports: a comment is not a purchase.
--
-- Only matches are stored (a few per thousand comments); scripts/ingestion/purchase_intent.py recreates them.
-- kind: 'bought' = the commenter says they ordered, bought or used the code;
--       'asking' = the commenter asks where to buy, for the link, or the price.

create table if not exists purchase_intent_comments (
  platform   text not null check (platform in ('youtube', 'instagram', 'reddit')),
  comment_id text not null,
  post_id    text not null,
  creator_id uuid,
  kind       text not null check (kind in ('bought', 'asking')),
  phrase     text not null,
  scored_at  timestamptz not null default now(),
  primary key (platform, comment_id, kind)
);
create index if not exists idx_purchase_intent_post on purchase_intent_comments (platform, post_id);
create index if not exists idx_purchase_intent_creator on purchase_intent_comments (creator_id);
comment on table purchase_intent_comments is 'Comments that look like buying or wanting to buy (rule-based proxy outcome, not sales).';
