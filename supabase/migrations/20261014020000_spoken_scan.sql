-- Videos scanned for SPOKEN sponsors (2026-10-14).
--
-- WHY: many creators write nothing in the description and say the sponsor and code out loud. scripts/ingestion/spoken_scan.py
-- reads a video's auto-captions (youtube-transcript-api, no quota) and records here what it found. YouTube blocks caption
-- requests after about 10-20 in a row, so the scanner works in small batches and every result is saved at once; a re-run
-- skips videos already scanned.
--
-- evidence: ['spoken:brand:NAME(code)', 'spoken:disclosure:<phrase>'] as produced by spoken_sponsor.spoken_evidence.
-- Nothing here changes is_sponsored by itself: a person checks a sample of the hits before they become labels.

create table if not exists spoken_scan (
  video_id      text primary key references youtube_videos(video_id) on delete cascade,
  scanned_at    timestamptz not null default now(),
  has_captions  boolean not null,
  language      text,
  characters    int,
  evidence      jsonb not null default '[]'::jsonb
);
create index if not exists idx_spoken_scan_hits on spoken_scan (scanned_at) where jsonb_array_length(evidence) > 0;
comment on table spoken_scan is 'Videos scanned for spoken sponsors from their captions; evidence lists what was found.';
