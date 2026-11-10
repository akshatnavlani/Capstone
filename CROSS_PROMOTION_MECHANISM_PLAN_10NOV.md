# Cross-promotion mechanism test for the detected cross-platform spillover: plan fixed before any number (10 Nov 2026, ~19:15 IST)

Agreed with Shimona on 10 Nov 2026 ("spillover try to find"). Written before the split below was computed. Adds to, and
does not replace, the detected result (scripts/run_platform_pairs.py, models/platform_pairs.json: Instagram posts ->
comments on the same creator's YouTube videos older than 72 h, 90 creators, F 1.484, placebo p 0.002). Every earlier
result stands.

## Question
If the detected link is audience moving from Instagram to the same creator's YouTube, it should be STRONGER for creators
who point their Instagram audience to YouTube in their captions. If it is equally strong for creators who never mention
YouTube, the link is more likely a shared rhythm (busy weeks on both platforms) than audience flow.

## Groups (identity only, fixed by this rule)
Same creators and data as the detected test (run_platform_pairs.load and build_series, comments on videos older than
72 h, last 365 days, creators with >= 5 Instagram posts). Per creator: share of their Instagram captions matching
`youtube|you tube|\byt\b` (case-insensitive). PROMOTERS = share above the median of these creators; OTHERS = the rest.
Secondary split (other direction): share of their YouTube video texts (title + first 400 characters of description)
matching `instagram|\binsta\b`; median split the same way, used for the YouTube comments -> Instagram posts direction.

## Measure and test
- Pooled Granger F (lags 1-3, creator mean removed; run_platform_pairs.granger_f, unchanged) computed in each group.
- PRIMARY: difference F(promoters) - F(others) for Instagram posts -> old-video YouTube comments. p = share of 2,000
  random relabellings of creators into groups of the same sizes (seed 0) with a difference at least as large.
  MECHANISM SUPPORTED only if p < 0.05 AND the promoters' own Granger p (500 circular shifts, seed 5, as in the
  detected test) is < 0.05.
- SECONDARY (same rule): the YouTube-description split, YouTube comments -> Instagram posts direction.
- Also printed: the detected test re-run on today's data (all 90+ creators), as an update, not a new test.
- Fewer than 15 creators in a group: printed, not a result.

## Not allowed
Changing the word lists, the median split, the lag count or the windows after seeing numbers; running again until it
passes. Run once; the result is reported whatever it shows, beside every other spillover result.
