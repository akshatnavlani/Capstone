-- Evidence type for every sponsorship label (2026-10-14).
--
-- WHY: is_sponsored mixes strong evidence (Instagram's own "Paid partnership" label, #ad) with weaker evidence (a brand
-- name next to a discount code, which shows a commercial relationship but not always a paid sponsorship). GAIL and the paper
-- need to tell them apart: train on the strong labels only, or on all of them, and say which.
--
-- sponsorship_evidence (one value per labelled row, the STRONGEST evidence present; the full list stays in
-- sponsorship_raw_matches):
--   official_label   the platform's own paid-partnership label
--   disclosure_tag   #ad / #sponsored / "sponsored by" / "in partnership with" written by the creator
--   brand_and_code   a known brand together with a discount code or a link
--   brand_mention    a known brand named or @mentioned, no code
--   creator_comment  the creator's own comment on the video carries the brand and code
--   spoken           the brand and code are said in the video (captions)

alter table youtube_videos add column if not exists sponsorship_evidence text;
alter table instagram_posts add column if not exists sponsorship_evidence text;
alter table reddit_posts add column if not exists sponsorship_evidence text;

create or replace function sponsorship_evidence_of(raw jsonb) returns text
language sql immutable as $$
  select case
    when raw is null or jsonb_typeof(raw) <> 'array' or jsonb_array_length(raw) = 0 then null
    when raw ? 'native:paid_partnership_label' then 'official_label'
    when exists (select 1 from jsonb_array_elements_text(raw) e where e like 'spoken:%') then 'spoken'
    when exists (select 1 from jsonb_array_elements_text(raw) e where e like 'comment:%') then 'creator_comment'
    when exists (select 1 from jsonb_array_elements_text(raw) e where e not like 'brand:%' and e not like 'native:%') then 'disclosure_tag'
    when exists (select 1 from jsonb_array_elements_text(raw) e where e like 'brand:%' and (e like '%code%')) then 'brand_and_code'
    when exists (select 1 from jsonb_array_elements_text(raw) e where e like 'brand:%') then 'brand_mention'
    else 'disclosure_tag' end
$$;

update youtube_videos set sponsorship_evidence = sponsorship_evidence_of(sponsorship_raw_matches) where is_sponsored and sponsorship_evidence is null;
update instagram_posts set sponsorship_evidence = sponsorship_evidence_of(sponsorship_raw_matches) where is_sponsored and sponsorship_evidence is null;
update reddit_posts set sponsorship_evidence = sponsorship_evidence_of(sponsorship_raw_matches) where is_sponsored and sponsorship_evidence is null;

create or replace view creator_sponsorship_events as
 select creator_id, brand_id, 'youtube'::text as platform, video_id as content_id, published_at as posted_at, sponsorship_raw_matches, sponsorship_evidence
   from youtube_videos where is_sponsored is true
 union all
 select creator_id, brand_id, 'instagram'::text, post_id, posted_at, sponsorship_raw_matches, sponsorship_evidence
   from instagram_posts where is_sponsored is true
 union all
 select creator_id, brand_id, 'reddit'::text, post_id, posted_at, sponsorship_raw_matches, sponsorship_evidence
   from reddit_posts where is_sponsored is true;
