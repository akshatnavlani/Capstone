-- Hand check of the sentiment scorer on Hindi, Hinglish and English comments (2026-10-22).
--
-- WHY: the sentiment model is trained on English. About 1% of our comments are in Devanagari and many more are Hindi written in
-- Roman letters ("Hinglish"), which an English model reads as nonsense. A person labels a sample of each kind, and the model's score is
-- compared with the labels per language. The model's own score is NOT shown to the reviewer (it would bias the answer); it is stored
-- here only so the comparison needs no second lookup.
--
-- verdict: 'positive', 'negative', 'neutral' (no feeling, or a question), 'unclear' (cannot tell, or not about the creator/video).

create table if not exists sentiment_review (
  sample_id    uuid primary key default gen_random_uuid(),
  batch        integer not null,
  position     integer not null,
  language     text not null check (language in ('english', 'hinglish', 'devanagari')),
  platform     text not null check (platform in ('youtube', 'instagram', 'reddit')),
  comment_id   text not null,
  creator_id   uuid,
  comment_text text not null,
  model_score  double precision,
  sampled_at   timestamptz not null default now(),
  verdict      text check (verdict in ('positive', 'negative', 'neutral', 'unclear')),
  reviewer     text,
  reviewed_at  timestamptz,
  unique (platform, comment_id)
);
create index if not exists idx_sentiment_review_batch on sentiment_review (batch, position);
comment on table sentiment_review is 'Human labels of comment sentiment by language, to validate the English-trained scorer on Hindi and Hinglish.';
