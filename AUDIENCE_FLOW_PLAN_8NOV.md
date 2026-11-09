# Collaboration spillover on past data: two tests, plan fixed before any data (8 Nov 2026)

Agreed with Shimona on 7 Nov 2026. Written on 8 Nov before the comments for these tests had been collected and
before any number was computed. Separate questions from the sponsorship-spillover test (SPILLOVER_RESULTS_7NOV.md:
not detected) and from the forward subscriber study (COLLAB_SPILLOVER_PLAN_7NOV.md). Every result is reported.

## Events (fixed list, built 7 Nov from identity rules only)
models/audience_flow_events_7nov.json: 159 events, 108 creator pairs. An event = a YouTube video or Instagram post by
creator A whose title, description or caption has the @handle of a held creator B, published in the last 365 days;
only the first tag of B by A within 30 days; B in scope (creator rule with data/creator_scope_overrides.csv); A and B
both have YouTube videos. Comments: models/audience_flow_videos_7nov.txt (A's top 5 videos by comment count in the
60 days before the tag; B's top 5 in the 30 days before and top 5 in the 30 days after), fetched with
scripts/ingestion/youtube_comments_backfill.py --video-ids-file (up to 100 comments per video, by relevance).

## Test 1 (primary of this plan): audience flow
- A's audience = distinct comment authors on A's videos in the 60 days before the tag.
- Share before = share of B's distinct commenters in the 30 days before the tag who are in A's audience.
  Share after = the same for the 30 days after. Effect per event = share after - share before.
- An event counts only if B has at least 20 distinct commenters on each side.
- Placebo: for the same (A, B), the same calculation at 5 random times in the past 365 days with no tag between A
  and B within 45 days of that time.
- Pass mark: DETECTED only if the 95% interval of the mean effect (bootstrap resampling creator pairs) is above 0
  AND the placebo interval includes 0. Fewer than 20 counted events: printed, not a result.

## Test 2 (secondary): short-window engagement of B
- B's YouTube videos at least 14 days old; engagement = log(views + likes + 1) minus B's own median for videos of the
  same kind (Short or long).
- Effect per event = mean over B's videos in the 7 days after the tag minus mean over B's videos in the 30 days before.
- Placebo: B's own random times with no tag of B within 30 days (5 per event).
- Same pass mark and bootstrap; fewer than 20 counted events: printed, not a result.

## Placebo times (fixed 8 Nov, before any result)
scripts/audience_flow_test.py draws the placebo times once with seed 0 (Test 1) and seed 1 (Test 2); the videos the
Test 1 placebo needs are in models/audience_flow_placebo_videos_8nov.txt and get comments the same way.

## Replication (added 8 Nov 2026, before any result of this plan was computed)
The same two tests, same rules and pass mark, repeated on a larger set: tag events from the last 730 days instead of
365 (the YouTube history held reaches about 2 years), and comments up to 300 per video (3 pages) instead of 100.
Run after the first run, on the next quota day. Both runs are reported; the replication does not replace the first.

## Not allowed
Changing windows, thresholds or the event list after seeing results; re-running until something is significant;
reporting Test 2 or any subgroup as the main finding. Limits stated with the result: comments are the top 100 per
video by relevance, not all comments; handles can change; a tag is not always a joint video.
