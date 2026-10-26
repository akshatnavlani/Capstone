# Data-collection handoff for GAIL (branch review2-shimona-temporal)

Numbers read from the live Supabase database and the code on 26 Oct 2026, ~18:40 IST. "Core 150" = `creator_verification` rows with link_level confirmed/probable (150 creators; 116 fitness, 23 adjacent, 11 famous-general).

## 1. Sources and collectors
| Script / job | Platform | Schedule | Writes |
|---|---|---|---|
| `snapshot_youtube.py` (Supabase pg_cron `youtube_snapshots`) | YouTube Data API: new uploads + videos < 7 days old | every 2 h at :17 (156 runs since 13 Oct, 1 with errors) | `youtube_videos`, `post_snapshots`, `snapshot_job_log` |
| `instagram_daily.py` (Windows Task Scheduler `CapstoneInstagramDaily`) | Instagram via OpenCLI/Chrome, read-only | daily 12:00 IST, cap 130 page loads/UTC day | `instagram_posts`, `instagram_profiles`, `post_snapshots`, `instagram_daily_runs`, `instagram_extra_loads`, `instagram_collect_failures` |
| `instagram_backfill_counts.py` (inside the daily job, up to 25 loads/day) | Instagram old posts: counts + owner check | daily from 27 Oct | `instagram_posts` |
| `youtube_backfill_history.py` | YouTube API, 24 months | manual, one-off (done 26 Oct) | `youtube_videos` |
| `orchestrator.py` | YouTube comments, Instagram comments | manual | `youtube_comments`, `instagram_comments` |
| `reddit_collect.py` | Reddit (r/indianfitness, r/Fitness_India) | manual; last run 21 Oct | `reddit_posts`, `reddit_comments`, `reddit_post_creators`, `reddit_search_log` |
| `spoken_scan.py`, `comment_sponsor_pass.py`, `sponsorship_detector.py` | YouTube captions / creator comments / text | manual label passes | `spoken_scan`, `is_sponsored` + `sponsorship_evidence` columns |
| `score_sponsorship_events.py` | n/a | manual | `sponsorship_event_scores` |

## 2. Creator selection
Fixed, hand-curated list (hashtag discovery -> human review in a sheet -> `promote_candidates.py`). **No snowball sampling.** Scope (India + fitness) is by human curation only; there is no automatic country/topic filter.
| | Count |
|---|---|
| `creators` rows | 390 (202 fitness_influencer, 95 athlete, 49 lifestyle, 44 team/league/other) |
| Creators with YouTube videos / Instagram posts / Reddit posts | 179 / 119 / 129 |
| Core 150 with YouTube / Instagram / Reddit data | 149 / 78 / 18 |
| YouTube channels with country = IN | 137 of 179 (25 unknown, 17 other) |
| Snowball check (26 Oct, 623 listed collaborators not in `creators`) | 281 have a same-handle YouTube channel; 30 confirmed the same account; 0 are Indian fitness creators (brands, celebrities, organisations). Not added. |

## 3. Collaboration links
Detected: (a) Instagram collab co-author header (`collab_edges.py`); (b) 880 `frequent_collaborator` entries in `creator_related_accounts`; (c) Reddit posts naming two creators (co-occurrence); (d) NEW 26 Oct: two creators with a sponsored post for the same classified brand ("shared brand"). **Not done:** `@mention` / "ft." parsing of YouTube titles/descriptions, tagged accounts, comment-based links.
| Links among the core 150 | Before | Now |
|---|---|---|
| Creators with any graph link | 17 | 80 (shared brand alone: 65) |
| Directed collaboration edges (whole table) | 354 | 354 (unchanged; only 7 of 880 listed collaborators are inside the 150) |
| Shared-brand edges (directed, new) | 0 | 1,212 |
| Training pairs (event, neighbour, lift) | 88 collaboration | 88 + 16,072 shared-brand rows = 153 independent observations from 70 neighbours |

