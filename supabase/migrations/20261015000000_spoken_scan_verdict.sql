-- Her check of the spoken-sponsor hits (2026-10-15).
--
-- WHY: spoken_scan only records what the caption scanner heard. A person listens to each hit and says whether the
-- video really is sponsored. The verdict is stored here, next to the hit, so the labels written from it can always be
-- traced back to who checked what and when.
--
-- verdict: 'yes' = sponsored or promoting the brand, 'no' = not an ad (for example only names the equipment used),
--          'unsure' = could not tell. Only 'yes' hits become sponsorship labels (evidence type 'spoken').

alter table spoken_scan add column if not exists verdict text check (verdict in ('yes', 'no', 'unsure'));
alter table spoken_scan add column if not exists reviewer text;
alter table spoken_scan add column if not exists reviewed_at timestamptz;
comment on column spoken_scan.verdict is 'Human check of the hit: yes / no / unsure. Only yes becomes a label.';
