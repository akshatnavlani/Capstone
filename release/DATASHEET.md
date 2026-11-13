# Indian Fitness and Health Creator Network: datasheet (release candidate, 14 Nov 2026)

Built by `scripts/export_release_dataset.py` from the project database. **Not yet published**; publishing is a team decision.

## What it is
Public engagement data for 651 Indian fitness and health creators (512 in the study's scope) on YouTube and Instagram, with
dated sponsorship labels, links between creators, and creator-to-creator tag events. It supports the spillover analyses of
the paper "GAIL-R: Testing Sponsorship Spillover on Multi-Platform Creator Networks with Placebo-Penalised Orthogonal Learning".

| File | Rows | One row is |
|---|---|---|
| creators.csv | 651 | a creator: category, in scope (0/1), has YouTube / Instagram data, subscriber band |
| youtube_videos.csv | 244,746 | a video: creator, publish date, Short (<= 180 s), views, likes, comments, sponsored (0/1), evidence tier, brand category |
| instagram_posts.csv | 3,322 | a post: creator, date, media type, likes, comments, sponsored, paid-partnership label, evidence tier, brand category |
| edges.csv | 1,170 | a creator pair: `collaborates_with` (listed related accounts) or `co_occurs_with` (discussed in the same Reddit post), with a weight |
| tag_events.csv | 441 | creator A tagged creator B (@handle) on a date: the events of the pre-registered tag study |

## How it was collected
YouTube Data API v3 (channels, videos, statistics; history back to November 2022 for in-scope channels), Instagram through a
read-only browser extension within about 130 page loads a day per account, Reddit public page JSON. Only public data was read;
no account was followed, liked or messaged. Counts are as read on 13-14 Nov 2026 (views and likes keep growing after that).

## Sponsorship labels
Rule-based detector in six evidence tiers (official label, spoken, creator comment, disclosure tag, brand and code, brand
mention); a creator's repeated footer lines are ignored. Strong tiers were correct in 73 of 75 hand-checked events; weak tiers
are less reliable. `sponsorship_evidence` gives the tier.

## Anonymisation
Names, handles, channel / video / post ids, titles, descriptions, captions, comments, thumbnails and brand names are removed.
Creators, videos and posts are keyed by salted SHA-256 hashes; the salt is not released. Subscriber counts are given only as a
band. The creators are public figures and their counts are public, so re-identification by matching dates and counts is
possible in principle; the release is meant for research on aggregate patterns, not on individuals.

## Known limits
Instagram coverage is thin (3,322 posts). Engagement is not sales. Labels are rules, not ground truth. Creator scope (Indian,
fitness and health) is a hand rule recorded in data/creator_scope_overrides.csv.