## 4. Sponsorship detection
Rules in `sponsorship_detector.py`: Instagram paid-partnership label (51 posts have it), known brand + code/@mention/disclosure tag, explicit tag, creator's own comment, spoken scan of captions. **YouTube's "includes paid promotion" flag is not available through the API and is not used.**
| | Count |
|---|---|
| Flagged events (YouTube / Instagram / Reddit) | 1,745 / 127 / 4 (1,871 with a creator) |
| Events with a brand (1,871 with creator) | 1,679 (72 brands) |
| Strong evidence (label, tag, spoken, creator comment) | 360 of 1,876; weak (brand name / brand + code) 1,516 (81%) |
| Checked by a person, one by one | 62 review rows + 33 spoken hits (a further 37 review rows were marked "assumed / not checked" and 45 spoken 'yes' were approved without checking: all left out). 100 more queued (batch 11) |
| Accuracy of flagged events | 73 of 75 checked one by one = 97% (95% interval 91-99%), but that is 4% of events. Claude's text-only readings of 113 weak-tier events find only 61% (52-70%) look sponsored from the description alone (it cannot hear spoken sponsors): the weak-tier precision is somewhere between about 60% and 95% |
Caveat: earlier versions of this report quoted 91%; that mixed in rows marked "assumed" and earlier Claude drafts and is retracted. No random sample of unflagged videos was checked by a person, so the miss rate is unknown (the promo-word sample Shimona checked had 6 real ads among 19 decided).

## 5. Engagement history
| | Earliest - latest | Per-post snapshots |
|---|---|---|
| YouTube (core 150, 59,281 videos) | 20 Dec 2023 - 26 Oct 2026 (all 61,265: from Sep 2020) | 260,874 readings of 60,015 videos since 11 Oct, every 2 h for videos < 7 days old; 2,671 videos have 3+ readings |
| Instagram (core 150, 1,021 posts) | 20 Feb 2024 - 26 Oct 2026 | 1,254 readings of 909 posts since 12 Oct, about daily; 61 posts have 3+; 403 posts lack like/comment counts |
| Reddit (3,308 posts) | 25 Jan 2023 - 21 Oct 2026 | none |
Only 15 days of growth readings exist, so no long-term growth curves.

## 6. Reddit
3,308 posts from 24 subreddits (large share is Cricket/NBA, not fitness), 61,570 comments (6,608 with a time). Posts link to creators via `reddit_post_creators` using strict alias matching (full name, nickname, handle of 6+ characters): 3,406 links, 129 creators (only 18 in the core 150). Sentiment: `cardiffnlp/twitter-roberta-base-sentiment-latest` (English-trained). Check on 120 comments (40 per language) against Claude's labels, NOT human ground truth: Spearman with label English +0.77, Hinglish +0.47, Devanagari +0.33 (`scripts/check_sentiment_labels.py`); human labels still pending. Reddit talks about brands far more than about single creators.

## 7. Data quality
- Instagram: 78 of 150 creators have posts; 403 of 1,021 posts have no counts; 4 failure rows (3 creators; 2 skipped on purpose); daily cap 130 loads; Instagram throttles automation (stop at first block); foreign posts detached with backup table.
- YouTube: 0 duplicate videos, 0 missing views; 1 of the core 150 has no videos (149 of 150 have); Hindi/Hinglish sentiment weak (see section 6); quota 10,000 units/day.
- Labels: weak tiers dominate (81% of events); their true precision is uncertain, between about 60% and 95% (see section 4); false positives are mostly a creator's own discount code in a vlog.
- Reddit comment times only for 11%; Reddit last run 21 Oct.
- Brand cleanup: 28 wrong brand attachments removed 25 Oct; 37 events had brands without a category.
- Duplicates: 0 duplicate post ids; 0 duplicate creator names.

## 8. Plan
| What | When |
|---|---|
| YouTube 2-hourly snapshots | running; keep going |
| Instagram daily job incl. count filler (~342 old posts) | daily 12:00 IST; about 14 days |
| Reddit refresh | about 28 Oct (manual) |
| Lag re-tests (more readings) | about 29 Oct and 8-10 Nov |
| Hand-check batch 11 (100 events) | waiting on Shimona |
| Snowball sampling / `@mention` and "ft." collaboration parsing | not started; needs scraping time |
