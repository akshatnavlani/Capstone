# Older-period replications of four spillover tests (plan fixed 14 Nov 2026, 22:20, before any event list or outcome)

Agreed with Shimona (14 Nov: "do it by 21, find all the things"). The 2022-2024 YouTube history now exists for 365 of 381
in-scope channels, so four tests that were NOT detected on Nov 2024 - Nov 2026 can be repeated, unchanged, on the
non-overlapping period Nov 2022 - Nov 2024.

## Tests (same code, same rules and pass mark as the original plans; only the end date moves back two years)
| Test | Original plan | New end date | Extra data needed |
|---|---|---|---|
| Joint video: A and B in one video -> B's engagement | JOINT_VIDEO_SPILLOVER_PLAN_9NOV.md | 9 Nov 2024 | none |
| Audience flow (Test 1): A's commenters move to B after A tags B | AUDIENCE_FLOW_PLAN_8NOV.md (replication settings) | 9 Nov 2024 | comments, up to 300 per video |
| Brand spillover: A promotes brand X -> B's comments name X | BRAND_SPILLOVER_PLAN_8NOV.md | 8 Nov 2024 | comments |
| Sponsor carry-over: brand named on the creator's next videos | SPONSOR_CARRYOVER_PLAN_9NOV.md | 9 Nov 2024 | comments |
Not repeated: sponsored post on one app -> the creator's other app (needs 2022-2024 Instagram data, which does not exist).

Implementation: each script reads its end date from the environment variable SPILL_NOW (default unchanged) and adds the
suffix SPILL_TAG ("older") to its output files, so the original result files are never overwritten.

## Data step
Comments for the videos each test lists (its own "videos" / "placebo-videos" mode, run with SPILL_NOW), fetched with
scripts/ingestion/youtube_comments_backfill.py --video-ids-file, at most about 4,000 units a day (shared key), 15-19 Nov.
If a list cannot be fetched in time, that test is reported as "not run (data)" rather than run on partial comments.

## Rules
- Each test runs once, after its data step; results reported whatever they are, next to the original runs.
- Multiple testing, stated in advance: this adds four tests to about fifteen already run. With that many tests at the
  0.05 mark, about one pass is expected by chance alone, so a single pass here is reported as "suggestive, needs
  confirmation", not as a finding on its own.
- No change to windows, thresholds or events after any number is seen. No further spillover tests before 21 Nov
  except the two forward tests already planned for 20 Nov.
