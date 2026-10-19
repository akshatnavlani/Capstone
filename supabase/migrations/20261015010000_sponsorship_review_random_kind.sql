-- Hand-check round 2 (2026-10-15): a third kind of sample.
--
-- WHY: round 1 sampled flagged posts and unflagged posts WITH promo words. That says nothing about ads the rules
-- missed on posts with no promo words at all. 'unflagged_random' = a random post the rules did not flag and that has no
-- promo words, so the share of real ads among them estimates the overall miss rate.

do $$
declare c record;
begin
  for c in select conname from pg_constraint
           where conrelid = 'sponsorship_review'::regclass and contype = 'c' and pg_get_constraintdef(oid) like '%sample_kind%'
  loop
    execute format('alter table sponsorship_review drop constraint %I', c.conname);
  end loop;
end $$;

alter table sponsorship_review add constraint sponsorship_review_sample_kind_check
  check (sample_kind in ('flagged', 'unflagged_promo_words', 'unflagged_random'));
