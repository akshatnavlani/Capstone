# Data for training and testing (state on 2026-10-14)

Everything lives in the shared Supabase Postgres database; nothing needs exporting. Read it with `DATABASE_URL`
(`backend/.env`, never committed). Tables below are new or changed since 2026-10-11. All timestamps are UTC.

## Who is in the data
| Table | What |
|---|---|
| `creators` | every creator (`creator_id` is the key that joins YouTube, Instagram and Reddit rows) |
| `creator_verification` | the verified fitness list: 168 rows, **149 collectable** (`link_level` confirmed or probable, `creator_id` not null). `sponsor_group` A = brand code or tag seen in the bio; B = none seen. `ig_handle`, `yt_handle`, `yt_channel_id`. |
| `brands`, `creator_brand_links` | 80+ brands; which creator promotes which brand (about 180 pairs), with the evidence text |

## Sponsorship labels (the GAIL examples)
`creator_sponsorship_events` (a view): one row per labelled post: `creator_id, brand_id, platform, content_id, posted_at,
sponsorship_raw_matches, sponsorship_evidence`. About 750 rows, 84 creators, 700 with a brand.
`sponsorship_evidence` says how strong the evidence is (use it to choose strict or loose training labels):
`official_label` (Instagram paid-partnership label) > `spoken` > `creator_comment` > `disclosure_tag` (#ad, sponsored by) >
`brand_and_code` (known brand beside a discount code) > `brand_mention`. Posts tagged `promo_code_only` (about 150) are NOT in
the view: they have a code but no known brand.
**Caveats:** labels are produced by rules (`scripts/ingestion/sponsorship_detector.py`), not by people. A hand check
(`sponsorship_review`, 99 items, 62 checked one by one) found: when the rules say sponsored they were right 48 of 48; about 43% of
code-only posts they skipped were real ads, so the labels under-count. Many events sit on a few creators (top 10 creators hold
about 59%). Do not split train/test by post: split by `creator_id`.

## Posts, comments and growth
| Table | What |
|---|---|
| `youtube_videos` (21K), `youtube_comments` (198K), `youtube_channels` | exact `published_at`, `duration_seconds`, counts; comments for each creator's newest 30 videos |
| `instagram_posts`, `instagram_comments`, `instagram_profiles` | posts since 2026-10-12 have `thumbnail_url`, exact `posted_at`, `has_paid_partnership_label`; comments have `posted_at`. Older rows (1,811) have none of these and mostly belong to other kinds of creators. Follower counts are rounded ("105K"); some creators hide likes. |
| `reddit_posts`, `reddit_comments`, `reddit_post_creators` | posts found by creator-name and brand searches in r/indianfitness and r/Fitness_India; comments from 2026-10-14 have exact `posted_at`. Reddit is mostly about brands, rarely about single creators. |
| `post_snapshots`, `profile_snapshots` | growth readings: one row per post (or account) per reading, `fetched_at` minus the post's time = its age. YouTube every 2 hours (Supabase timer `youtube_snapshots`, log in `snapshot_job_log`), Instagram a few times a day. Started 2026-10-11, so full first-24-hour curves exist only for posts published since then. |

## What is NOT ready yet
Instagram covers 26 of the 149 creators; cross-platform lag analysis needs about 4 weeks of readings (until mid-November);
new creators have no graph links or CLIP/BERT embeddings yet; spoken sponsors are not detected.

## Handy queries
```sql
-- strict labels only
select * from creator_sponsorship_events where sponsorship_evidence in ('official_label','disclosure_tag','brand_and_code');
-- a creator's posts on both platforms in time order
select 'youtube' p, published_at t, title from youtube_videos where creator_id = :id
union all select 'instagram', posted_at, left(caption, 80) from instagram_posts where creator_id = :id order by t;
-- growth curve of one post
select fetched_at, view_count, like_count, comment_count from post_snapshots where post_id = :post order by fetched_at;
```
