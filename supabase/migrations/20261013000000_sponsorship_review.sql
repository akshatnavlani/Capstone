-- Hand check of the rule-based sponsorship labels (2026-10-13).
--
-- WHY: is_sponsored / creator_sponsorship_events are set by sponsorship_detector.py rules, not by people. Before the labels
-- are used to train or evaluate GAIL, a person reads a spread-out sample and says whether each one really is sponsored. This
-- table holds the sample and the verdicts, so the real precision (and the miss rate on unflagged posts) can be computed.
--
-- verdict values: sponsored (the post itself promotes a brand), not_sponsored, footer_only (a vlog or other post that only
-- carries discount codes in its description), unsure.
-- detected_sponsored = what the rules said. verdict = what the person said. sample_kind: 'flagged' (rules said sponsored) or
-- 'unflagged_promo_words' (rules said no, but the text has a promo code / brand-like wording): the second kind estimates misses.

create table if not exists sponsorship_review (
  sample_id          uuid primary key default gen_random_uuid(),
  batch              int  not null,
  position           int  not null,
  sample_kind        text not null check (sample_kind in ('flagged', 'unflagged_promo_words')),
  platform           text not null check (platform in ('youtube', 'instagram')),
  content_id         text not null,
  creator_id         uuid references creators(creator_id) on delete set null,
  creator_name       text,
  title              text,
  snippet            text,
  evidence           jsonb,
  detected_sponsored boolean not null,
  link               text,
  sampled_at         timestamptz not null default now(),
  verdict            text check (verdict in ('sponsored', 'not_sponsored', 'unsure')),
  reviewer           text,
  reviewed_at        timestamptz,
  unique (platform, content_id)
);
create index if not exists idx_sponsorship_review_batch on sponsorship_review (batch, position);
comment on table sponsorship_review is 'Hand check of rule-based sponsorship labels: a stratified sample plus the reviewer verdicts.';
