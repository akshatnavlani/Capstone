# Joint-video spillover: plan fixed before any effect was computed (9 Nov 2026)

Agreed with Shimona on 9 Nov 2026 ("one best idea"). Written before any effect, placebo or per-event number of this test
was computed. Already known when writing: a rough count of full-name mentions of held creators in other creators'
YouTube titles (379 events in 730 days, counted only, no outcome looked at). Every earlier test stays reported as it is.

## Why this test
Every earlier test used a weak link (an @tag, a shared sponsor). In a joint video A's audience actually sees B.
Koch et al. (2018): YouTube collaboration videos brought both channels gains within days, mostly channels under 100k.

## Events (identity rule only, from titles)
- A joint video = a YouTube video by creator A (in scope, creator rule with data/creator_scope_overrides.csv), published
  in the 730 days before 9 Nov 2026, whose TITLE names a held in-scope creator B != A together with a collaboration
  marker: "ft", "ft.", "feat", "feat.", "featuring", "with", "x", "×", "&", "vs", "and", "collab" directly before B's name,
  or "x", "×", "&" directly after it; or B's @handle anywhere in the title.
- B's name = the creator name without any bracket part, lower case, at least 2 words and 8 letters, not a club/team/
  league/brand-like word ("fitness", "official", "fc", "club", "team", "league", "cricket", "tv", "yoga", "india"); B's
  handles (YouTube or Instagram, 6+ letters) also count.
- Only the first joint video of (A, B) within 30 days. B must have YouTube videos.

## Measure (data already held: views and likes of B's own videos)
- B's videos at least 14 days old on 9 Nov 2026; engagement = log(views + likes + 1) minus B's own median for videos of the
  same kind (Short <= 180 s, or long).
- B's videos whose title names A (B's own upload of the same collaboration) are left out of both windows.
- Effect per event = mean over B's videos in the 14 days after the joint video minus mean over B's videos in the 30 days
  before. An event counts with at least 1 video on each side.
- Placebo: B's own random times in the same 730 days with no joint video involving B within 30 days, 5 per event, seed 0.

## Test and pass mark
- Primary: all counted events. DETECTED only if the 95% interval of the mean effect (bootstrap over (A, B) pairs, 2,000
  draws, seed 0) is above 0 AND the placebo interval includes 0. Fewer than 20 counted events: printed, not a result.
- Secondary (pre-specified, reported separately, same pass mark): B with under 100,000 subscribers.
- Also printed, not a pass mark: the host A's own videos, the same calculation (does the host gain too?).

## Not allowed
Changing markers, windows, thresholds or the creator list after seeing numbers; re-running until something passes.
Creators added after this plan was written (16 added on 9 Nov evening) are included only if they were in the database
when the test is run, which is once.
