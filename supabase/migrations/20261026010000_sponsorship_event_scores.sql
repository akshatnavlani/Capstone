-- Probability that a detected sponsorship event is a real ad (2026-10-26).
--
-- WHY: only about 10% of the detected sponsorship events were ever checked by a person. scripts/score_sponsorship_events.py learns from those checks
-- (ml/sponsorship_quality.py) and stores one probability per event here, with the model version. Nothing reads this table to change labels or training data
-- yet: it is for reporting and for an optional probability filter that has to be chosen explicitly.

create table if not exists sponsorship_event_scores (
  content_id    text        not null,
  platform      text        not null check (platform in ('youtube', 'instagram', 'reddit')),
  p_ad          real        not null check (p_ad >= 0 and p_ad <= 1),
  model_version text        not null,
  scored_at     timestamptz not null default now(),
  primary key (content_id, platform)
);
comment on table sponsorship_event_scores is 'Model probability that a detected sponsorship event is a real ad; learned from human-checked rows, scored on unseen creators.';
