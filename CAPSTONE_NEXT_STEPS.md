# CAPSTONE — NEXT STEPS & LIVING STATE

**Read this first, every session.** This is the orchestrator's single source of truth for where
the project actually is, what's broken, and what remains between here and the thesis. It
supersedes memory when they disagree — memory is a pointer, this is the record.

Last verified: **2026-09-24** (re-scope only, no live DB re-query — Review 1 closed state unchanged: 259/54/170 wired end-to-end, see §1 Review 1 closed. Team decision 2026-09-24: Review 2 = pipeline-complete per PendingWork 2026-09-20; Review 3 = improvements).

**Update 2026-10-13 late (growth timer moved into Supabase):** GitHub Actions' schedule ran only 4 times in ~24 h (every 7-9 h, not every 2 h), so the first-24-hours growth schedule now runs inside Supabase: migration `20261013010000_youtube_snapshot_timer.sql` (extensions `http` + `pg_cron`, function `public.snapshot_youtube_run()`, log table `snapshot_job_log`), pg_cron job `youtube_snapshots` at minute 17 of every 2nd hour (UTC), API key in the vault (secret `youtube_api_key`, function not executable by anon/authenticated). First test run: 82 s, 177 channels, 52 new uploads, 779 snapshots, 2 chunks lost to a deadlock because the GitHub job was writing at the same time (consider disabling the GitHub schedule to avoid collisions). New uploads get no brand/sponsorship label from the timer: re-run apply_sponsorship afterwards. Hand check of the sponsorship rules finished (99 items, 62 checked one by one): flagged ones right 48/48; of unflagged posts with promo-code words about 43% (6 of 14) were real ads, so recall is the weak side.

**LATE 26 OCT (14:00-15:00 IST), after extending YouTube history and re-labelling: three results CHANGED, read these before the older notes below.** (1) Data: YouTube videos of the 150 went from 21,143 to 59,232 (history now about 24 months, `scripts/ingestion/youtube_backfill_history.py`, 3,054 quota units, no brand guessing); the label pass then found 970 more sponsored YouTube videos and 9 Instagram posts: sponsorship events with a creator 892 -> 1,871 (109 creators, 356 with strong evidence, 81% are the weaker brand-name/promo-code tiers), no stray brands created. (2) Training examples: shared-brand rows 16,053 -> 153 independent observations from 70 neighbours (was 118 / 55); links: shared-brand alone connects 65 of the 150, with the existing links 80 (was 67). SIMULATED VALIDATION ON TOP OF THE REAL DATA (27 Oct ~03:00 IST; everything labelled SIMULATED, reads the real data, writes only local JSON in models/, never touches the database or any real result; real scraping unaffected): (1) `scripts/sim_semisynthetic_benchmark.py` -> `models/sim_semisynthetic_benchmark.json`: real shared-brand rows (10,641 from 65 neighbours) with a planted spillover effect and a planted pre-existing trend (normal 0.15 +/- 0.15 per neighbour). NAIVE analysis (lift after the post above zero?) is off by +0.38 at every effect size and 'detects' an effect in 100% of simulated studies even when the true effect is 0; the PLACEBO test used on the real data (Test A) is off by -0.05, has 0% false alarms, and detects a planted 0.10 in 48% of studies and 0.25 or more in 100%. LIMIT: if the effect reaches only 20% of neighbours the placebo test (median over neighbours) misses it (detects an average effect of 0.20 in 6%). So the real result of about 0 rules out a BROAD spillover of 0.25 or more, not a localised one. Neural GAIL is not in this table (needs a retraining run; scripts/gail_acceptance.py failed 0 of 4 on 26 Oct). (2) `scripts/sim_lag_power.py` -> `models/sim_lag_power.json`: extra attention planted 12-36 h after each REAL Instagram post on the real YouTube growth readings. All-posts test (294 units, 55 creators): 0% false alarms, finds +10% of a normal day in 7/8 plantings, +15% 8/8; strict test (65 units, 29 creators): +15% in 4/8, +25% in 8/8. So 'no lag confirmed' in 15 days of readings rules out a large delayed effect only. Dashboard: two SIMULATED cards on the Analysis tab (S9). RULE KEPT: simulated data is never added to the training set or the database; it is validation only. Tests: tests/test_direct_effect_ranking.py 6 pass. DOSE-RESPONSE (27 Oct, `scripts/run_spillover_dose.py`, `models/spillover_dose.json`): does a stronger shared-brand tie (more shared brands) show more neighbour lift than at placebo dates? Mature rows 10,641. 1 shared brand: -0.053 [-0.110, +0.021] (65 neighbours); 2: -0.055 [-0.301, +0.160] (29); 3 or more: -0.108 [-0.231, -0.058] (19); trend over 63 neighbours Spearman -0.05 [-0.28, +0.19]. NO dose-response, so weighting links by strength is not supported by the data and the link weights were left as they are. Also measured: name-based collaborations in titles ('ft. Name', 'x Name') add only about 7 reliable pairs inside the 150 (words like 'vs' and 'with' pick up plain mentions), not added. TWO POSTS UNFLAGGED (27 Oct ~10:00 IST, Shimona said yes; `scripts/ingestion/unflag_two_posts_20261027.py`, `--undo` available, backup table `sponsor_flip_backup_20261027`): youtube pcxTYVgflpc (description says 'Not a paid promotion') and tUkIMp4SMnE (joke title) are now is_sponsored = false; recorded in sponsorship_review as not_sponsored by 'Shimona (said yes to Claude's recommendation ...; not checked one by one)'; removed from sponsorship_event_scores. Events now 1,874. OPEN: 17 of the 45 spoken-scan 'yes' labels of 24 Oct carry only a bare Hindi word (sponsor/promotion); 28 are brand + code said aloud (reliable). Plan: after the running scan finishes, fetch the captions of those 17 and read the sentence around the keyword, give Shimona a list; flip nothing without her yes. INSTAGRAM COUNTS BACKLOG (27 Oct ~09:00 IST): 403 of 1,021 Instagram posts of the 150 have no like/comment counts, and each needs its own page load (cap 130 per UTC day for everything). `BACKFILL_LOADS_PER_DAY` raised from 25 to 60 in `scripts/ingestion/instagram_daily.py` (the reserve is now at most half of the day's budget, was a third; tests updated, 120 ingestion tests pass), so the 12:00 job spends up to 60 loads on the oldest-priority posts (sponsoring creators and shared-brand neighbours first) and the rest on refreshing young posts. About 7 daily runs clear the backlog if the laptop is on with Chrome open at 12:00 each day; put the constant back to 25 once fewer than about 50 posts are left. Not pushed yet. UNLINKED-CREATORS FIX (27 Oct ~02:40 IST): of the 59 core creators with no graph link, 49 had NO sponsorship event at all (22,641 videos, only 29 ever scanned for spoken sponsors) and 10 had 22 real sponsored posts (official label / #ad) with no brand identified. `scripts/ingestion/assign_missing_brands_20261027.py` (applied, backups `brand_assign_backup_20261027` and `brand_category_backup_20261027`; never touches is_sponsored): 17 posts given the brand named in their own text, 12 new brands, 25 previously unclassified brands classified (7 marked not_a_brand: a person, an event, a club, own channels, a broken name; others `consumer_other` = real brand outside the fitness categories). Effect: core creators with any link 91 -> 95 (Sanjay Duseja, Tanmay Bhat, Dr Ambika Dutt, Mukti Gautam). Two posts that look sponsored but are not are listed for Shimona's decision (labels unchanged): youtube pcxTYVgflpc ('Not a paid promotion') and youtube tUkIMp4SMnE (joke title). `spoken_scan.py --no-event-creators N` STOPPED on purpose at 8 of 233 videos (02:50 IST, laptop cannot stay on overnight; every scanned video is saved in `spoken_scan`, a re-run skips them). TO RESUME on the morning of 27 Oct, laptop on and awake for about 5 hours: `cd scripts/ingestion; python spoken_scan.py --no-event-creators 3 --limit 400` (the latest 3 long videos of each creator with no sponsorship event, about 175 videos, about 37 an hour, about 4.7 hours; no Chrome needed so it can overlap the 12:00 Instagram job). When it finishes: label pass for new spoken hits (needs the detector flow used on 26 Oct), re-export training inputs, copy into exports/training_inputs_26oct. **CORRECTION 27 Oct ~01:30 IST (supersedes every '91%' / '117 of 128' / '179 checked' / '0 of 24' figure in this file, the report, the dashboard card and the earlier chat): those mixed human checks with other rows.** `sponsorship_review` reviewer values: 'Shimona' 62 (checked one by one), 'Shimona (assumed: unchecked, same as the rule)' 31 and 'Shimona (said ... not checked one by one)' 6 (copy the rule's answer, circular), 'Claude (draft, text only)' 100 (15 Oct batches 6-10, incl. the 24 random unflagged videos) and 'claude (not human)' 100 (26 Oct batch 11). The scoring script now treats only reviewer exactly 'Shimona' and her own spoken_scan verdicts (minus the 45 unchecked 'yes') as human. CORRECT NUMBERS: flagged events checked one by one = 73 of 75 real (97%, 95% interval 91-99%; brand_and_code 28/29, official_label 14/14, spoken 23/24) but that is only 4% of 1,876 events; Claude's two text-only readings of 113 decided flagged events find only 61% (52-70%) look sponsored from the description alone (cannot hear spoken sponsors or see the video), so weak-tier precision is somewhere between about 60% and 95%, to be settled by Shimona checking the 30 batch-11 rows Claude called footer-only. No random unflagged sample was checked by a person, so the miss rate is unknown. `sponsorship_event_scores` rewritten with model_version `tier-precision-human-only-2026-10-27`. LABEL QUALITY DONE (26 Oct night): only about 10% of events were human-checked, so `scripts/score_sponsorship_events.py` measured the labels (grouped-by-creator cross-validation, `ml/sponsorship_quality.py`, report `models/sponsorship_quality.json`, S9 card). RESULT: of 128 flagged events a person checked, 117 are real ads = 91% (95% interval 85-95%); by tier official_label 17/17, disclosure_tag 6/6, brand_mention 9/9, spoken 23/25, brand_and_code 62/70 (89%). A text+tier model did NOT beat the tier-only baseline and cannot separate real from false among flagged events (AUC ~0.5, only 11 known false ones), so events are scored by shrunk tier precision (model_version `tier-precision-2026-10-26`) in table `sponsorship_event_scores` (1,876 events, migration 20261026010000). Unflagged side: a random sample of 24 unflagged videos had 0 sponsored; the promo-word sample (not random) had 10 sponsored of 53 decided, so some real ads are missed. The false positives are mostly a creator's own affiliate code with no ad disclosure (Buy link / code in a vlog) and are not separable by position or words with 70 checks. GAIL's training data was NOT changed. Next lever: hand-check batch 11 (100 unchecked weak-tier events in the spillover pairs, in `sponsorship_review` and `scripts/label_check_sheet.md`, made by `scripts/make_label_check_batch.py`); after her verdicts re-run score_sponsorship_events.py, and only then decide about a probability filter in make_shared_brand_targets.py. SENTIMENT RE-SCORE DONE (27 Oct ~00:00 IST): `scripts/score_creator_sentiment.py --limit-creators 0 --devanagari-model` over 35,152 comments (newest 100 per creator per platform); 238 Devanagari comments went through the multilingual model, the rest through the English model. New file adopted as `models/temporal_sentiment.json` (286 creators; 4 creators outside the 150 had no comments in this run and keep their earlier entry; the previous file is saved in the scratchpad). Effect: median change 0.0001, 29 creators moved by more than 0.02 and 13 by more than 0.05 (largest +/-0.14; partly newer comments, partly the Devanagari fix); coverage of the core 150 unchanged (149 scored). ml 149, backend 120, ingestion 120 tests pass. LINKS, PLATFORM PROFILE, RANKING (26 Oct late night): (1) NEW LINK TYPE @mentions: `build_mention_edges` in `backend/app/feature_store.py`, endpoint `/feature-store/edges/mentions`, exported as `mention_edges.json` (copy in `exports/training_inputs_26oct/`): a creator @-mentions the handle of another creator we track in a video title/description or Instagram caption; 154 directed edges, 34 pairs inside the 150, links 42 of the 150 on their own. Creators of the 150 with any graph link: 17 (flags off) / 80 (SHARED_BRAND=1) / 46 (mentions only) / **91 (both)**, measured by running the patched loaders. (2) PATCH FIX: the earlier patch put the SHARED_BRAND graph block inside `load_collab_edges`, where `itertools` is not imported, so `SHARED_BRAND=1` would have crashed with a NameError at training start; it now sits in `load_cooccurrence_edges` (next to the Reddit pairs) and `MENTION_EDGES=<dir>/mention_edges.json` adds the mention pairs to the collaborates_with graph. Patch regenerated (60 lines), applies cleanly to a pristine copy and the result compiles. TRAINING ENV NOW: `SHARED_BRAND=1`, `MENTION_EDGES=exports/training_inputs_26oct/mention_edges.json`, `SHARED_BRAND_TARGETS=exports/training_inputs_26oct/training_pair_deltas.json`. Mention pairs are graph edges only, not extra training targets. (3) PLATFORM PROFILE: `backend/app/platform_profile.py`, `GET /platform-profiles/{creator_id}` (and `?creator_ids=` for several): per platform audience, typical views/likes/comments, engagement rate, posts in the last 90 days, sponsored-vs-usual, first-24-hour growth from the growth readings, and a strong/typical/weak status (engagement-rate third among creators tracked on that platform; unknown below 5 posts with counts); a summary sentence says which platform is stronger. Dashboard button 'Show YouTube vs Instagram status' loads it per creator (`frontend/src/components/PlatformProfileCard.tsx`). Checked live: Ankit Yadav weak on YouTube, strong on Instagram; Prem Joshi strong on YouTube, no Instagram data. Startup warm-up of the comparison data. (4) RANKING: creators with no collected posts on either platform ranked high on category + graph alone (e.g. #1 and #3 for 'whey protein'); `data_coverage` now on every recommendation and creators with data rank above those without (none removed), dashboard shows 'no data collected yet'. Backend tests 120 pass (was 111); frontend tsc + eslint pass. SENTIMENT CHECK (26 Oct night, `scripts/check_sentiment_labels.py`; labels by Claude from the text only, `models/sentiment_labels_by_claude.json`, NOT human ground truth; human labels in `sentiment_review.verdict` still pending, run with `--human` then): current English-trained model vs labels, Spearman: English +0.77, Hinglish +0.47, Devanagari +0.33. Multilingual model `cardiffnlp/twitter-xlm-roberta-base-sentiment` (Shimona said yes; 1,112 MB weights, downloaded 26 Oct into the local Hugging Face cache; the first download also pulled a redundant TensorFlow file, deleted): English +0.75, Hinglish +0.45, Devanagari +0.76. Decision: use it for Devanagari comments ONLY (about 1-2% of comments); `scripts/score_creator_sentiment.py --devanagari-model` does that (helper `ml.temporal.sentiment.multilingual_scorer`; needs `tokenizer.json` copied next to the weights from the sibling repo `...-sentiment-multilingual`). Hinglish is still only moderate with either model. CLAUDE PRE-LABELS OF BATCH 11 (100 events, `models/label_check_batch11_by_claude.json`, written into `sponsorship_review` with reviewer 'claude (not human)' so they are kept apart; `score_sponsorship_events.py` excludes them from the human numbers and reports them separately): from the text only (links not opened): 55 sponsored, 30 footer-only (generic coupon list or pasted block on a video not about that brand), 10 unsure, 5 not ads. So only 55 of 90 decided (61%, 95% interval 51-71%) look sponsored in this sample of weak-tier events inside the spillover pairs, against 89% for brand_and_code in the human sample. Either Claude is stricter than the human reviewer or the earlier 91% is optimistic for these events; Shimona's check of the 30 footer-only rows settles it. DIRECT EFFECT (26 Oct night, `scripts/run_direct_effect.py`, `models/direct_effect.json`, Eesha's PDF item B; association within creator, not proof of cause): a sponsored YouTube video gets about the same views as the creator's own typical video (median effect -0.017 log points, ratio 0.98, 95% interval -0.18 to +0.19, 80 creators / 1,397 events; strong-evidence only +0.020 [-0.46, +0.45], 48 creators / 193 events). Their like+comment rate is lower: -0.045 [-0.136, -0.013] all events, -0.176 [-0.345, -0.064] strong only (about 16% lower). The same-method check on non-sponsored posts is +0.10 for views (so the method itself leans slightly positive; relative to it sponsored views are about 0.12 lower) and -0.025 for rate. Instagram has only 15 mature sponsored posts with counts (13 creators): too few to read. OUT-OF-TIME RANKING TEST (`scripts/run_ranking_test.py`, `models/ranking_test.json`, PDF item D2; harness ready, GAIL row pending): creators ranked from pre-cutoff data, outcome = mean direct effect of their sponsored YouTube videos after the cutoff. Cutoff 1 Jan 2026 (37 creators): no baseline beats random (popularity Spearman +0.08 [-0.27,+0.44], P@10 0.30 vs 0.32 random; engagement rate +0.13, P@10 0.40; past direct effect +0.30 [-0.05,+0.62], P@10 0.50 vs 0.28); cutoff 1 Jul 2025 (52 creators): all near zero and past direct effect flips to -0.14, so the one hint at the first cutoff is noise. Reading: with a direct effect near zero nothing predicts it. Pass GAIL's scores built ONLY from pre-cutoff data with `--scores` to add a GAIL row (a model trained on all data has seen the outcome window and cannot be tested this way). Tests: `tests/test_direct_effect_ranking.py` (5 pass). FUSION LAYER (checked 26 Oct night with `scripts/check_live_scores.py`): works end to end; sentiment real for 149/150, creator feature (CLIP/BERT) 150/150, spillover real for only 5/150 (145 neutral 0.5) until GAIL is retrained with the shared-brand graph; weights 0.4/0.3/0.3 cannot be fitted (only 10 labelled outcomes). SNOWBALL TRIAGE (`scripts/ingestion/snowball_triage.py`, `models/snowball_candidates.json`, 623 YouTube quota units, read only): of 623 listed collaborators not in `creators`, 281 have a YouTube channel under the same handle, only 30 are confirmed to be the same account by their channel description, and 0 of those are Indian fitness creators (they are brands, celebrities and organisations: Myntra, Gucci, NBA, Herbalife). Snowballing from the listed collaborators is therefore not worth running; plausible individual fitness accounts would be at most a handful. Not added to the database. FRESH TRAINING INPUTS (26 Oct ~18:25 IST, 1,876 events, after the last data changes): `exports/training_inputs_26oct/` (git-ignored, 16 MB; `training_pair_deltas.json` = 88 collaboration rows + 16,072 shared-brand rows -> 153 independent observations from 70 neighbours, self-check 51 of her lift rows recomputed, 0 differ). Use this folder instead of the earlier final26_sb for SHARED_BRAND_TARGETS. DAILY JOB CHANGE (26 Oct evening, tested: 120 ingestion tests, dry run only; first live use is the 27 Oct 12:00 run): `instagram_daily.py` now reserves up to 25 of the 130 daily page loads (`BACKFILL_LOADS_PER_DAY`, at most a third of what is left, never more than posts waiting) for the owner-checked count filler (`instagram_backfill_counts.read_and_fill` / `posts_to_fill`): posts of the verified 150 with no counts and no ownership check, creators with sponsored posts first. It runs AFTER the refresh and new-creator phases inside try/except, so a fault there is logged and cannot fail the day; foreign posts it finds are detached with a backup (`instagram_posts_foreign_backup_20261026`) and written into `ownership_audit_checkpoint.json` (a tracked file that will change daily). About 342 posts wait, so roughly 14 days to clear. The run's `instagram_daily_runs.detail` reports how many were filled/detached. If it misbehaves, set `BACKFILL_LOADS_PER_DAY = 0` to switch it off. ROBUSTNESS (26 Oct evening, `scripts/run_spillover_placebo.py --strong-only`, `models/spillover_placebo_test_strong_only.json`): keeping only events with STRONG evidence (360 events, 1,230 event-neighbour rows, 54 neighbours inside the 150) the within-neighbour placebo test still finds no positive spillover: per-neighbour median -0.11 [-0.17, +0.00], events beat placebo for 20 of 54 neighbours; mature-only -0.01 [-0.23, +0.07], 25 of 51. So the null does not depend on the weaker brand-name / promo-code labels. FINAL STATE 26 OCT ~15:30 IST (everything below re-verified after the YouTube extension and re-labelling): TRAINING TARGETS (target builder only, NO training; `scripts/patches/train_prod_model_shared_brand.patch`, run with SHARED_BRAND_TARGETS=<final26_sb>/training_pair_deltas.json): canonical collaboration pairs 88 (was 75); flag OFF = 24 labelled creators / 39 independent observations; flag ON = 91 labelled creators / 186 independent observations, target sd 0.96, max |target| 5.0. INSTAGRAM today: noon run OK (refreshed 6, collected 1); count-filler now verifies the page AND the true owner from the same single load (`instagram_backfill_counts.py`: foreign posts are detached with a backup, nothing written for them) and read 12 more posts: 12/12 got counts, 0 foreign; day total 123 of 130 page loads; 342 posts of the 150 still have no counts and were never owner-checked (165 of them belong to exposed neighbours and are listed first). MONITORING: GET /alerts now returns `creator_name` and `propagated_from_name` (names appear in about 2 s instead of 11 s); the 13 alerts are from 5 Oct (mostly cricketers/clubs, none are fitness creators) and were not regenerated (`scripts/generate_propagated_alerts.py --write` would, deliberately not run). TESTS: backend 111, ml 139, ingestion 119 pass; frontend tsc, eslint and `next build` (7 routes) pass. App checked in the browser: brief form, results (full list, broader-match labels, real feature scores on a cold start), Explainability (per-creator arithmetic), Monitoring, Analysis (S9 tab). NOT DONE / NOT TESTED: no model retrained or changed; Docker compose untested (Docker not installed on this laptop); about 1,100 old Instagram posts mostly of creators outside the 150 unaudited; GAIL's saved checkpoint still gives a real spillover score to only 5 of the 150 (145 isolated) until it is retrained with the shared-brand graph (links reach 80 of 150: shared brand alone 65).
(3) SPILLOVER: the exposed-vs-unexposed comparison (Test B) now reads +0.49 [+0.27, +0.74] (70 exposed, 60 unexposed inside the 150), which excludes zero. DO NOT quote it alone: the within-neighbour placebo test (Test A, `scripts/run_spillover_placebo.py`, each creator against ITSELF at dates months away) reads +0.00 [-0.04, +0.03] with events beating placebo for 33 of 65 creators (mature-only: -0.05 [-0.10, +0.03], 27 of 65), i.e. no spillover; the median paired difference is -0.16. The group comparison picks up what kind of creator is exposed (already growing faster at ordinary dates). Report Test A as the main result and Test B with that explanation. (4) LAG: the 'emerging delayed signal' reported earlier (Instagram post with no YouTube upload nearby -> YouTube views, p 0.002 on 51 posts) FADED with more data: 14.5 days, 64 posts / 29 creators, best p 0.048 in 36-48h, not detected after correction (threshold 0.0125). Retract it; re-test at 18 and 28 days. Control still detected. Files saved: `models/spillover_placebo_test.json`, `models/spillover_effect_restricted150.json`, `models/snapshot_lag.json`.

**Update 2026-10-26 (Shimona; live-checked 10:00-12:00 IST): DATA READY FOR RETRAINING. Nothing has been retrained or changed in GAIL (Shimona asked to start the retrain herself / with Eesha).**

HANDOFF FOR WHOEVER RETRAINS
1. Clean data package, exported 26 Oct: `python scripts/export_feature_store.py <out_dir>` writes creators (390), collaboration (354 directed), co-occurrence (1,416), sponsorship (802 edges; was 819 before 28 wrong brands were removed) and NEW `shared_brand_edges.json` (774 directed). The shared-brand relation is a separate, opt-in endpoint (`/feature-store/edges/shared-brand`, `build_shared_brand_edges` in `backend/app/feature_store.py`): the saved checkpoint was trained without it, so it is only used if the retrain adds it. In the 26 Oct scratch test it was merged into `co_occurs_with` (patch: after the Reddit pairs are built in `load_cooccurrence_edges`, add creators who share a sponsored brand, weight = shared brands; env flag SHARED_BRAND=1). Effect on the graph (of the 150): creators with any link 17 -> 67 (fitness 9 -> 58 of 116).
2. Training population: the verified 150 (`creator_verification`, link_level confirmed/probable). Under collaboration links only, 15 of the 19 measured exposed creators were celebrities/clubs outside the 150 (only 4 inside, 2 fitness); with the shared-brand link 54 of 75 exposed are inside the 150 (51 fitness).
3. Targets: per-creator robust (median-based) engagement lift around sponsored events, clipped +-5, from `compute_training_pair_deltas.py` (Eesha's branch). Pairs and measurable examples after today's cleaning: 76 candidate pairs, 27+ measurable, 22 exposed (collaboration) / 75 (shared-brand). Unexposed comparison creators: `scripts/make_unexposed_controls.py`.
3b. TRAINING EXAMPLES (important): `train_prod_model.py` builds its targets from Track A's `pair_count`, which only counts a pair when the sponsored creator LISTS a collaborator who is also one of our creators; only 7 of the 880 listed collaborators are inside the 150 (widening the match to YouTube handles adds 2), so adding the shared-brand edges to the GRAPH does not add training examples. `scripts/make_shared_brand_targets.py --base <export dir> --out <dir>` (needs Eesha's `ml.engagement_lift` / `ml.target_clustering`; run with PYTHONPATH pointing at her checkout) builds the shared-brand (event, neighbour, lift) rows with her own lift definition, after first recomputing her collaboration lifts (40 rows, 0 differ). Run 26 Oct on the cleaned data: 4,920 shared-brand rows -> 118 independent observations (E2 clustering, 30-day window) from 55 neighbours, versus about 20 from collaboration links; robust lift median -0.10, stdev 1.67. The relation is exploratory (niche overlap can contribute): label it so. To use it in training, `build_targets_from_canonical` must read these rows as well: `scripts/patches/train_prod_model_shared_brand.patch` (44 lines, applies cleanly to review2-eesha-model's `scripts/train_prod_model.py`, off by default) does that. `SHARED_BRAND=1` adds the shared-brand pairs to the co_occurs_with graph; `SHARED_BRAND_TARGETS=<dir>/training_pair_deltas.json` adds the rows as training targets (clipped at +-5; without the clip the largest target is 12.4). Target builder only, NO training, 26 Oct on the live data: flag off = 22 labelled creators / 30 independent observations (her original behaviour); flag on = 75 labelled creators / 146 independent observations, target sd 1.07, max |target| 5.0. Apply with `git apply scripts/patches/train_prod_model_shared_brand.patch` (or `patch -p1`).
4. DO NOT quote the in-sample effect printed by `train_prod_model.py` (memorised: in-sample error 0.004 vs 2.21 baseline, effect -0.02 with SE 0.016). Known GAIL issues (all measured on 24-26 Oct): propensity ranges 0.000-1.000 (saturated), the neural head ignores exposure (moves <0.01 when exposure is zeroed), attention learns nothing about WHICH neighbour matters (correlation about 0.01), it under-estimates planted effects by 30-60%, and in sparse worlds it can return the wrong sign. `scripts/gail_acceptance.py` (simulated worlds) fails 4 of 4 checks today; re-run it on any changed model. Cross-fitting + proper propensity + exposed-only averaging fixes the false effect at zero and the wrong signs but still under-estimates by about a third (sim_fixed_estimator, scratchpad).
5. Validation protocol to report after the retrain (held-out REAL creators only; simulated data never in the test set): held-out error vs an always-zero baseline and a train-mean baseline, rank correlation predicted vs actual lift, share with the right sign, exposed-minus-unexposed gap predicted vs actual; effect recovery and attention correlation on the simulated acceptance worlds. The reported real-data EFFECT comes from `ml/spillover_effect.py` (difference in means / adjusted, creator bootstrap), restricted to the 150: shared-brand link -0.00 [-0.30, +0.30] (54 exposed, 72 unexposed), collaboration links only 4 exposed = unusable. Detection curve (simulated): 19 exposed sees +0.5 only 39% of the time; 81 exposed 90%.
6. After the retrain run `python scripts/check_live_scores.py` (about 2 min). Today: spillover isolated 145 / inferred 4 / trained 1; sentiment 149 scored; creator feature 150 scored (spread 0.23-0.82 for 'whey protein'). Target: far fewer isolated.
7. Fusion formula (documented priors, not fitted): final = 0.4 spillover + 0.3 sentiment/risk + 0.3 creator-feature, x100; minus 10 points if sentiment/risk < 0.3; interval = 100 x sqrt((0.4 hw1)^2 + (0.3 hw2)^2 + (0.3 hw3)^2). Feature-score AUC 0.85 (fitness brief) / 0.57 (cricket brief).

WHAT CHANGED IN THE REPO ON 25-26 OCT (all tested; nothing committed by Claude)
- Data (Supabase, every change backed up): 28 wrong brand tags removed (`brand_fix_backup_20261025`); 2 brands attached (`brand_rematch_backup_20261026`); 43 posts that belong to other accounts detached from creators (`instagram_posts_foreign_backup_20261026`; the audit found 21.2% of 690 audited old posts foreign; 38 more old posts of the 150 audited 26 Oct: 34 clean, 4 foreign); 161 old Instagram posts got like/comment counts (`scripts/ingestion/instagram_backfill_counts.py`); `instagram_collect_failures` (skip a creator whose page has no posts) and `instagram_extra_loads` (audits count against the daily 130 page-load budget); no rows deleted. ~1,100 old posts (mostly of creators outside the 150) are still unaudited.
- Backend: `include_broader_matches` (default off) + `product_match` on results so the dashboard fills a short list; shared-brand edge builder + endpoint; CLIP/BERT models now load at server start and a request waits (up to 60 s, cold start only) for them, because the first request after a restart used to return the neutral 0.5 for the feature score (verified live: cold request, 8.7 s, 0 of 10 neutral).
- Frontend: sends `include_broader_matches: true`, shows a "broader match" label; new Analysis tab "S9 Live results" (lag test, spillover on the 150, simulated detection curve, data inventory); the old "lag not proven, only 13 creators" text is replaced. `docker-compose.yml` added (UNTESTED, Docker is not installed on the laptop; the backend image has no ml/ or models/ by design, so spillover and creator-feature scores are neutral inside Docker). `.claude/launch.json` added for the preview tool.
- Tests: backend 107, ml 139, ingestion 118 pass; frontend tsc, eslint and `next build` (7 routes) pass.
- Scheduler note: Windows Task Scheduler runs `CapstoneInstagramDaily` at 12:00 and catches up a missed run at boot (it did on 25 Oct 19:23); check for a running `instagram_daily.py` / `running.lock` before any manual Instagram work.
STILL OPEN: Shimona's checks (45 caption labels approved unchecked, 120 Hinglish comments, SentiMix benchmark not downloaded), second-machine Instagram capacity (per-account budget), 28-day lag, 81+ exposed creators, GAIL changes (Eesha), commit and push (about 40 files).

**Update 2026-10-24 (Shimona; live-checked 11:45 IST):**
- **Eesha pushed E8, E10, E12-E14 on 23 Oct 18:52 (origin/review2-eesha-model 104d4cc/5b12122/5d10ed2):** capacity knob GAIL_HIDDEN_CHANNELS (default 16; her finding: width is not the limit, the model fits its labelled nodes in-sample and ignores exposure), bot scoring wired (0 of 219 flagged, nobody excluded), training-path fixes (the propensity head was learning P(own sponsorship), AIPW never ran, the consistency mask ignored co_occurs_with, training windows were unbounded while the inspection script was bounded, the run now survives Supabase closing an idle connection). Her own limitation note: nuisance models are fit in-sample, per-creator tau between -0.04 and +0.03; cross-fitting is her next change. E4's ablation harness is `ml/synthetic_recovery.py` (`compare_supervision`); E5 not found (the plan said to evidence-check or drop it).
- **Retest on her newest code (scratch copy, nothing in the repo or production checkpoint changed):** her suite 201 passed, 1 skipped; canonical pairs 75, 26 with a same-platform lift, effective N 19 (16 after her training filter); leave-one-out with the median target on collaboration links, 16 held-out creators: MSE 2.56 vs always-zero 2.21, rank corr -0.51; collaboration + shared-brand links (4,619 rows, 120 independent observations, 56 neighbours), 71 held-out creators: MSE 3.28 vs zero 3.22, MAE 0.83 vs 0.72, rank corr -0.04, direction right 52%. Same conclusion as 22 Oct: no detectable spillover and no skill over a zero guess.
- **Lag re-run at 12.4 days (`models/snapshot_lag.json`, 10.7-day version kept in scratch):** control passed (688 uploads, 121 creators); Instagram post -> views on YouTube videos older than 72 h not detected (199 units / 46 creators, smallest p 0.072 at 12-24 h; all four windows after the post positive: +0.26, +0.10, +0.29, +0.10; the earlier pre-event excess faded); the "no YouTube upload within 24 h" subset (39 units / 22 creators) that looked significant at 10.7 days is now p 0.07 (fragile, small); YouTube upload -> Instagram posting: +0.33 of the usual rate in the 12 h BEFORE the upload (p 0.001, 3,443 units / 56 creators), nothing after (third consistent run).
- **Instagram:** 71 of 150 verified creators collected, 41 with 2+ readings, 38 creators with enough on both platforms for lag (target 40), 177 posts with a reading inside their first 24 h (target 300), 13 days of readings (target about 28). No daily run was recorded on 23 or 24 Oct before 10:23 (laptop off at 12:00; the task's 10:12 run on 24 Oct ended with exit code 3221225786, killed). `instagram_daily.py` now (a) skips a creator whose profile was read in the last 30 days (fitwithdilsil: 803K followers, no post in a year, was being retried every day: check whether the handle is right), (b) collects fitness creators first, then sponsor group A, then confirmed links, (c) never spends loads on `famous_general` creators (11 on the list: Elvish Yadav, Fukra Insaan, etc.; only Raj Shamani has any fitness-brand ad; their existing data stays).
- **YouTube top-up 24 Oct:** 5,793 comments for 546 new uploads, +7 YouTube / +6 Instagram sponsored, +3 from creators' own comments (849 labelled posts, 786 with a brand), 798 buying-comment matches. Reddit unchanged since 21 Oct (next refresh about 28 Oct).
- **GAIL effect estimate, cross-fitting tested on a scratch copy of Eesha's 104d4cc (24 Oct afternoon); nothing on her branch or in the production checkpoint changed.** Her E12 code reports an AIPW effect with both nuisance models fit on the same creators it averages over (she flags this herself). Findings: (1) every creator with a measured lift is a neighbour of a sponsored creator, so exposure is 1 for all of them and the effect is not identified from data (a zero-effect world returned +3.4); fix = add an unexposed comparison group (creators with no sponsored neighbour, lift measured at placebo dates drawn from the real event dates) → 16 exposed + 84 unexposed, built by `scripts/make_unexposed_controls.py`. (2) With that group, the cross-fitted GAIL neural head still FAILS the planted-effect check (true +1.47, estimate +0.04): its outcome head reads a 1289-dim embedding that identifies each creator, so exposure carries no weight (predictions move <0.01 when exposure is zeroed). (3) A cross-fitted AIPW with a low-capacity outcome model also fails (+0.58) because the propensity weights add noise at 16 exposed. (4) What passes: difference in means and ridge-adjusted exposure coefficient with a creator bootstrap (`ml/spillover_effect.py`, `scripts/run_spillover_check.py`, `tests/test_spillover_effect.py`, results `models/spillover_effect_check.json`): effect 0 → interval includes 0; planted +1.47 → found ([+1.06, +2.59]); planted +0.73 → NOT detected ([-0.10, +1.29]). **Real data: diff-in-means +0.27 [-0.39, +1.06], adjusted +0.18 [-0.81, +1.22] → no detectable spillover; effects larger than about +1 lift (≈100% engagement) are ruled out, smaller ones cannot be seen at 16 exposed creators.** For Eesha: do not report the in-sample tau as an effect; cross-fitting the neural head will not fix it (the head needs a low-capacity exposure pathway); the write-up should use the bootstrap estimates and state the detectable-effect floor. Needs more exposed creators (Instagram depth over the next 2-3 weeks) to move that floor. **Sample-size table (80% power, 5% two-sided, ratio 1:5 exposed:unexposed, sd 1.47):** +1.0 needs 21 exposed/105 unexposed; +0.75 needs 36/180; +0.5 needs 81/405; +0.3 needs 225/1,125; +0.2 needs 506/2,530. Have 16/84 (16 creators from 21 events by only 12 sponsoring creators; floor today about +1.1). **Shared-brand relation through the same check (24 Oct evening, `models/spillover_effect_check_shared_brand.json`, data from looeval5):** exposed creators rise from 16 to 71 (66 sponsoring creators, 682 events, 85 unexposed). Real: diff-in-means +0.18 [-0.17, +0.51], adjusted +0.34 [-0.64, +1.42] → still no detectable effect, but the floor drops to about +0.5. Planted checks: effect 0 → includes 0 (but +0.40 [-0.03, +0.82], borderline); +0.76 → not detected; +1.52 → found (estimate +2.20, overshoots by about 0.7). Caveats: (a) exposure is "promotes the same brand", which is confounded with niche/category and is a different hypothesis from collaboration spillover; (b) the 71 nodes share 682 events from 66 creators, so resampling nodes understates the uncertainty; (c) the upward bias in the zero-effect world needs a repeat with other seeds before this is quoted. Needs the team decision on whether to treat it as an exploratory result. **Retrain 24 Oct 19:28 (scratch copy of 104d4cc, checkpoint NOT copied into the repo):** 26 rows -> 19 independent observations across 16 creators; in-sample MSE 0.0042 vs 2.21 baseline (99.8%, memorisation, not skill); reported ATE -0.024 with naive SE 0.016 (an artifact, do not quote); propensity min 0.000 / max 1.000 (saturated, the script's own check fails); learned transmission shares co_occurs_with 0.51 / collaborates_with 0.49; bot detection 0/224 flagged.
- **GAIL spillover check re-run on the new labels (24 Oct night; both result files in `models/` replaced; all steps exit 0):** the 45 new labels changed little: candidate rows 75→76, measurable 26→27, exposed creators 16→17 (shared-brand 71→72). Collaboration only: real diff-in-means +0.25 [-0.39, +1.01] and adjusted +0.45 [-0.72, +1.71], no detectable effect; checks: effect 0 → -0.11 (includes 0), +0.72 → +0.88 [+0.15, +1.59] found, +1.44 → +1.57 found. Shared-brand (72 exposed, 152 analysed): real +0.16 [-0.20, +0.48], adjusted +0.00 [-0.73, +0.72], no detectable effect; checks: effect 0 → -0.20 (includes 0; the earlier +0.40 was chance), +0.79 → +0.24 not detected, +1.57 → +1.61 found (the earlier overshoot is gone). Floor: about +1.0 (collab only) and about +0.8 (shared-brand). The AIPW column keeps failing the planted checks, so it is not the headline. The caveats on shared-brand (niche confound, shared events) stand.
- **Why 49 of the 76 candidate GAIL pairs are not measurable (25 Oct, live-checked) — it is coverage, not waiting:** every event is 63+ days old, so no pair is waiting for its after-window. For the 49: 23 have no Instagram post within ±30 days of the event at all; 13 have Instagram posts on BOTH sides but those old posts were saved by the first collector WITHOUT like/comment counts (1,339 old Instagram posts have no counts); the rest have posts on one side only. **Fix built: `scripts/ingestion/instagram_backfill_counts.py`** (one-time, read-only; reads an old post page and fills its counts; each read is logged as a `post_snapshots` row so it counts against the 130-loads/day budget; same stop-at-first-block rules; `pending_posts` skips finished posts; test added). Posts to read: 111 (list built from looeval6, 9 creators) → makes 13 pairs measurable, so up to 9 more exposed creators (17 → up to ~26). Probe on 3 posts at 00:38 IST worked (3/3, no block); 108 posts left. Cost is about one day of Instagram budget, so it competes with the daily refresh: plan is about 55 posts a day for 2 days, run after the UTC day resets (05:30 IST). Not scheduled; needs Shimona's go and the laptop on with Chrome open. No model change (she declined one on 25 Oct); the data route is the plan.
- **LAG RE-RUN 26 Oct 00:38 (13.9 days of readings; previous run 12.4 days saved as `models/snapshot_lag_24oct_backup.json`; `models/snapshot_lag.json` replaced; positive control passed):** control (YouTube upload -> YouTube views) 867 units / 125 creators, detected (p 0.001, 0-12h). Instagram post -> YouTube views on older videos, all posts: 261 units / 52 creators, best p 0.104 (12-24h), NOT detected (was p 0.072). Same, only Instagram posts with no YouTube upload within 24 h ("pure"): 51 units / 26 creators, best p 0.002 at 36-48h, DETECTED after correction (threshold 0.0125); was p 0.070 at 24-36h with 39 units; excess rises across 12-24h (0.23), 24-36h (0.43, p 0.012), 36-48h (0.49): a delayed rise, strongest 1.5-2 days after the post. YouTube upload -> Instagram posting: 3,918 units / 63 creators, best p 0.81, not detected after the event (an excess BEFORE the upload, -12..0h, p 0.001: creators post on Instagram shortly before uploading). Reading: an emerging, fragile signal (small n, best window moved between runs, near the edge of the 48h window); re-run at about 18 days (29 Oct) and 28 days (8-10 Nov) before claiming it; consider widening the window to 72h.
- **OLD-DATA OWNERSHIP, 26 Oct ~10:00 (the August collection bug: profile grids mixed other accounts' posts in and saved them under the creator).** Audit checkpoint (`scripts/ingestion/ownership_audit_checkpoint.json`) holds 690 posts: 146 (21.2%) belong to another account (earlier unbiased sample 14.1%). Of those 146, 107 were already detached (the netflix_in / primevideoin / pumaindia / delhipremierleaguet20 'orphan' posts); 39 were STILL filed under a creator (38 with counts, 3 sponsored) and were detached today (`creator_id` set NULL, backup `instagram_posts_foreign_backup_20261026`, `is_sponsored` and counts untouched). Real sponsorship events (with a creator) now 892 (93 creators, 802 with a brand); 5 sponsored posts are now creator-less. STILL OPEN: 1,808 old-style posts (no thumbnail, created before 1 Oct) of which only 690 audited, so about 1,118 unaudited, about 200+ foreign at the measured rate (estimate); the username field matches the creator on all 2,488 posts so it cannot reveal this, only the post page's og:description owner (`real_owner()` in audit_post_ownership.py, about 10 s and 1 page load per post). The 111 count-backfill posts: 38 audited (0 foreign), 73 not audited, so some of the 9 newly measurable pairs may rest on foreign posts. Plan: audit unaudited old posts that feed measurable pairs first, then count only verified posts (audited clean, or new-style posts collected since Oct with own-link filtering) in pair building; new daily collection is unaffected (own-link filter).
- **POPULATION CHECK, 26 Oct 02:30 (important for how spillover is reported):** of the 19 exposed creators with measured lifts under collaboration links only, just 4 are in the verified 150 (2 fitness) and 15 are outside it: celebrities and clubs such as Ronaldo, MrBeast, Karan Johar, Kerala Blasters, Mumbai City FC, Virat Kohli's and others (collaboration links connect fitness creators to famous non-fitness accounts). With the shared-brand link, 54 of 72 exposed creators are in the 150 (51 fitness) and 53 of 68 sponsoring creators are in the 150. The 20 unmeasurable neighbours are 19 outside the 150 and almost all Instagram-only celebrities/organisations (Virat Kohli alone accounts for 15 pairs from 2024-25 events with no Instagram counts around those dates), so spending Instagram page loads on them is a poor use of budget; a YouTube top-up would not help (only 5 of the 19 have a YouTube handle, and those 5 already have 213 videos stored). Estimates RESTRICTED TO THE 150 (exposed and unexposed both in the 150, 1,000 bootstrap draws, `restrict150.py` in the session scratchpad): shared-brand 54 exposed / 72 unexposed: difference in means +0.12 [-0.15, +0.37], adjusted +0.01 [-0.24, +0.43], no detectable effect, so effects above about +0.4 are ruled out for fitness creators; collaboration links: only 4 exposed in the 150, not usable (the apparent -0.46 rests on 4 creators). The planted-effect worlds of that run: effect 0 gave a false +0.68 (the known unlucky seed-7 draw), +1.5 found (+1.47). REPORT THE SHARED-BRAND RESULT RESTRICTED TO THE 150 AS THE MAIN SPILLOVER RESULT (labelled: exposure = promotes the same brand as a sponsored creator; niche confounding possible) and say that collaboration links connect mostly to celebrities and are too thin inside the 150.
- **SIMULATED DETECTION-POWER CURVE (26 Oct, not real data; `sim_power_curve.py` in the session scratchpad; heavy-tailed lifts like the real ones: Student-t 3 df, sd 1.47, clipped at +-5; unexposed group = 5 x exposed; 300 studies per cell; detection = 95% bootstrap interval of exposed minus unexposed mean excludes 0).** Share of studies that detect an effect of +0.25 / +0.50 / +0.75 / +1.00, with the false-alarm rate when nothing is there: 16 exposed 17/34/61/79%, false alarms 9%; 19 exposed (today) 16/39/69/86%, 8%; 40 exposed 25/61/91/100%, 7%; 81 exposed 36/90/99/100%, 5%; 160 exposed 61/99/100/100%, 7%; 320 exposed 90/100/100/100%, 5%. Reading: at today's 19 exposed creators we catch a doubling of engagement (+1.0) about 86% of the time but a +0.5 effect only 39%; +0.5 needs about 81 exposed (90%), +0.25 needs 320. Matches the formula table (81 for +0.5). The real-data null on collaboration links is therefore informative for large effects only.
- **GAIL ACCEPTANCE TEST (26 Oct 00:46; `scripts/gail_acceptance.py`, simulated worlds, 6 seeds, N=400, noise 1.5; run on a scratch copy of Eesha's 104d4cc): NOT ACCEPTED, 0 of 4 checks pass.** Truth = planted effect x mean true exposure over all creators. Dense: planted 0 -> -0.06 (ok); 0.5 -> +0.17 (truth +0.49); 1.0 -> +0.50 (truth +0.99); 2.0 -> +0.95 (truth +1.98). Sparse (about 39% exposed): planted 0 -> -0.65; 0.5 -> -0.54 (truth +0.13); 1.0 -> -0.41 (truth +0.25, wrong sign); 2.0 -> -0.21 (truth +0.51, wrong sign). Attention correlation about 0.00 everywhere (pass mark 0.20). Checks: (1) zero effect gives about 0 (+-0.2), (2) planted 0.5/1/2 recovered within 25% (or +-0.2), (3) attention correlation >= 0.20, (4) no wrong-sign estimate at planted >= 1. Re-run it on any changed GAIL before trusting its effect numbers. Candidate fixes to TEST (not applied; Shimona declined a model change 25 Oct): cross-fitted nuisances, the saturated propensity (0.000-1.000), a simpler exposure, an exposed-only estimand.
- **SIMULATION RESULTS, 25 Oct night (all simulated; Eesha's harness unchanged except an adjustable loss-weight copy of its training loop, `sim_tune.py` in the session scratchpad; nothing written to the database).** Checked first that the harness truth is fair (planted 1.0 -> true average effect 0.94-1.00). Training-settings search, N=400, noise sd 1.5, 6 seeds, effects 0 / 0.5 / 1 / 2: DENSE world (86% of creators exposed): default loss weights recover about 35-50% of the planted effect (mean estimates +0.17 / +0.50 / +0.95 for 0.5 / 1 / 2); no overlap+smoothness+consistency penalties recover about 65-80% (+0.40 / +0.80 / +1.27) but add noise (sd 0.3-0.4) and a false +0.25 at zero effect; consistency off only: +0.35 / +0.66 / +1.20, false +0.11 at zero. More epochs help a little (72%), wider network (41%) and slower lr (20%) hurt. SPARSE world (39% exposed, closer to our real network): EVERY setting fails; the default gives -0.65 at zero effect and -0.21 at a planted +2.0 (wrong sign); no-penalty and consistency-off are very noisy (sd 0.4-0.9) and still negative at +0.5 and +1.0. Head-to-head on the same worlds, our simple estimators (`ml/spillover_effect.py`) have bias within +-0.06 at every planted effect and both exposure densities (difference in means +0.05 dense / -0.06 sparse, adjusted -0.02, sd 0.08-0.18). Conclusion: loss-weight tuning cannot fix the neural effect estimate under sparse exposure; use the simple estimators for every real-data effect claim, report the neural head's simulated behaviour as a limitation, and leave any change to GAIL's loss or architecture to Eesha / the team (Shimona declined a model change on 25 Oct). Pretraining on simulations was not run: the failure is estimator bias at sparse exposure, which pretraining does not address.
- **25 Oct evening: backfill, scheduler collision, robustness of the GAIL check.** (1) Count backfill (`instagram_backfill_counts.py`) read 55 of the 108 remaining old posts (55/55 got counts, no block); exposed creators (collaboration only) 17 -> 19; 53 posts still to read; first-24h Instagram posts 178 -> 193; both-platform lag creators 40 (goal 40 reached); days of readings 14. (2) INCIDENT: the laptop was off from 00:56 to 19:17 on 25 Oct, so the 12:00 run was missed; Windows Task Scheduler (`StartWhenAvailable`) then started the catch-up run at 19:23 on its own, which overlapped my backfill on the same Chrome and would have taken the day to about 185 page loads (cap 100-135). I stopped the scheduled run at 19:55 (saved work kept, lock removed, `instagram_daily_runs` row closed as `stopped`) and re-ran the daily job against the real budget (refreshed 7, `_d_loki_` had no posts so it was recorded in `instagram_collect_failures` and skipped); day total 103 counted loads, no block. RULE: before starting any manual Instagram work, check `Get-CimInstance Win32_Process` for a running `instagram_daily.py` and `running.lock`. (3) Zero-effect repeats, 8 random draws each: false alarms 1 of 8 in both versions (chance level; the earlier shared-brand +0.70 was the one unlucky draw, seed 7), draw means near 0 (shared-brand about +0.08; collaboration about +0.20, slightly high). Real-data estimates across the same 8 draws: collaboration only (19 exposed) -0.08 to +0.21, median +0.10, 0 of 8 intervals exclude 0 (a clear null); shared-brand (72 exposed) +0.07 to +0.40, median +0.23, 2 of 8 intervals exclude 0 and all 8 estimates are positive: a weak, borderline positive association of roughly +0.2 (about 20% more engagement), not robust and probably confounded by niche; report it as exploratory. 
- **DATA INVENTORY, live-checked 25 Oct ~19:45 IST (150 verified creators: 120 confirmed + 30 probable handles; 116 fitness / 23 adjacent / 11 famous_general).** YouTube: 21,137 videos (Dec 2023 - Oct 2026, all with views), 165,862 comments on 5,207 videos (about 25% of videos), 206,408 growth readings since 11 Oct (2,572 videos with 3+), 769 sponsored videos (739 with a brand). Instagram: 995 posts from 77 creators, only 584 (59%) with like/comment counts, 768 with thumbnails, 55 sponsored (5 official paid-partnership labels), 29,973 comments, 1,092 growth readings. Reddit: 376 posts linked to 18 creators, 61,570 comments but only 6,608 (11%) with a time. Sponsorship events 897 (93 creators, 77 brands): ONLY 233 (26%) have strong evidence (official label / disclosure tag / spoken / creator comment); 664 are brand name or brand + code in description; 718 of the branded events are supplements, so athleisure (footwear + apparel + equipment) is 35 events, 13 creator-brand pairs, 10 brands, and only 6 events with strong evidence. Eesha's feature-store export (819 sponsorship edges, 183 creator-brand pairs) matches the database exactly. Human checks: 199 sponsorship_review rows with verdicts, 78 spoken hits (69 yes / 9 no, of which 45 yes were approved unchecked on 24 Oct), 120 sentiment comments waiting for Shimona. Quality problems: Instagram counts missing on 41% of posts (backfill in progress), weak-evidence labels dominate, Hinglish sentiment untested, 37 events with a brand that has no category, 75 sponsored events with no brand. Ratings: YouTube good; Instagram, labels, comments mixed; Instagram growth readings and Reddit weak.
- **Wrong brand attachments fixed (25 Oct evening, backed up in `brand_fix_backup_20261025`; `is_sponsored` untouched):** 28 rows (26 YouTube, 1 Instagram, 1 Reddit) had a brand that is not a brand (gmail, Delhi, Call, GunjanShouts, iamsrk) or the creator's own other channel (ONE CHANCE: onechanceshorts, theonechance, 12 events); brand set to NULL. Sponsorship events with a brand 822 -> 803, distinct brands 77 -> 70. To undo: set `brand_id` back from the backup table. Eesha's export was built before this, so her edge count (819) is now 19 too high until she re-exports.
- **SIMULATION (not real data) — GAIL power curve, 25 Oct 00:52 (Eesha's `ml/synthetic_recovery.py`, unchanged, scratch copy of 104d4cc; driver `sim_power.py` in the session scratchpad):** planted effect 1.0, noise sd 1.5 (like our real lifts; her default noise is 0.05), 3 seeds per size, 300 epochs. Mean |estimated − planted| effect error: N=120 0.29, N=400 0.43, N=1,200 0.32 — it does NOT shrink with more creators, so the remaining error is bias in the model, not lack of data. Within-neighbourhood attention correlation with the planted per-edge weights: +0.014, +0.013, +0.010 at all sizes (her ceiling for the default world is about +0.33), so the model does not learn WHICH neighbours transmit. Consequences for the write-up: (1) the average effect is recovered only roughly (error about 30-40% of the effect) even with 1,200 creators; (2) do not claim that attention weights explain which relationships carry spillover; (3) more real data helps the bootstrap estimates, but would not by itself fix the neural head. Caveat: 3 seeds, one effect size, directions of the errors not recorded. Shimona declined a model change on 25 Oct; this is reported to Eesha as a finding. Real-data estimates keep using the bootstrap check.
- **Caption-hit verdicts, 24 Oct evening (Shimona):** the Shorts scan finished (150 scanned, 2 hits). Of the 50 unchecked hits she checked 5 by hand and all 5 were NOT ads (rows 6 Ankit Baiyanpuria MuscleBlaze code, 30 Nitin Chandila WORD, 33 NotSoFit Nutrabay code, 35 ONE CHANCE WORD, 47 Shivam mishra AsItIs code) → saved `no`. She then answered "yes" to saving the other 45 as ads without opening them → saved `yes` (reviewer Shimona) and applied: 45 YouTube videos newly labelled `sponsorship_evidence='spoken'`, backed up in `youtube_videos_sponsor_backup_20261012`; YouTube sponsored videos now 775 over 70 creators; `creator_sponsorship_events` 897 rows / 93 creators. **Quality warning:** all 5 she opened were false positives (3 of them from the "code" tier), so the unchecked 45 may contain many false labels; the spoken tier precision is unknown. Revert by setting `verdict` back to null and restoring from the backup table. Lag and GAIL inputs changed: re-run both before quoting numbers. Also skipped: handles `corefitlabofficial` and `fitwithdilsil` (rarely post, content not useful) are parked for a year in `instagram_collect_failures`; Instagram target is effectively 148.
- **Instagram noon run 24 Oct failed halfway, then fixed (afternoon):** it collected fitgirl_08 (Soniya Singh Khatri, 8 posts), then stopped on `corefitlabofficial` ("no post links found"), a `probable` handle taken from a YouTube description and never verified. Nothing is saved for a failed creator, so it would have come first again every day and blocked the queue. Fix in `scripts/ingestion/instagram_daily.py`: only a real block (429, rate limit, chromewebdata, login/challenge redirect, "try again later") stops the run; a one-creator problem is written to the new table `instagram_collect_failures` (migration 20261024000000), skipped for 14 days, and the run goes on; 3 such failures in a row also end the run. `corefitlabofficial` is recorded there. Still to hand-verify: `corefitlabofficial` and `fitwithdilsil` (no post in a year); 30 handles remain `probable`. 115 ingestion tests pass.
- **Sentiment review table** `sentiment_review` (migration 20261022000000) holds 120 comments (40 English, 40 Hinglish, 40 Devanagari) for a hand check of the English-trained scorer; about half of usable comments are Hinglish; `scripts/make_sentiment_review.py` creates it.

**Update 2026-10-22 (Shimona; live-checked 13:00 IST): GAIL tested with Eesha's latest code (origin/review2-eesha-model a49e86d, E11 median-based lift), on a scratch copy; nothing in the repo or production checkpoint changed.**
- Eesha's suite: 167 tests pass. Her new commits found the same limits: of 75 canonical pairs 49 give no same-platform lift (neighbour never has posts on one platform both before and after inside the window), effective N is about 19; a wider baseline recovers at most 7 pairs. E4, E5, E8, E10 are still not on the remote.
- **Leave-one-out (her script reads `mean_lift`, so the median target was tested by swapping in `robust_lift`; with the mean target one creator at +34.7 dominated everything, MSE about 77 for every model).** Median target, 16 held-out creators: older code MSE 2.08 vs always-zero 2.21 (barely beats it; rank corr +0.44, direction right 69%); Eesha's code 2.56 (does not beat it; rank corr -0.33, 38%). With 16 folds neither is distinguishable from the baseline (standard error about 1).
- **Shared-brand relation tested as an experiment** (creators who promote the same brand: 374 pairs, 352 inside the verified 150; 4,443 (event, neighbour) rows with a same-platform 30-day lift from 651 events; after E2 clustering 119 independent observations, 55 neighbours, largest cluster 7%; my in-memory lift computation reproduces Eesha's 26 lifts exactly, 0 differ). Leave-one-out on 70 held-out creators with her code: MSE 3.69 vs always-zero 3.47, MAE 0.88 vs 0.76, rank corr -0.08, direction right 56%: no better than guessing zero.
- **Model-free placebo test** (neighbour's median lift after the real event vs lifts at dates shifted by 90-150 days): after real events -0.08 vs +0.03 at placebo dates; per-neighbour median difference -0.03, 95% interval [-0.08, +0.02] (22 of 52 neighbours); with a maturity guard (events 90+ days old, earlier placebo dates only) -0.11, [-0.23, +0.07] (18 of 44). **No detectable positive spillover between creators sharing a brand over a 30-day window.** The shared-brand link is a weak stand-in for influence; genuine collaboration rows (26) are too few to test. This is a defensible negative result, not a data-size excuse: 4x more independent observations did not change it.
- **GAIL validation controls (Eesha's code, leave-one-out, 70 held-out creators from the 4,443 shared-brand rows; planted effect = beta x spread of real lifts x z(exposure) + noise of the same spread, exposure = number of distinct sponsoring creators linked to the neighbour):** beta 1.0: MSE 4.57 vs zero 5.09, rank corr +0.36, direction 67% (detected); beta 0.5: 3.42 vs 3.51, rank corr +0.04, MAE 1.544 vs 1.539 (NOT detected); beta 0.0: 3.21 vs 2.44, rank corr -0.22, 44% (finds nothing, correct); placebo-adjusted real target (event lift minus the neighbour's own lift at dates shifted 90-150 days; 61 folds): 1.73 vs 1.52, rank corr -0.06 (nothing). So GAIL works (finds a strong planted effect, no false alarm) but at this sample size can only detect effects about as large as the noise; the real data shows none under mean, median or placebo-adjusted targets, and the model-free placebo test agrees. Defensible thesis statement: no spillover detected at or above that size; weaker effects could not be ruled out. Scripts (scratchpad, not in repo): make_gail_controls.py, shared_brand_deltas.py, spillover_placebo.py.
- Live end-to-end check of /recommendations (whey protein brief, India, 500,000 INR): 200, is_mock_data false, but only 3 results (strict product filter) and all three have spillover_basis 'isolated' (score 0.5) because new fitness creators have no graph edges; sentiment (0.47-0.75) and CLIP/BERT feature scores (0.72-0.75) are real. Frontend: tsc, lint and next build pass (6 routes). Backend 99 tests, ML tests 134 (incl. 9 for the lag analysis).
- Domain finding: 135 of the 144 loose pairs (and most collaborator rows) come from the old celebrity/sports creators; only 11 of the verified 150 fitness creators own any collaborator row; 35 handles referenced by 2+ of our creators are brands, media, teams and officials (netflix_in, primevideoin, myntra, the Delhi league teams), not fitness creators.
- Reddit old-comment re-timing (`reddit_collect.py --retime`, tested; matches old comments by their hash id so nothing is added twice): about 100 s per thread and about 25 comments timed per thread, so 900 threads would take about 25 h: stopped after a few threads, not worth the time. Scripts for the experiment are in the scratchpad, not the repo.

**Update 2026-10-21 (Shimona; live-checked 23:30 IST):**
- **New lag analysis (S1 v2)** written because the old lag scripts cannot use the growth readings or exact Instagram times: `ml/temporal/snapshot_lag.py` (weighted event study with a placebo that keeps the HOUR OF DAY: a first version with random-hour placebos reported the creators' daily rhythm as an effect, even before the event) + `scripts/run_snapshot_lag.py` (read-only; writes `models/snapshot_lag.json`; about 13 min) + `tests/test_snapshot_lag.py` (9 tests: finds a planted effect, false-alarm rate near 5%, a daily-rhythm test that the naive placebo fails and the same-hour placebo passes). Re-run as data grows: planned at 18 days (about 29 Oct) and 28 days (about 8 Nov).
- **Preliminary result at 9.8 days of readings (not yet stored in models/):** positive control PASSED (YouTube upload -> views gained, 489 units / 115 creators, +0.84 of the usual rate in 0-12 h, p 0.001). Instagram post -> views on YouTube videos older than 72 h: NOT detected after correction (133 units / 42 creators, smallest p 0.039 at 12-24 h vs 0.0125 needed; activity in the 24 h BEFORE the post is also elevated, so a common driver is not excluded). YouTube upload -> Instagram posting: Instagram posting is +0.31 of the usual rate in the 12 h BEFORE an upload (p 0.001, 3,268 units / 51 creators) and not after: creators post on Instagram shortly before uploading (posting behaviour, not audience lag). Units from one creator are not independent, so p-values are optimistic.
- **Catch-up on 2026-10-21:** comments saved for 930 new YouTube uploads (16,139 comments), label pass +13 YouTube / +23 Instagram sponsored, +6 from creators' own comments (830 labelled posts, 769 with a brand), buying-comment proxy re-scored (780 matches). Reddit searches repeated (344), 58 new posts, 6,364 comments with times. Instagram 61 of 150 creators, 39 with 2+ readings. Spoken scan 757 videos / 68 hits, 40 hits waiting for Shimona (24 have a brand + code, which were 100% right so far; 16 are the Hindi word only, which were wrong about a third of the time).
- **Pushed** 2026-10-21 (commit 558f4ba, to origin review2-shimona-temporal and to capstone-snapshots main). Eesha's branch still ends at E2 (91bcb8e); E4, E5, E8, E10 not on the remote. GAIL candidate runs (older code vs Eesha's code, in scratch) and a leave-one-out test on 16 held-out creators: neither beats an always-zero baseline (MSE 77.5/77.6 vs 77.0; without the single +34.7 outlier 2.27/2.29 vs 1.75); Eesha's version fixes the propensity-head saturation; canonical pair count is 75 (27 independent observations by E2 clustering, 21 creators, Virat Kohli = 17 pairs).

**Update 2026-10-18 (Shimona; live-checked 23:10 IST):**
- **Daily Instagram task, first real runs:** the 06:00 trigger fired at 14:33 because the laptop was off (StartWhenAvailable): result 0, 44 readings, 2 new creators. A second run (started by hand with `Start-ScheduledTask` at 22:20) ended with result 1 after 7 readings and left no log line; the same script run from a terminal worked end to end (13 creators re-read, coachkamath and sonalkapoor.23 collected). Cause of the failed scheduled run not found (the Windows task history log is off; the Chrome/OpenCLI extension also flickered around 22:18). Fix: `instagram_daily.py` now writes one row per real run to `instagram_daily_runs` (migration 20261018000000: status ok / budget_used / chrome_not_connected / locked / failed, with the refresh step's last output lines on failure), so a failed run is never silent again. Check it with `select * from instagram_daily_runs order by started_at desc`.
- **Instagram:** 50 creators with new-style posts (+ coachkamath, sonalkapoor.23, roaming_nutritionist and the 2 from the 14:33 run), about 123 page loads used on 2026-10-18 (UTC day), no block so far in about 600 loads over 6 days.
- **Spoken hits:** 28 checked by Shimona (24 yes, 4 no): 86% real, so the caption scan is the best label source; 701 sponsored YouTube videos (67 creators), 794 labelled posts. About 1,590 Shorts and 340 long videos are still unscanned (about 13 rounds of 150).
- **Engagement proxy (read-only, exploratory):** for 15-20 creators with enough videos, sponsored Shorts get about 24% fewer views than the same creator's normal Shorts (lower for 15 of 20) but about 27% more comments per view; long videos show no clear difference. Together with the purchase-intent comment rate (8.2 vs 2.7 per 1,000 comments on sponsored vs other videos) this is the outcome PROXY set; neither is sales.
- **Sentiment re-scoring** resumed from its checkpoint on 2026-10-18 (33,332 comments); embeddings were refreshed on 2026-10-17.

**Update 2026-10-17 (Shimona; live-checked 19:20 IST):**
- **Daily Instagram task (Shimona said yes 2026-10-17):** Windows scheduled task `CapstoneInstagramDaily`, daily 06:00 IST (StartWhenAvailable, runs only while she is logged on, not admin, 3 h limit), runs `scripts/ingestion/instagram_daily.py` with the repo venv. It stops quietly if Chrome/OpenCLI is not connected, works to a cap of 100 page loads per UTC day (counted from `post_snapshots`), spends about 60% on re-reading the newest (<2 days) posts of the longest-since-refreshed creators and the rest on collecting the next verified creators (most sponsored events first), stops at the first failure/block, never retries. Log: `%LOCALAPPDATA%\CapstoneInstagram\daily.log`. `python instagram_daily.py --dry-run` prints the plan and opens nothing. Remove: `schtasks /delete /tn CapstoneInstagramDaily /f`.
- **Instagram:** 42 creators collected (+Desi Gym Reviews, Shivaji Fitness, Sivaguru, Abhinav Mahajan, Dr Umesh Wadhavani, Rahul IFBB, Eshwar Bolegar, Yuvraj Singh Fitness, Liril Soni), 32 with 2+ readings (target 40). Lag readiness: YouTube 481 videos with a full first-24h curve; Instagram only 54 posts with a reading inside their first 24 h and 13 creators with 3+ posts on each side (target 40), 6 days of readings: Instagram readings are about daily, so lag is YouTube-hourly vs Instagram-daily.
- **Shorts:** 75% of verified creators' videos are Shorts (<=180 s or #shorts) but only 2.4% are labelled sponsored (long videos 6.4%; half have an empty description). `spoken_scan.py --shorts` scans Shorts of creators who also have Instagram posts (1,832 qualify); first 90 scanned, a few hits waiting for review.
- **Spoken hits:** 16 of the first 19 confirmed by Shimona (10, 18, 19 = only equipment talk) and labelled (evidence `spoken`); verdicts stored in `spoken_scan.verdict` (migration 20261015000000). Soniya Singh Khatri's YouTube = the joint "Rohit Soniya Vlogs" channel (confirmed by Shimona, 41 videos, 1,040 comments).
- **Label hand-check round 2:** 100 fresh posts in `sponsorship_review` batches 6-10 (new kind `unflagged_random`, migration 20261015010000); Claude's text-only DRAFT verdicts are stored (reviewer 'Claude (draft, text only)'); Shimona is checking 28 of them (16 unsure + 12 confident) which replace the drafts. Draft findings: 0 of 25 random no-promo-word posts were ads; weaker-tier labels (`brand_and_code`, `brand_mention`) hold up only about half the time (many are standing "use my code" footers): 277 of 595 YouTube weak-tier events have the same creator+brand on 4+ videos with the brand not in the title. NOT changed yet (would flip labels true->false): proposal is to keep them but tag the tier, train on strict tiers first, and add a "standing footer" tier only with her approval.
- **Outcome proxy (no real sales data exists; only brands hold it; no open dataset found):** `scripts/ingestion/purchase_intent.py` (+tests, migration 20261017000000, table `purchase_intent_comments`) flags comments that look like buying ('bought': ordered/bought/used the code) or wanting to buy ('asking': link/price/where to buy) in English, Hindi and Hinglish; HTML stripped, noisy phrases ('le liya', bare 'purchased') removed after a 30-comment look (about 55-60% right before, about 85% after, to be confirmed by Shimona's check). 727 matches (YouTube 588, Instagram 17, Reddit 122). On YouTube, videos labelled sponsored draw 8.2 such comments per 1,000 against 2.7 for the rest (3.1x), and 18.5% of sponsored videos have at least one versus 7.2%. It is a PROXY (a comment is not a purchase), to be used to compare the fusion and spillover scores and to sanity-check the labels.
- **YouTube featured channels** (channelSections, 1 quota unit per channel): only 4 pairs between creators we hold (1 between verified creators); 89 distinct featured channels outside our set, none featured by 2+ verified creators. Not written; adding them as neighbours would put non-verified creators in the dashboard, so it is a team decision.
- Not done: sentiment re-scoring (paused, checkpoint kept), more Shorts and long-video caption scans, Instagram collab co-author reading for graph links, 108 creators still to collect on Instagram.

**Update 2026-10-15 (Shimona; live-checked 17:00 IST):** collection first, analysis (sentiment, embeddings, audits) last.
- **YouTube:** 148 of 149 collectable creators have videos (Virat Kohli has no channel; Bani J has 1 video and Neeraj Chopra 12 in the last 12 months; Soniya Singh Khatri has no channel of her own: the only large candidate is the joint "Rohit Soniya Vlogs", NOT saved, her call). 21,606 of 21,613 videos now have a length (7 gone from YouTube). Comments saved for 419 of the 424 new uploads found by the timer (6,771 comments with exact times; commentThreads costs 1 quota unit per video, not free). Label pass re-run: 674 sponsored YouTube videos (62 creators), 762 labelled posts overall, 183 creator-brand links.
- **Spoken sponsors:** the caption scan finished 150 videos (19 with a spoken sponsor, in table `spoken_scan`). YouTube's caption block had lifted by 23:15 IST on 2026-10-14. Hits are NOT labels until Shimona checks them; 341 more qualifying videos remain for later rounds.
- **Instagram:** still 32 creators with new-style data; creators with 2+ readings on a post went 12 -> 27 (target 40). The safe daily page-load budget (about 100, counted from 05:30 IST) was used up on 2026-10-15; the first collection of 8 more creators and the rest of the second readings wait for the next reset. No block.
- **Reddit:** 260 -> about 320 threads read after two more batches; 5,449+ comments with exact times; about 75 threads left.
- **Graph links:** only about 10 solid creator-to-creator links can be derived from @mentions, profile links and names in titles (fitness creators rarely tag each other). 7 well-supported pairs were written to `creator_related_accounts` (relation `frequent_collaborator`, rows created 2026-10-15; 5 title-only candidates incl. Virat Kohli / Pooja Bishnoi were held back as weak). `scripts/find_computable_training_pairs.py` now finds 144 pairs from 58 of 759 events: most events give none because the new creators have no neighbours. Options: read Instagram collab co-authors (`collab_edges.py`, page loads), or a shared-brand relation (needs Eesha's multi-relational work E6; team decision).
- **Sentiment scoring** of all creators' comments was started and STOPPED on purpose (collection is not finished): checkpoint kept at the scratchpad `temporal_sentiment_new.json.checkpoint.json`; re-run `scripts/score_creator_sentiment.py --limit-creators 0` after collection. CLIP/BERT embeddings, fusion backfill, audits and the Analysis-tab export are also still to re-run at the end.
- **Note:** `find_computable_training_pairs.py` writes `scripts/computable_pairs.json` into the repo folder when run from there; it is a scratch output, do not commit it.

**Update 2026-10-14 (Shimona; live-checked 14:30 IST):** see `DATA_FOR_TRAINING.md` for the table guide (written for Eesha's E-task testing; she needs only the shared `DATABASE_URL`, sent privately).
- **Sponsorship labels:** `creator_sponsorship_events` 759 rows (84 creators, 703 with a brand). New column `sponsorship_evidence` (official_label > spoken > creator_comment > disclosure_tag > brand_and_code > brand_mention; migration 20261014000000, backfilled). 31 labels came from creators' own comments (`comment_sponsor_pass.py`, standing comments repeated on 4+ videos are ignored). Posts with a promo code but no known brand are tagged `promo_code_only` (154) and are NOT events. A hand check (table `sponsorship_review`, 99 items, 62 checked one by one): flagged ones right 48 of 48; about 43% of the code-only posts skipped were real ads. Round 2 of the check is still to do.
- **Reddit:** new collector `reddit_collect.py` (strict alias matching instead of the old ~24% wrong links; thread comments read from the page JSON so every comment has id and exact time; resumable via `reddit_search_log`; searches 12 s apart; Windows cmd quirk: no '&' or double quotes in the page script or query). 342 searches done in r/indianfitness and r/Fitness_India; 511 posts saved (420 tied to a known brand by strict matching, 18 creators named); 148 threads read, 4,046 comments with times; 245 more threads waiting. Reddit talks about brands, rarely about single creators.
- **Instagram:** 32 creators now have new-style data (198 posts, 1,786 comments with times); 12 creators re-read for growth (69 posts with 2+ readings). Safe pace: about 100-135 page loads a day, no block so far. Target 40 for the lag analysis, 60 planned.
- **YouTube growth timer in Supabase** (pg_cron job `youtube_snapshots`, every 2 h): run log in `snapshot_job_log`, all runs since 2026-10-13 23:47 succeeded with 0 errors.
- **Spoken sponsors:** `spoken_sponsor.py` + resumable `spoken_scan.py` (table `spoken_scan`, migration 20261014020000). A 10-video test found a spoken sponsor in 2. YouTube blocks caption requests after about 10-20 in a row and the block lasts over an hour on this connection; the scanner waits and resumes, nothing is saved as a label until a person checks the hits.
- **Not done yet:** second label hand-check, graph links from @mentions and shared brands for the new creators, S2 embeddings refresh, daily scheduled Instagram reading, 245 more Reddit threads, the scanner run.

**Update 2026-10-13 night (names from Shimona):** checked Gaurav Taneja (already ours), Ankit Baiyanpuria (already ours; MuscleBlaze athlete per his Instagram bio, group set to A; the reported Asics deal is not supported by any source), Soniya Singh Khatri (@fitgirl_08, 3M, bio tags Ripped Up Nutrition / Red Skull / TrueForma; saved as `pending`: her YouTube channel is not found yet, search after the API quota resets), Bani J (@banij 2M + YouTube @banij 24.2K, saved `probable`; no brand tags in her bio, Reebok/Adidas claims unsupported), Neeraj Chopra and Virat Kohli (athletes already in `creators`, added to the verification list as `adjacent`; our saved posts show no shoe-brand ads, Virat's 2 #Ad are Oakley and a Dubai campaign). Verification list: 168 rows, 149 collectable. Brand matcher: a bare '@brandname' mention now counts as a mention; added TrueForma, Mille, Gayor, Nakpro etc. Not done yet: collect Bani J on YouTube, find Soniya's YouTube channel, verify the 21 discovery creators' Instagram handles, widen Instagram (hold until the daily page-load budget resets, about 100 used on 2026-10-13).

**Progress update 2026-10-13 (Shimona, data collection; live-checked 16:45 IST):** `scripts/validate_collection.py`: 5 pass, 6 fail (was 2 / 8).
- **YouTube:** 21,347 videos (20,085 with a length, 94.1%), all 146 collectable verified creators collected (12 months, exact times, newest-30-video comments with times). Added 21 creators found by YouTube API discovery (saved as `probable`, Instagram handle from their own YouTube link, NOT yet checked on Instagram; verified_by 'Claude (YouTube API discovery, 2026-10-13)'); the verified list is 164 rows. Brand-first and keyword searches yield few brand-promoting mid-size creators (about 3 per 10 searches); Tharun Kumar (no Instagram listed) and The Nitesh Fitness Empire (handle not matched) were left out.
- **Snapshots:** 695 posts have 3+ snapshots (target 500). Snapshot job `.github/workflows/snapshot_youtube.yml` runs on GitHub (private repo Shimonasinha/capstone-snapshots, `23 */2 * * *`). GitHub skipped most scheduled runs in the first 14 hours (1 run instead of ~14), so growth curves may have gaps; check again after 2 days and, if still gappy, move the schedule into Supabase (pg_cron + Edge Function). Run time was cut from 11 min to under 2 min by bulk writes in `snapshot_youtube.py` (`split_items`).
- **Instagram:** the collector reads pages (OpenCLI's `instagram profile`/`user` are broken upstream, see the 2026-10-12 entry) and `scripts/ingestion/snapshot_instagram.py` repeats the check; 12 pilot creators (@fitadesss, @itsprashantdesai, @fitandnirbhay, @shubhang_lifts, @unchained.sw, @shivohamofficial, @harshfit7, @chiragbarjatya, @nitinchandila, @theyashanand, @yourfitnesstories, @rishiraj.shekhawat_), 0 blocks over ~250 page loads on 2 days. First growth pairs 13 h apart look sensible (e.g. one post 3,700 -> 6,346 likes). Limits: rounded follower counts, creators may hide likes, first ~12 posts only.
- **Sponsorship labels:** `creator_sponsorship_events` 648 rows (78 creators, 594 with a brand), still RULES not human labels. Hand check in progress: table `sponsorship_review` (migration 20261013000000), 99-item stratified sample in 5 batches of 20, verdicts y / n / f (footer only) / ?; compute precision and miss rate from it before quoting labels.
- **Bugs fixed:** collector now rolls back after a failed creator (44 of 92 creators had been skipped by an aborted transaction); the extractor no longer saves everyday words ('Call') as brands; 7 creators had no `youtube_handle` on their `creators` row and were never collected.
- **Known gaps:** 12 'pending' and 5 'page' rows are not collected; Reddit untouched; Instagram old posts (1,811) are mostly other kinds of creators; `creators.instagram_handle` for Ranveer Allahbadia is still 'beerbiceps' (team decision).

**Progress update 2026-10-12 (Shimona, data-collection quality work; live-checked the same day):**
- **Verified creator list in Supabase:** `creator_verification` (143 rows: 120 confirmed, 6 probable, 12 pending, 5 page; 117 analysis-ready, target 150), `creator_brand_links` (102 pairs, 38 creators), `brands` 74 rows (not-a-brand junk flagged, not deleted). `creators` 259 -> 367 so 125 verified rows carry a `creator_id`. New tables `post_snapshots` / `profile_snapshots` (append-only) are filling for YouTube.
- **Instagram exact post time:** 1,806 of 1,811 posts now have time of day (decoded from the post code; backup `instagram_posts_time_backup_20261012`). The collector keeps exact times (pushed, commit 961c95d), but other people's scheduled collectors still run the OLD code and write YouTube videos with no length and no snapshots (10 creators refreshed 2026-10-11 ~04:30 UTC have 0 of 620 lengths).
- **YouTube collected with the new collector:** 26 creators done, 92 more running (about 5 min each; the driver script is a one-off, not in the repo). Per creator ~200 videos over 12 months, exact times, lengths, snapshots, newest-30-video comments with times. A video's description is empty for ~40% of videos; most creators do not write brand names in text.
- **Sponsorship labels (RULES, NOT hand-verified):** `scripts/ingestion/sponsorship_detector.py` marks a post sponsored on a platform label, a disclosure tag (negation such as "NO PAID PROMOTION" ignored) or a known brand beside a code/@mention; description lines repeated on 4+ of a creator's videos (affiliate footers) are ignored unless the brand is in the title. `creator_sponsorship_events` 66 -> 283 rows (35 creators, 241 with a brand), but 216 YouTube events sit on only 14 creators; my own read of 40 samples found about 37 right. Needs an independent hand check before it is quoted. Backups `youtube_videos_sponsor_backup_20261012`, `instagram_posts_sponsor_backup_20261012`, `*_brand_backup_20261012`. YouTube's own paid-promotion flag was false on 200 of 200 tested videos, so it is not a usable label.
- **Instagram (corrected 2026-10-13):** `opencli` 1.8.8 is installed and connected, but its `instagram profile` / `user` commands are BROKEN for every account since Sept 2026 (Instagram retired the endpoints; the fallback answers HTTP 429; upstream jackwener/OpenCLI#2456, fix PR #2522 not merged). It is NOT our request volume: the first call ever already failed. The collector now skips those commands (`_IG_COMMANDS_DOWN`) and reads the profile page and each post page instead (`parse_profile_page`, `parse_post_extras` in orchestrator.py). Live test on @fitadesss (page loads only, no block): followers/following/posts + bio, post time, exact likes/comments (rounded 'K/M' counts only for big posts), image link (`thumbnail_url`), paid-partnership label, and every comment with its exact time (`instagram_comments.posted_at`; 0 of 24,822 before). New `scripts/ingestion/snapshot_instagram.py` repeats the check for a small creator list with a request budget (8s gap, daily cap 100 page loads, stops at the first block); 7 page loads for 1 creator with 6 young posts. It must run on a machine with the signed-in Chrome + OpenCLI (not GitHub). Limits: 12 post links on the first grid screen, follower counts are rounded ('105K'), `instagram user --limit` max 12. Pilot plan: 5 creators, 1-2 runs a day, then widen.
- **Not done:** 33 more creators to reach 150 (public search is saturating; YouTube API search is the next route), Instagram comment times and image links (0 of 1,811 / 0 of 24,822), Reddit comment times, hand verification of the sponsorship labels, hourly/daily snapshot scheduler on a machine that stays on.

**Progress update 2026-10-05 (Shimona, branch `review2-shimona-temporal`):**
- **S1 Temporal branch: DONE** (commit 593c7cf). Real `sentiment_risk_score` for 149 creators (RoBERTa safety score, shrunk to 0.5), risk propagation over `collaborates_with` + `co_occurs_with` (`risk_alerts.propagated_from_creator_id` source via `scripts/generate_propagated_alerts.py`, dry run by default), pooled lag test and Granger test. Result: the 12-24h cross-platform lag is NOT supported on the available data (positive control works). Artifact `models/temporal_sentiment.json`.
- **S2 CLIP/BERT creator feature score: DONE** (this change). `creator_feature_score` is no longer a constant 0.5: it is brief-dependent relevance (CLIP text-to-image on thumbnails; CLIP-text + mean-pooled BERT on scrubbed text, rank-averaged) blended 0.7/0.3 with engagement/reach percentiles (`ml/feature_score.py`, `backend/app/creator_features.py`, artifact `models/creator_embeddings.npz` from `scripts/compute_creator_embeddings.py`). Models load in a background thread on the first request (fallback 0.5 until ready, about 30 s). Real signal for 167 of 259 creators; the 92 with no text and no image (and creators without data) stay exactly 0.5. Weights 0.7/0.3 are uncalibrated (S3). Measured on real creators: text relevance AUC about 0.85 (fitness brief, 78 matching) vs 0.70 for BERT pooled output alone.
- **Environment note:** Windows Application Control now blocks scipy's `_bglu_dense` DLL on this machine, which broke `scipy.stats` and any `transformers` import. `ml/_scipy_compat.py` skips that unused solver only when it is blocked; Granger now uses `scipy.special`. The policy itself is untouched.
- **S3 Fusion calibration: DONE.** Found and fixed a scale bug: GAIL's spillover is a relative engagement lift (-1 to +23), not 0-1, so `0.4*spillover*100` saturated: 20 creators sat at exactly 100, 4 at 0, and every one of the 187 graph-connected creators had a confidence interval spanning the whole 0-100 range. Fusion now uses the creator's percentile of the GAIL lift (`spillover_unit`, `backend/app/spillover.py`) and a three-branch interval (spillover + sentiment by comment count + feature by evidence, combined in quadrature, `backend/app/fusion.py`): typical width 45-51 pts, none spans the whole range, scores spread 15-89 with no ties at the top. `is_mock_data` is now true only for the demo creators. Weights stay 0.4/0.3/0.3 as documented priors: no outcome exists to fit them (10 labelled lifts, sentiment shows no association: Spearman -0.05, p 0.89), so `scripts/calibrate_fusion.py` instead measures stability (weights moved by up to 0.1 keep a median 9 of the top 10; extreme weightings change the ranking a lot). Results in `models/fusion_calibration.json`. `scripts/backfill_fusion_scores.py` (dry run by default, brief-independent baseline rows) was run with `--write` on 2026-10-05: 258 rows inserted, 259 creators now have a stored baseline row. Stale dashboard/explainability/tooltip strings and `API_CONTRACTS.md` current-state lines were corrected.
- **S6 Graph visualization: DONE.** `frontend/src/components/CreatorGraph.tsx` (d3-force layout, no backend change) on `/explainability`: 187 graph-connected creators, collaboration and co-occurrence links in separate colours, nodes coloured by spillover basis and sized by score for the current results, click a creator to highlight and list their links. The 72 isolated creators are counted, not drawn. Finding: `GET /feature-store/edges/*` returns every relationship in both directions, so the "340 collaboration / 1,414 co-occurrence edges" are directed counts: 170 and 707 unordered pairs. Use pairs when quoting graph size (S4, S8, the report). Learned per-relation weights (E6) are not served by the API yet, so the graph shows raw counts only. Checked in a browser: light and dark mode, phone width (layout fine; tapping single dots is fiddly with 187 nodes), keyboard (Enter/Space select), trained/inferred colours, and a note when current results include creators with no edges (not drawn). No automated frontend tests exist in the repo; verification was manual plus lint, tsc and `next build`.
- **S8 Cross-platform linking audit: DONE (read-only; fixes are the team's call).** `scripts/audit_creator_links.py` -> `models/link_audit.json`; write-up in the documents folder (`S8_Cross_Platform_Linking_Audit.md`). Headlines: only 42 of 259 creators (16%) span 2+ platforms; YouTube links 2-4 of 41 doubtful (Jeet Selal is a fan-club channel, Sania Mirza's is her podcast and the podcast also exists as a separate creator row, Nisha Kumari and Shaan Mukherji rest on identical handle text only); 94 of 257 Instagram handles never fetched; no handle claimed by two creators (the `lebron` duplicate is gone); **Reddit post->creator links about 24% wrong (95% interval 18-28%)**: generic-name businesses and team names matched on common words, and name collisions; **51% of `co_occurs_with` pairs exist only because of 8 roster/auction posts naming 8+ creators**; Instagram post misattribution was 25.7% before Track A's collection-time filter and 0/123 after it, but 861 pre-filter posts (27 sponsored) were never audited; 4 of 66 sponsorship events have no creator; **only 1 of 54 training pairs is measured on 2 platforms and 20 are dropped as cross-platform straddles, so the cross-platform interference claim rests on one pair.** Also added the missing regression test for the null `creator_id` path (`test_feature_store.py`). Second pass added: `collaborates_with` (170 pairs) is 57% team/league affiliations, only 19% listed by both creators, 2 same-entity pairs, none clearly false in a 40-pair hand review; and about 14-17 of the 135 non-athlete/team/league 'creators' are businesses, media or fan pages (shops, gyms, booking businesses, a news page) that Track A's classifier flags 0 of (open item P1.4). Not covered: YouTube video attribution, subreddit routing, the 861 unaudited pre-filter Instagram posts, account type of the 124 athlete/team/league rows. The Reddit/co-occurrence findings matter for S4 (ablations: drop co-occurrence edges; strict-evidence only).
- **S7 Filter and cost error analysis: DONE (read-only; fixes are the team's call).** `scripts/audit_filters_and_cost.py` -> `models/filter_cost_audit.json`; write-up `S7_Filter_and_Cost_Error_Analysis.md` in the documents folder. The standing demo query (Athletic water bottle / 5M / India) reproduces exactly under the FLAT cost this branch uses: 259 considered, 15 budget, 116 region, 128 product, 0 results (the tiered cost on `review-1` gives 16/116/127, so the Review 1 notes' label 'tiered' is wrong). Region filter: of 116 drops, 48 (41%) have explicit India evidence in the data (9 have YouTube country code `IN`, which never equals 'india'; 5 have India/Indian in their own name, which is never read), ~80% are Indian creators by reviewer judgement; 38% of creators have no region text so the filter is a no-op for them. Product filter: 'athlete' is not a substring of 'athletic', so all `athlete` creators are dropped for 'Athletic water bottle' (102 recoverable by stemming, 39/40 hand-checked sensible); 3-letter words match inside other words ('mat' in 'cinematic'; 13 of 24 substring-only keeps were accidents); and the hard product filter leaves a median of 4 of 259 creators over 10 briefs, which defeats S2's relevance ranking. Cost models: ranking is by fusion score so only eligibility changes; category-tiered flips 0-3 creators (top 10 shared 9-10/10), a hypothetical follower-tiered model flips 2-11 (top 10 shared 7-10/10); the 'athlete'/5M/India canary has the same top 10 under all three. Also: the empty-result explanation and tiered cost exist only on branch `review-1` (4 commits not merged into this branch); this branch's dashboard shows an empty list with no explanation for a zero-result query.
- **S1 follow-up 2026-10-06: propagated alerts WRITTEN (13 rows in `riskalert`, source `sentiment_propagation`, `propagated_from_creator_id` set), Monitoring page now populated.** The first dry run (15 alerts) was NOT written: the S8 audit showed it rested on weak Reddit co-occurrence links from non-creator accounts (only 1 of the top 20 on a solid link), which would have put false warnings on real people. Fix: risk propagation now uses `feature_store.build_supported_co_occurrence_edges` (a post counts only if it names BOTH creators in full and links fewer than 8 creators) plus the unchanged collaboration edges; the plain `build_co_occurrence_edges` is untouched because the GAIL graph and checkpoint use it. After the fix 17 of the top 20 rest on a direct, well-supported link; the 13 written are all real people (sources: Sunil Narine, Trent Boult, Suhan Khan; two are 2-hop). Side effect: `sentiment_risk_score` propagation in `/recommendations` now uses the same filtered edges (128 creators receive propagated risk, was 149). Severity is relative within the alerted group and propagated risk values are small (0.01-0.02). Tests: 86 backend pass (2 new).
- **S1 lag, two more tests 2026-10-06 (the brand-facing question).** (a) `scripts/run_event_lag.py` + `ml/temporal/event_study.py` -> `models/event_lag.json`: after creator A's sponsored post, does collaborator B show extra activity (hourly where timestamps allow, else daily) vs B's own pre-event rate, placebo-tested; positive control works (own YouTube upload -> +25 comments in 0-12h, p 0.001); no collaborator reaction found (cross-platform p 0.8-0.98), 10-109 usable pairs, hour-level only for 9 of 62 events (53 Instagram events are date-only). (b) `scripts/run_same_creator_lag.py` + `ml/temporal/performance_lag.py` -> `models/same_creator_lag.json`: for the SAME creator on both platforms, does performance (comments vs the creator's own level, age-adjusted) on YouTube precede Instagram performance a day later? Only 13 creators have >= 6 measured posts on both; 17-30 matched day pairs per lag; lag +1 corr 0.11, p 0.27, detectable |corr| ~0.41 -> INCONCLUSIVE (underpowered), same-day corr 0.24 (p 0.09). No follower history exists (one snapshot per account), so 'growth' is measured as comment performance / attention, not follower growth. What would settle it: snapshot follower counts and post engagement every few hours for several days after each post for creators on both platforms (prospective collection), and recording Instagram like counts and time of day. Tests: 6 + 6 new model-side tests.
- **Analysis tab built 2026-10-06 (`/analysis` in the dashboard).** One interactive page for S1, S2, S3, S6, S7, S8 with a plain verdict at the top of each section (the S1 lag verdict is 'not proven', not hidden). Interactive parts: a lag slider per creator on both platforms (pooled lag profile, click a lag), a brief picker for the S2 top creators, weight sliders for S3 that re-rank the top 10 live, a cost-model picker for the S7 funnel and budget picker for cost stability, and the S6 graph. Data path: `scripts/export_analysis_dashboard.py` collects the saved results (`models/temporal_lag.json`, `event_lag.json`, `same_creator_lag.json`, `fusion_calibration.json`, `filter_cost_audit.json`, `link_audit.json`, `temporal_sentiment.json`) plus the daily curves, the three fusion inputs for six briefs and the live alerts into `models/analysis_dashboard.json` (about 90 KB); `GET /analysis` (`backend/app/routers/analysis.py`, read-only, 4 tests) serves it; the frontend is `frontend/src/app/analysis/page.tsx` + `frontend/src/components/analysis/*` (plain SVG, no new dependency). Refresh after any audit script: rerun the export script (about a minute, it loads CLIP and BERT). The hand-reviewed sample numbers in S7/S8 are kept in the export script (`HAND_REVIEW_*`) so the tab shows them with the data. The graph tab loads edges from the database live (about 7 s in dev). Screenshots: documents folder `analysis_tab_screens/`. Not covered by automated frontend tests (none exist in the repo): checked in a browser, lint, tsc and `next build`.
- **S7 fixes APPLIED 2026-10-06 (code only).** `backend/app/routers/influencers.py`: keyword filters now use whole-word, lightly stemmed matching (a 6+ letter query word may still match inside a longer word; shorter words must match whole), and the region filter also reads the creator name, the country code `IN`, the flag, +91, Indian scripts and 'indian'/'bharat' (whole word). Creators with no region text are still kept. Tests: `backend/tests/test_filters.py` (11), 99 backend tests pass. Live data: the demo query 'Athletic water bottle' / 5M / India went from 0 to 86 results; region drops 116 -> 87, product drops 128 -> 71; median creators per product brief 4 -> 10; 'yoga mat' 18 -> 6 (no more 'mat' inside 'cinematic'). Still open (team decisions): soft product penalty instead of a hard drop, cleaning the 14-17 non-creator accounts, the tiered cost and empty-result message on `review-1`, place-name evidence for the region filter (18 of 87 region drops). The S8 Reddit-link and account-clean-up fixes are NOT applied: they edit Track A's data or the graph GAIL trained on (retraining is Eesha's).
- **Still open for Shimona:** S4 (needs Eesha's E2, not on her branch yet), S5 (E3/E6/E7/E9 landed, E4 not; write per-component status now, re-rate the headline claim after E4). The final stale text on the explainability page about lag insights now says the 12-24h lag is not supported.

---

## 0. How to use this file

- **Start of session:** read this top-to-bottom before proposing anything.
- **Verify before trusting:** every number here was live-checked at the date above, but data
  changes daily. Re-query before acting on a specific figure. See §3 for how.
- **Update it:** when a problem is fixed or a phase completes, edit this file and commit. Don't
  let it drift — a stale plan is worse than none.
- **Ownership:** this file is the orchestrator's. Tracks have their own `HANDOFF.md` in their
  worktrees; those are per-track detail, this is the cross-project view.

---

## 1. What this project is

Influencer–brand matching for sponsorship decisions. A brand states product, budget, and target
region/demographic; the system returns ranked creators with a 0–100 score and an ROI breakdown.

The research contribution is **GAIL (Graph-Adaptive Interference Learning)** — a GNN with
attention that learns *personalised spillover weights* (when a brand sponsors creator X, how
much does collaborator Y benefit?) instead of hand-crafted rules like `spillover = 1/distance`.
Built on established components (GAT via PyTorch Geometric, propensity scoring, doubly-robust
correction, Laplacian regularisation, Granger causality) — a rigorous *application* of known
causal-ML methods to a novel domain, not new theory. That framing is deliberate and defensible;
don't let it drift back toward claiming proofs.

**Architecture:** Dual framework — a GAIL branch (spillover) and a Cross-Platform Temporal
branch (lag detection, sentiment propagation) → combined by a Causal Inference layer →
Fusion Layer (weighted 0–100 score + risk adjustment) → Application Layer (recommendations,
alerts, explainability graph).

### Timeline & milestones (confirmed with the user on 2026-08-11, re-scoped 2026-09-24)

| Milestone | When | Requirement |
|---|---|---|
| **Review 1** | late Aug – early Sep 2026 | **≥50% complete, with working examples** — CLOSED 2026-08-26 |
| **Review 2** | late Oct – early Nov 2026 | **100% pipeline-complete — all PendingWork E/S/A items done** (decided 2026-09-24) |
| **Review 3 / Final submission** | late Nov – early Dec 2026 | **Improvements on a completed pipeline** — hardening, thesis, **deployable not deployed** |

**Deliverables:** source-code repo + thesis paper are **compulsory**. A live demo earns **extra
credit**. **Public deployment is explicitly out of scope until after submission** — the bar for
submission is *deployable* (Docker + security), not *deployed*.

The user's stance: *"don't worry about the deadline, work on it as much as we can."* Take that as
permission to prioritise depth over schedule anxiety.

**Review 1 bar, set by the user 2026-08-11: a basic demo with ~100 creators is sufficient.**
139 candidates already exist on the sheet, so this is comfortably reachable *without* changing
how data collection works. Explicitly:

> **Do not rush or compromise data collection to hit an earlier demo.** The user's position:
> *"better the data, better the model, better the project."* Review 1 is a checkpoint, not the
> goal. Quality of process — relevance verification, honest edge counts, no padding — takes
> precedence over demo timing. If a choice arises between a denser demo and cleaner data, choose
> cleaner data.

### Review-readiness criteria (added 2026-08-16) — raw volume alone does NOT satisfy any of these

This session's central lesson: creator count and row counts are *necessary but not sufficient*.
The real bottleneck at every stage has turned out to be structural (does an edge resolve, does an
event have `brand_id`, does a connected neighbor have pre-event history) — not volume. Check the
structural criteria before declaring a milestone's data "ready," not just the headline counts.

**Review 1 — "basic dry run," the bar for THIS check-in:**
- [x] ~100 creators (259, well past the floor — 260→259 after Athletics dedup)
- [x] **Computable training pairs: 54** (2026-08-26, canonical `pair_count.py` 138 checks / 53 dated events / 40 yielding / 23 directed / 19 undirected / 170 graph — was 52 on 2026-08-21, +2 from 8 newly sponsored+connected creators; see P0.4)
- [x] Real collaboration edges: 170 (340 directed / 1,414 `co_occurs_with`, giant 185 — unchanged undirected since bulk promotion, still healthy).
- [x] At least one creator with comment volume (Reddit/IG/YT) sufficient to sanity-check a sentiment/reputation signal — **PASS 2026-08-26 Track B**: 149/259 with ≥1 comment (134k pools: 54k YT + 24.8k IG + 55k Reddit) — top-3 50 texts each (Ronaldo 9012, Carry 5174, Kohli 4283), SST-2 mean range 0.346 std>0.8, English-only mislabels noted — `reputation_score` still 0% `§5` but volume sufficient for sanity.

**Review 2 — "GAIL trains for real, fusion produces real scores":**
- [ ] Sponsorship events: 300+ (established Phase 2 target)
- [ ] Real resolved edges: 500+ (established Phase 2 target)
- [ ] A meaningful count of *computable* training pairs (connected + straddling) — dozens at
      minimum; re-derive this target once Review 1's actual resolve-rate is known, don't assume
      it scales linearly with event count given the structural sparsity already observed.
- [ ] Brands with real scraped profile data, not just mention-extracted names
- [ ] Comment volume sufficient to compute a real per-creator sentiment signal across most of the
      creator set, not just the best-covered few

**Submission — "complete, deployable":**
- [ ] Dataset stabilized (no active collection actively invalidating demo state during evaluation)
- [ ] Data supports both branches (GAIL + Temporal) for the full creator set or an honestly-scoped
      subset, stated plainly in the thesis rather than silently narrowed
- [ ] Limitations section grounded in what was actually found this project (observational data,
      disclosure-based treatment labels, structural graph sparsity, India-skewed sample,
      engagement-per-rupee not true ROI) — not a generic boilerplate list

### 2026-09-24 Re-scope — Review 2 = pipeline-complete, Review 3 = improve (team decision)

Source: `Capstone — Pending Work & Track Allocation.pdf` (2026-09-20, repo-root untracked).
Per the user 2026-09-24, **all 21 PendingWork items are the Review 2 exit gate**; anything
leftover plus hardening moves to Review 3. Timeline is explicitly not the constraint — scope
is. Extra data collection and actual public deployment stay out of scope for this comparison.

- **Review 2 DONE means:** Eesha E1–E10 (E1 propensity fix, E2 per-(event,neighbour) targets,
  E3 doubly-robust, E4 causal-supervised attention, E5 mismeasured-treatment, E6
  multi-relational exposure, E7 second GNN layer, E8 hidden-dim, E9 rename, E10 bot wiring) +
  Shimona S1–S8 (S1 Temporal branch, S2 CLIP/BERT, S3 fusion calibration, S4 evaluation suite,
  S5 novelty rewrite, S6 graph viz, S7 filter/cost error analysis, S8 cross-platform audit) +
  Akshat A1–A3 (A1 `ml/` vs `backend/app/gail/` dedup first, A2 test/build gate, A3 canaries).
- **Old Review 2 data targets above (300+ events / 500+ edges / brand profiles / sentiment
  volume) are background, not the Review 2 exit gate** — they need collection scale-up, which
  is excluded from this re-scope by explicit user instruction.
- **Review 3 / submission = improve a completed pipeline:** any unfinished E/S/A items, full
  security pass beyond the A2 smoke test (auth, Supabase password rotation, RLS/anon-key
  review, dependency audit), brand-profile enrichment, thesis + repo cleanup + HLD
  Twitter→Instagram fix, dataset stabilization / honestly-scoped subset declaration, demo
  polish. Bar stays *deployable, not deployed*.

### 2026-08-26 - Review 1 CLOSED - end-to-end wired, demoable

Frozen main @ this commit + tag review1-2026-08-26 + branch review-1. Live DB: 259 creators / 54 pairs (138 checks, 53 events, 40 yielding, 23 directed/19 undirected, 170 graph) / 340 directed collaborates_with + 1,414 co_occurs_with (giant 185, 72 isolates 27.8%) / 6,153 posts (1,607 YT /1,811 IG 100% dated /2,748 Reddit) / 58 is_sponsored IG +3 YT +0 Reddit (18 with brand_id) / 19 brands / 134k comments (54k YT +24.8k IG +55k Reddit). Track A 918fb5c re-verified 54; B 5f8706f prod artifact models/gail_checkpoint.pt c6488a6 (N=10, hw 3.28 trained +/-13pts, inferred x1.6 +/-21pts, propensity mean 0.61 after z-score fix, sentiment 149/259 PASS); C b3905ef wired backend/app/spillover.py:1 + fusion.py:57 (basis trained|inferred|isolated|placeholder, w2 placeholder) 65ec502 - 3 archetypes c4b20 Virat trained 21.61->100 [0-100] / 89972 AB inferred 1.19->77 [0-100] / 78e48 _bungy isolated 0.5->50 [40-60]; D 5861f4d SpilloverBadge.tsx:1 wired, npm run build + lint pass, CORS localhost:3000 verified, 5 routes 200. Review 1 demo: brand-input -> dashboard -> explainability shows emerald/violet/zinc badges + wide CI + placeholder footnotes - honest small-N thesis story. PENDING_TRACK_D.md deleted. Next: Review 2 (300+ events /500+ edges / sentiment reputation_score real / brand profile data).

### 1a. Batch-readiness criteria (added 2026-08-18) — when to stop deepening the current 259 and
promote the next batch

The user's stated policy: loop data collection on the current creator set until EITHER it's
genuinely exhausted across all three platforms, or a real sufficiency threshold is hit — whichever
comes first. Don't promote the next batch before then. Concretely:

**"Exhausted" (stop looping regardless of pair count) — ALL of:**
- [ ] Every one of the 259 creators has been *attempted* on all 3 platforms — not necessarily
      successfully, but no creator sits fully untouched on YouTube or Reddit. (Instagram is
      already effectively maxed given the adapter block; browser-only coverage work counts here.)
- [x] **DONE 2026-08-18.** Track C confirmed (by reading the code, not inferring) that real
      multi-platform disclosure detection has existed since Weeks 7-8 — the "32, Instagram-only"
      result reflected zero real signal at the old, much smaller YouTube/Reddit scale, not an
      unbuilt capability. Re-run at the new scale (1,227 YouTube videos/39 creators, 681 Reddit
      posts) found 2 new YouTube events (`keralablasters`, via "brought to you by"), 0 on Reddit.
      Neither creator is graph-connected yet, so no new pair this round — but the mechanism is
      now confirmed real and current, not a guess.
- [ ] Every connected, dated sponsorship event has been checked cross-platform for a straddle
      (routine now per §5 P0.4, not a manual spot-check).
- [ ] Computable training pairs have stopped growing for 2 consecutive rounds despite the above
      being satisfied — the real diminishing-returns signal.

**"Sufficient" (can stop early even if not fully exhausted) — the real target:**
- [x] **DONE 2026-08-18. Computable training pairs ≥ 20** — the bare floor for any legitimate
      held-out split. **~38, independently confirmed** (see P0.4). The loop's own "Sufficient"
      stop condition fired for real after 13 cycles, not a premature/false stop.
- [x] Real resolved collaboration edges: 170, up from 161 — healthy trend, tracked each round.
- [ ] Reddit unblocked for a meaningful share of the 231 handle-named creators (real-name
      backfill via free bio/channel-title sources, gated on Instagram deepening producing names —
      see §5 P0.5).

Report against this checklist every round, not just raw creator/post/event counts — a round that
grows posts but doesn't move the pair count or check off one of these boxes hasn't actually made
the batch more ready.

---

## 2. THE CENTRAL PROBLEM — **caption cause RESOLVED, edge cause pivoted** *(updated 2026-08-11 post-Phase-1A)*

GAIL trains on `(sponsored creator → neighbour engagement change)` pairs, so the effective
sample size is **sponsorship events**, not creator count. For weeks the team optimised creator
count, which was never the binding constraint.

### ✅ Cause 1 — captions: FIXED, and the hypothesis was half-wrong

**The real root cause was simpler than assumed: one cause, not two bugs.** `parse_caption()` was
wired in at commit `8b493d1` (2026-08-10 01:19), but all 97 rows were fetched 2026-08-08 →
2026-08-09 — *entirely before it*. The scraper was already correct; **nothing ever re-scraped the
stale rows.** The two visible signatures were real but downstream of that one cause:
- 49 NULL captions correlate perfectly with `media_type IS NULL` (listing-sourced rows, empty
  metadata dict ⇒ every field None)
- 48 rows clipped at exactly 100 (`opencli instagram user` truncates at exactly 100)

*(Doc correction: this file previously cited lengths "101, 104" from an orchestrator sample.
Track A's analysis found a hard ceiling of exactly 100. The discrepancy is unresolved and
immaterial — the substantive finding, that truncation was deleting end-of-caption disclosures,
is confirmed by both.)*

**Verified live after the fix:** 60 non-null captions, 60 distinct, max 1058 chars, avg 257,
35 rows >100 chars. 37 remain NULL — see the open decision below.

**THE SIGNAL IS REAL.** Genuine disclosures now visible that truncation had destroyed:
`mirzasaniar` "…Milton, a brand that's Made in India… **#ad**" · `virat.kohli` "…@oakleymeta AI
glasses… **#Ad**" · `virat.kohli` "…**#Ad** #VisitDubai" · `neeraj____chopra` "After two seasons
as Ambassador… Co-Owner @ubsathleticskidscup". **Every one sits at the END of its caption** —
exactly where the 100-char cut was landing. This is direct evidence that "0 sponsorships" was a
scraping artifact. ⇒ **Scenario C is NOT triggered.** Honest read: *signal exists in ~5% of
captions, now needs Track C to re-label* — not "confirmed zero on good captions."

### ⚠️ Cause 2 — edges: table populated, but the assumed MECHANISM largely failed

`creator_related_accounts` went 0 → 1 row (1 resolvable edge: `virat.kohli` →
`royalchallengers.bengaluru`), written correctly with `relation_type='frequent_collaborator'`.

**But the team→player mechanism doesn't work as assumed.** Across 6 promoted team accounts, only
2 distinct handles were @-tagged in captions at all, neither an existing creator. **IPL/ISL team
accounts caption with hashtags, not player tags.** The single real edge came from a *creator's*
caption, not a team post.

**Best unexploited lead:** Instagram's **collab co-author list** ("X and N others"), rendered in
the page markdown — a genuine, native collaboration fact rather than an inferred one. Track A
deliberately did not build it rather than ship a second unvalidated mechanism in one round.
Also worth checking: Instagram's **"tagged people"** on posts, which is separate from caption
@-mentions and may be where teams actually tag players.

### ✅ RESOLVED 2026-08-11 — the 37 NULL captions were COLLAB POSTS, not contamination

Track A settled this with three independent lines of evidence from real post pages. The decisive
one: on `virat.kohli`'s live grid, **5 of 7 NULL-caption posts were still present — a higher hit
rate than with-caption posts (19 of 33)**. Contamination would show the opposite (absent from the
grid). Also: 11 of 18 probed posts showed the stored creator's handle in the co-author header
block, and zero showed the pure-contamination signature.

⇒ **Keep them.** On a collab post the caption belongs to the primary author, so a parse anchored
to the stored creator correctly returns nothing. Recovering them took captions from 60 → 82
non-null (82/82 distinct, max 1142).

**Bonus finding, unprompted and important:** 3 posts carry Instagram's native **"Paid
partnership" label**, rendered on the page but entirely absent from caption text. **A
caption-only labeler structurally cannot see this** — and it's Instagram's own declaration, so
likely the highest-precision sponsorship signal available. `instagram_posts` has no column for
it ⇒ **the project's first genuine schema addition.** Split: Track A adds/populates a raw
observation column (`has_paid_partnership_label`), Track C reads it when computing `is_sponsored`.

### ⚠️ Instagram rate limit hit 2026-08-11 (HTTP 429)

Self-caused and the arithmetic is clear: ~9h discovery loop + 97-post caption backfill + 97-post
collab pass (~200 post-page fetches in a few hours) + pilot. Affects **any** handle including a
control. Categorically different from the intermittent `HTTP 400 - make sure you are logged in`
seen all session.

**Diagnostic from the user: they can browse Instagram normally, logged in as the same account in
the same browser.** ⇒ rate-based throttle on the automation's request pattern, not an
account-level block — the recoverable kind. Response: wait, probe with a *single* call, and
follow `agent-reach`'s documented limits (`.agents/skills/agent-reach/references/social.md`)
rather than an ad-hoc strategy.

**Consequence for planning:** Instagram is both the slowest platform *and* the only one carrying
caption/collab/paid-partnership signal. Deepening all 55 on Instagram is not feasible before
Review 1 — the binding constraint is the rate limit, not time. Agreed plan: **YouTube across all
55 now** (API-based, unlimited, descriptions never truncated — also the Scenario-D fallback),
**Reddit second** unattended over days (~7.7 min/creator), **Instagram last** on ~15–20
high-signal creators with a hard per-day request budget. Depth of signal beats breadth.

### 🔗 Co-author handling — curation, not auto-promotion *(decided 2026-08-11)*

The collab extractor works, but from a 10-post sample it surfaced **18 distinct real co-authors
and zero were existing creators**, so they resolve to nothing. Many are orgs/brands/politicians
(`commonwealthsport`, `globalboxingseries`, `naralokesh`) — bulk-promoting them would pollute the
creator set and re-import the #fitindia-collision problem.

**Decision:** discovered co-authors go to the **Google Sheet as candidates for user review**,
through the existing curation flow, with provenance in `notes` and signals in the new
`brand_signals` column. Approved → promoted → the edges light up.

**Key mechanic Track A initially missed:** relationship rows should be written **immediately**
even when the co-author isn't a creator yet. Track C's resolver matches handles *at resolution
time*, so an unresolvable row costs nothing, is silently skipped, and **auto-resolves the moment
the co-author is promoted** — no re-scrape needed. Since these facts cost rate-limited Instagram
fetches to obtain and are nearly free to store, write them all. Report **rows written and
resolved separately**; they will now differ, which is correct rather than a problem.

### 🔗 Possible link between the two gaps — worth checking early
The 37 still-NULL captions are posts on a creator's grid authored by *someone else* (e.g. on
`kingjames`: `sixers`, `ljfamfoundation`, `chrisjohnsonhoops`). Two very different explanations,
with opposite implications:
- **Instagram collab posts** — co-authored, legitimately appear on both grids ⇒ **these ARE the
  collaboration edges we're missing**, and the NULL captions are a symptom of a signal we want.
- **Scraper contamination** — suggested/unrelated posts wrongly attributed ⇒ **bad data that
  inflates a creator's content count and could cause false sponsorship attribution**, and should
  be removed.
Distinguishing these is high-value and cheap. Do it before deciding what to do with the 37 rows.

---

## 3. Verified reference data (re-check before relying on it)

### 3.1 How to query the live DB (orchestrator can do this directly)

```bash
K="<publishable key — see §3.4>"
curl -s "https://fhbgbtxdtfluzohxyivg.supabase.co/rest/v1/<table>?select=*&limit=5" -H "apikey: $K"
# row count:
curl -s ".../rest/v1/<table>?select=id" -H "apikey: $K" -H "Prefer: count=exact" -H "Range: 0-0" -D - -o /dev/null | grep -i content-range
```
No `psycopg2` in the orchestrator env; REST is the route. **Read-only in practice — never write.**

### 3.2c Live DB state — **Track A verified 2026-08-16, close of Phase 1G** (NEWEST — supersedes 3.2a/3.2b for creators + edges)

| Table | Rows | Note |
|---|---|---|
| `creators` | **259** | was 63. Bulk promotion of 258 accepted sheet rows: 196 new, 60 enriched, **0 duplicates/collisions** |
| `creator_related_accounts` | 505 rows / **157 resolved** / **152 DISTINCT PAIRS** | was 15 resolved / 10 pairs. **No new scraping** — the same 505 rows resolve now that the endpoints are creators |
| Resolve rate | **31%** | was 2.4% |
| Creator categories | athlete 95 · fitness_influencer 82 · lifestyle_influencer 38 · team 20 · other 15 · league 9 | 132 of 146 `other` sheet rows were misclassified and corrected |
| Sheet | 994 rows | 258 accepted / 230 rejected / 506 not-decided. `approval_status` untouched by agents |
| IG coverage | 31 of 259 creators | **228 creators now have no Instagram content** — deepening is the gap |

🚨 **THE "STRUCTURALLY SPARSE GRAPH" FINDING IS OBSOLETE — Tracks B and C must be told.**
Both recorded "10 pairs / 2.4% resolve rate, structurally sparse, not a coverage gap" as a
settled property. It was true *of the 63-creator set* and is now **152 pairs at 31%**. The
graph was never structurally sparse; its endpoints simply weren't creators yet. Track B in
particular planned its first training run around a 10-pair graph.

**What this round proves about the lever** (Phase 1F predicted it; this confirms it at scale):

| Action | Distinct pairs added |
|---|---|
| Covering 7 new creators (Phase 1F — 275 posts scraped) | **0** |
| Promoting 196 already-observed co-authors (this round — no scraping at all) | **+142** |

⚠️ **Brands found accepted on the sheet, excluded from promotion and flagged for the user:**
`sporting.beyond` ("Sporting Beyond Pvt Ltd", a company — **already in `creators`** from a
Phase 1E targeted promotion and carrying a live resolved edge, so it was left in place rather
than deleted) and `sportsclaus` (sports media company). Agents **cannot** auto-reject these:
`approval_status` is the user's column. The brand is instead recorded against the creator it
was seen on via `brand_signals`. Note `brand_signals` is **live on the sheet now** — §3.4
below still calls it "TO ADD", which is stale.

### 3.2a Live DB state — **Track A verified 2026-08-15, close of Phase 1F** (superseded by 3.2c for creators/edges)

| Table | Rows | Note |
|---|---|---|
| `creators` | **63** | +3, all targeted promotions naming the row each resolved |
| `creator_related_accounts` | **505 rows / 15 resolved / 10 DISTINCT PAIRS** | **report pairs.** 15 resolved rows include reciprocal directions of the same collaboration; deduplicate with `least(name)/greatest(name)` |
| `instagram_posts` | **1,092** | 31 of 63 creators covered (was 24). **120 unscanned** — a throttle stopped the scan |
| `instagram_comments` | **13,097** | +1,546 |
| `has_paid_partnership_label` true | **12** | +1; Track C's highest-precision sponsorship signal |
| `is_sponsored=true` / with `brand_id` | 11 / 9 | unchanged — Track C hasn't relabelled the new posts yet |
| `brands` | 10 | unchanged |
| Sheet | 488 rows / 131 accepted | grown by co-author candidate pushes |

**Pairs added this round: 7 → 10. All 3 from targeted promotion; 0 from covering 7 new
creators.** That is the second independent confirmation that coverage does not add graph
structure — see the P0.2 rewrite above.

### 3.2b Live DB state — **Track C verified 2026-08-15, Phase 1F re-labeling** (newest; supersedes 3.2a's labeling row)

| Table | Rows | Note |
|---|---|---|
| `creators` | 63 | unchanged this round |
| `creator_related_accounts` | 505 rows / 15 resolved / 10 distinct pairs | unchanged; independently reproduced a third time (Track A → orchestrator → Track C, all match). API returns 20 edges = 2 directed edges per pair, not 20 relationships — documented for Track B. |
| `instagram_posts` | 1,092 | unchanged this round |
| `is_sponsored=true` (all platforms) | **18** | +7, all Instagram, 0 YouTube/Reddit. Force-relabel (`?force=true`) caught the 267 posts Phase 1F scraped that a default run would have skipped (they default to `is_sponsored=false`, not null). 13 via caption regex, **5 via `has_paid_partnership_label` only** — including one post with a still-empty caption, the case text-only labeling structurally cannot reach. |
| `is_sponsored=true` with `brand_id` | **10 of 18** | was 9 of 11. `/feature-store/edges/sponsorships` reconciles exactly against this raw count — zero gap between endpoint and data. 8 of 18 still lack `brand_id` — Track A's brand extraction lagging one round behind labeling, expected/routine. |
| `brands` | 10 | unchanged |
| Sheet | 488 rows / 131 accepted | unchanged this round |

**Collaboration graph is now a confirmed structural property, stated for Track B's benefit before
it starts training: 10 real pairs across 63 creators, ~2.4% resolve rate.** Not a bug, not a
coverage gap — verified twice more this round (Track A's scan of 267 new posts added 0 pairs;
Track C reproduced the resolver's own logic directly against the DB and got the identical count).
Track B should expect a small, sparse, but genuinely real graph on its first training attempt.

### 3.2 ~~Live DB state — orchestrator-verified 2026-08-14 after Phase 1E~~ (SUPERSEDED by 3.2a)

| Table | Rows | Note |
|---|---|---|
| `creators` | **60** | +4, all targeted promotions that each immediately resolved a specific pending edge (see P0.2) |
| `creator_related_accounts` | **316** | **10 resolved** (independently re-derived by the orchestrator via handle cross-reference, matches Track A's own count exactly) |
| `instagram_posts` | **825** | 24 of 60 creators now have IG content (was 13). 359 of the 424 new posts were never scanned for co-authors — see throttle note below. |
| `is_sponsored=true` (Instagram) | **11** | unchanged this round — expected, the new posts weren't scanned |
| `is_sponsored=true` with `brand_id` set | **9 of 11** | was 1 of 11. Root cause: extractor only matched explicit phrases; the dominant real pattern is a branded hashtag/@mention, which had no rule at all. 2 left deliberately unlinked (ambiguous/empty caption) rather than guessed — correct call given this is the sole treatment-label source. |
| `brands` | 10 | +1 since the report was written (`optimumnutri`) — background movement, not an error |
| Reddit co-occurrence | **0, confirmed structural not a bug** | 435 `reddit_post_creators` rows = 435 distinct posts, perfect 1:1. 427 of 435 rows belong to 5 creators; 8 of 13 have exactly 1 row each. Each post is found via a single creator's search, so overlap can't occur without two creators being searched in the *same* subreddit. More per-creator scraping won't fix this — needs a shared-subreddit search strategy, a deliberate mechanism decision. |
| Sheet | — | 112 of 116 approved rows deliberately NOT promoted (would add creators without adding training pairs) — see the targeted-promotion rule below |

All figures re-verified directly via REST by the orchestrator, independent of Track A's own
report — every number matched exactly except the `brands` count noted above.

**⚠️ New standing rule — never approve brand/company accounts on the sheet.** Brands
(e.g. Milton, One8) reach the `brands` table automatically via disclosure-text extraction on
sponsored content — never via the creator-promotion path. Approving one as a creator would (a)
have no valid `category` value and (b) let it resolve into `creator_related_accounts` as a false
"collaboration" edge, corrupting the sponsorship/collaboration distinction GAIL depends on. The
targeted-promotion mechanic (below) does NOT filter brand vs. person — user review is currently
the only safeguard.

**⚠️ Targeted-promotion rule (in effect since Phase 1E):** do not bulk-promote approved sheet
rows. Promote a candidate ONLY if their handle already appears in an unresolved
`creator_related_accounts` row — i.e. promoting them immediately resolves a specific known edge.
Report which row each promotion resolved. This is deliberate: general creator growth doesn't
help Track B until it produces a training pair.

**⚠️ Instagram throttle — real finding, and a verification-method lesson.** Not a 429; it's a
network-layer `chrome-error://chromewebdata/` failure that a 429-keyed check doesn't catch. A
**single-request probe after stopping is not a valid clearance test** — Track A confirmed
recovery with 3 passing single checks, then sustained scanning re-tripped it in 4 posts (~45s).
Needs a real cooldown (hours, not minutes) before the next sustained scan. Recorded in Track A's
HANDOFF.md as a standing lesson, since the same flawed single-probe method was used on the
earlier 429 too. The consecutive-failure abort caught the re-trip in 48s instead of ~54 minutes —
keep that mechanism.

**~~Outstanding, highest priority for the next Track A round:~~ DONE 2026-08-15 — and the
answer was NO.** The 359 posts were scanned (0 failures, 70 min); the throttle had genuinely
cleared, verified by a **sustained 12-request test** rather than the single probe that misled
the previous round. Resolved edges did **not** grow super-linearly — they did not grow at all
(316 → 423 rows, RESOLVED 10 → 10). Track A's own prediction is now **disproven, not
untested**. See the P0.2 rewrite above; do not re-open this as an open question.

**⚠️ Process incident, 2026-08-14:** the orchestrator edited this file after Phase 1C but never
committed/pushed it — Track A's Phase 1D round pulled `origin/main` and correctly found no trace
of Phase 1C content (still at commit `70cab91`). Not a Track A bug. **Lesson: this file is
useless to the other three track sessions unless it's actually pushed, every time.**

**Instagram grid-stall — characterized, one real bug fixed, root cause still open.** Byte-identical
failure sequence reproduced across Aug 11/Aug 12 logs; ruled out (with evidence, not assumption):
positional degradation, rate-limiting/time-of-day, account size. Isolated to the browser-driven
grid path specifically (`opencli instagram user` never failed in 3 days; only `browser open` →
`find --css` returns nothing). **Fixed:** a real tab-lease leak — `process_creator`'s
no-post-links raise sat before its session close, leaking up to 8 sessions/tabs per bad run.
Fixed on that path + a deterministic-name backstop in `run_batch`'s except. **Not yet proven** to
be the actual cause of the stall (that's a hypothesis pending re-measurement) — the discriminating
test is queued: run a consistently-failing creator (`cristiano`) alone as the first call of a
fresh session. Aug 13's 5×30s timeouts are a separate bug, recorded separately, not conflated.

⚠️ **Incident 2026-08-11, resolved:** Track A's first backfill auto-detected each post's author
instead of anchoring on the known username. Instagram post pages render *suggested* posts, so it
frequently grabbed a different post's author and caption — writing wrong captions to ~33 of 97
rows. Caught via distinctive signature (94 rows carrying only 61 distinct captions; one post_id
reporting two different authors across runs). Cleared and rebuilt with anchored parsing plus a
URL assertion. **Verified clean: 60/60 distinct.** Root enabler, in Track A's own words: `extract`
returns a `url` field that was never checked against the requested post — a violation of this
project's own "verify data arrived, not that code ran" rule, *while fixing an instance of that
same rule*. Both a good catch and a standing warning.

### 3.3 Schema — 13 tables + 1 view. **No schema changes needed.**

Every table, FK and `brand_id` column the model needs already exists. The gap is population,
not design.

**`creators`** (seed table)
`creator_id uuid PK · name · category · youtube_handle · instagram_handle · reddit_handles text[] · notes · created_at · updated_at · reddit_topic_subs text[]`
- ⚠️ **`category` has a CHECK constraint** — only: `athlete, team, league, fitness_influencer,
  lifestyle_influencer, other`. Any invented value hard-fails the insert.
- ⚠️ **No `follower_count` column.** It lives on `instagram_profiles.follower_count`.
- `reddit_handles` = creator-SPECIFIC subs (safe to take feed broadly).
  `reddit_topic_subs` = general/topic subs (must be name-searched, never taken as a whole feed —
  taking them broadly produced ~3,000 rows of noise and an 88% purge).

**`creator_related_accounts`** (collaboration edge source)
`id · creator_id→creators · platform CHECK(youtube|instagram|reddit) · handle text · relation_type text · created_at · UNIQUE(creator_id, platform, handle)`
- ⚠️ **`relation_type` must be exactly `"frequent_collaborator"`** — Track C's
  `build_collaboration_edges()` filters on that literal string and silently ignores anything else.
- ⚠️ **Both endpoints must already exist as `creators` rows.** The resolver matches `handle`
  text against other creators' own handles and silently skips unresolvable rows. Promote players
  to `creators` *before* writing relationship rows, or you get zero edges with no error.
- ⚠️ Resolver drops **ambiguous handles** (2+ creators claiming the same one). Duplicate rows
  both claiming reddit handle `"lebron"` are **still live in prod** — those creators will
  silently yield no edges until merged.

**`brands`**
`brand_id uuid PK · name (UNIQUE) · category · youtube_handle · instagram_handle · reddit_handle · follower_count · post_count · is_verified · source (default 'sponsorship_mention') · fetched_at · created_at · updated_at`
- ⚠️ **Documented scope boundary:** populated ONLY from brand names extracted from
  sponsorship-disclosure text on creator content — explicitly *"not an independent brand-discovery
  crawl."* The `source` column exists for if that changes. If brand-anchored discovery is ever
  used, use a **distinct source value** (e.g. `'brand_account_discovery'`) and note it in
  SCHEMA.md — Track B needs to distinguish provenance, because crawled brands have real profile
  data while mention-extracted ones have only a name.
- ⚠️ **There is no creator↔brand table.** The relationship exists ONLY as `brand_id` on content
  rows (`youtube_videos`, `instagram_posts`, `reddit_posts`). A brand's own posts have nowhere to
  live (brands aren't creators). So brand-anchored discovery can only be a *creator-discovery*
  mechanism; sponsorship linkage must come from the creator's own content.

**Platform tables:** `youtube_channels/videos/comments`, `instagram_profiles/posts/comments`,
`reddit_profiles/posts/comments`, `reddit_post_creators` (junction).
- `instagram_profiles` PK is `username`, `creator_id` FK is **nullable** — it holds comment
  authors too. Don't clobber `creator_id=null` rows; they're deliberately lean.
- `is_sponsored` / `sponsorship_raw_matches` on content tables are **Track C's** to populate.
- `is_bot_flagged` / `bot_score` are **Track B's** to populate.

**View:** `creator_sponsorship_events` — UNION of `is_sponsored=true` rows across all three
platform tables, carrying `brand_id`. Track B builds sponsors/sponsored_by edges from this.

**Migrations (6, in `supabase/migrations/`):** `init_schema`, `fix_missing_reddit_indexes`,
`add_brands`, `dedupe_creators`, `reddit_post_creators_junction`, `reddit_topic_subs`.
Live DB agrees with them.

### 3.4 Google Sheet (curation surface)

<https://docs.google.com/spreadsheets/d/1UX9K3gQnh4roMgTi0cy3Sxm82kTLDkZI9w4jJELFVPQ/edit>

Columns: `name · approval_status · category · youtube_handle · instagram_handle ·
follower_count · reddit_handles · notes · reddit_topic_subs`
- **`approval_status`** is the user's column — values `accepted` / `rejected` / blank. **Agents
  must never write to it.** Anything not exactly `accepted`/`rejected` = unreviewed.
- **TO ADD: `brand_signals`** — brands tagged in bio, discount codes, paid-collab language.
  Free to capture (the bio is already read for the relevance check) and predicts which creators
  will actually yield sponsorship events. Track A adds this via its Sheets API access.
- ⚠️ Sheet has **no `creator_id`** — promote must match on handle.
- ⚠️ Sheet sometimes holds data the DB lacks (e.g. `athleanx` has an instagram_handle on the
  sheet, NULL in DB) ⇒ promote is an **upsert**, not insert-only.
- ⚠️ Known glitch: row `nisha_optimist` has its own username in `approval_status`.
- Current: 139 rows — **19 accepted, 4 rejected, ~116 unreviewed.**

### 3.4b ⚠️ `DATABASE_URL` CHANGED 2026-08-14 — affects all four tracks

If `psycopg2.connect()` starts failing with
`could not translate host name "db.fhbgbtxdtfluzohxyivg.supabase.co" to address`, **the
project is fine and the password is fine.** Supabase's *direct* connection host is
**IPv6-only** (AAAA record, no A record), and the dev machine lost its IPv6 route — a direct
IPv6 TCP connect returns `WinError 10051, network unreachable` while every other hostname
resolves normally.

**Fix — a one-line DSN swap to the IPv4 session-mode pooler** (note the `postgres.<ref>` user):

```
DATABASE_URL=postgresql://postgres.fhbgbtxdtfluzohxyivg:<pwd>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

Verified by Track A 2026-08-14 (`select count(*) from creators` → 60, matching the last
known-good figure). Applied to Track A's `.env`; **B, C and D must make the same change in
their own gitignored `.env` files** — this is per-worktree config, not something a commit
propagates. Keep the old direct line commented for when IPv6 returns.

Lesson worth keeping: "host not found" was neither a DNS outage nor a credentials problem —
the name resolved fine, just to an address family with no route. Check the DNS *record type*
before concluding a service is gone.

### 3.5 Environment / access

| Thing | Detail |
|---|---|
| Supabase project | `https://fhbgbtxdtfluzohxyivg.supabase.co` |
| Credentials | In each track's gitignored `.env`. Password was pasted in chat 2026-08-11 — **should be rotated.** |
| Repo | `github.com/akshatnavlani/Capstone`, `main` + 4 track branches |
| Worktrees | `D:\Capstone-worktrees\track-{a-data-infra, b-ml-core, c-fusion-backend, d-frontend-app}` |
| Apify | **Genuinely unavailable** — checked across 3 restart cycles. Stop re-checking. |
| Docker | Installed, verified working (non-standard path: `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe`) |
| claude-in-chrome | Works in Track D. Diagnostic use only — it competes with OpenCLI for the browser. |
| Scraping | YouTube = official Data API (no contention). Instagram + Reddit = OpenCLI browser automation. |

### 3.6 ⚠️ Parallelisation rule (confirmed by a real incident)

OpenCLI arbitrates browser access via **tab leases from one daemon per Chrome profile**.

| Combination | Safe? |
|---|---|
| YouTube ∥ anything | ✅ independent transport (plain HTTP API) |
| Instagram ∥ Reddit | ❌ **starved Reddit completely** (0 of 8 creators) |
| Any two OpenCLI platforms | ❌ same mechanism |
| Two sub-agents ∥ same platform | ❌ same session, same rate limit |

**Safe pattern:** one sub-agent for YouTube, one doing Instagram→Reddit *sequentially*.

---

## 4. Track ownership (verified in code — don't blur these)

| Layer | Owner | Where |
|---|---|---|
| Scraping, DB population, raw relationship data | **A** Data/Infra | `scripts/ingestion/orchestrator.py`, `supabase/migrations/` |
| Edge *resolution* (DB rows → weighted edge lists), disclosure labeling, feature store, fusion scoring, API | **C** Fusion+Backend | `backend/app/feature_store.py`, `labeling`, `fusion.py` |
| Graph *construction* (edge lists → PyG HeteroData), GAIL, bot detection, CLIP/BERT | **B** ML-Core | `ml/schema.py`, `ml/gail_model.py`, `ml/training.py` |
| UI, explainability graph, Docker, browser verification | **D** Frontend+App | `frontend/` |

**Track A does NOT build the graph.** It collects relationship *facts*. C resolves them into
edges. B builds the tensor and trains.

---

## 5. PROBLEMS — ranked, with fix ideas

### P0 — blocking the thesis's core claim

**✅ P0.1 Captions — DONE 2026-08-11.** Root cause was stale rows never re-scraped after the
parser fix landed, not two separate bugs. Backfilled; 60 distinct captions, real disclosures
recovered. See §2.

**✅ P0.2 — RETIRED 2026-08-16/17. The graph was never structurally sparse — its endpoints
just weren't creators yet.** Everything below (2026-08-15) was a real, correctly-verified
finding *of the 63-creator set at the time* — but it was a snapshot of an unpromoted graph,
not a structural ceiling, and the next round decisively disproved the "sparse" framing rather
than confirming it further.

**What actually happened:** the user reviewed the full sheet backlog (258 accepted, 230
rejected — every row actually looked at). Bulk-promoting those 258 candidates converted
**142 previously-dangling `creator_related_accounts` rows into real resolved pairs, using
zero new scraping** — the rows already existed, their endpoints just weren't `creators` yet.
Resolve rate: **2.4% → 31%** (157 resolved rows / 505 total, independently re-derived by the
orchestrator and matched exactly: 152 distinct pairs, up from 10). Compare: covering 7 new
creators the round before produced 0 new pairs. **Promotion, not coverage, is the lever —
confirmed decisively now, not just theorized.**

⚠️ **Tracks B and C both built on the old 10-pair figure as a settled structural fact** — Track
B specifically planned its first real training run around "expect a small, sparse graph."
That plan needs correcting directly, not just via this doc update — both tracks should be told
this explicitly before doing anything further with the collaboration graph.

**Real bug found in the same round, still unfixed in code (data-only patch applied so far):**
`collab_edges.py`'s co-author-push path hardcodes `category: "other"` for every handle it adds
to the sheet (no bio available at push time to classify on), and `discover_candidates.py`
applies one `--category` hint per whole run rather than per-account. 146 of 258 accepted rows
were sitting at `category=other` because of this — traced with hard evidence (144 of 146 carry
co-author provenance, the only 2 exceptions are pre-existing dead-handle rows). Fixed
*retroactively* for those 146 rows (132 corrected, 13 genuinely `other`, 1 excluded as a
brand) via a new bio-reading `sheets_sync.update_category()`. **The code paths that caused it
are unchanged** — any further co-author-push or discovery run will recreate this exact problem
until the underlying functions do per-account classification at write time, not after.

⇒ Coverage still retains independent value (datapoints, captions, sponsorship events for
Track C) — just isn't the graph-density lever. The remaining lever, now proven not just
theorized: continue surfacing dangling co-author handles (collab_edges.py, now the
highest-confidence discovery mechanism available — it finds people already observed
collaborating with a creator, not merely predicted to) and get them through user review. The
bridge-queue framing (only 13 of 398 dangling handles referenced by 2+ creators) is superseded
by this — promotion converted far more than 13 dangling rows once bulk-authorized. Original
bridge-queue text, kept for the record, follows:

*Superseded text follows, kept for the record:*

~~Do not fund another round of Instagram coverage expecting resolved edges to move.
Coverage retains independent value (datapoints, captions, sponsorship events for Track C),
just not this one. The graph-density lever is the bridge queue: only 13 of 398 dangling
handles are referenced by 2+ distinct creators, and those are the only promotions that link
two covered creators rather than adding a leaf. Detail and the ranked list with brand
exclusions are in Track A's HANDOFF.md §3 (Phase 1F).~~

~~Track B should plan for a sparse collaboration graph. 2.4% of edge rows resolve; this
is a structural property of the curated set, not a collection bug.~~

*Also superseded, from the round before that:*

**~~P0.2 Collaboration edges — mechanism now works, bottleneck is Instagram coverage, not
extraction~~** *(Track A → C → B)* Team→player tagging is confirmed dead (IPL/ISL accounts caption
with hashtags). Its replacement — Instagram's collab co-author list — works and produced 72 edge
rows, but only 2 resolve, because resolving requires BOTH co-authors to already be creators with
Instagram content, and only ~9-12 of 56 creators currently have any `instagram_posts` at all. The
real lever now is Instagram coverage breadth (getting more creators past the grid-stall and
scraped at all), not further edge-mechanism work. 67 co-author candidates are on the sheet
awaiting user review — promoting them will raise resolved count once they have Instagram content
of their own.

**✅ P0.3 Promote-to-DB — DONE 2026-08-11.** `creators` 16 → 55, upsert semantics correct
(`athleanx` gained the instagram_handle it had on the sheet but not the DB — exactly the case
insert-only would have missed), 0 duplicates, `approval_status` untouched.

**✅ P0.4 — SUFFICIENCY THRESHOLD CLEARED 2026-08-18, RE-VERIFIED AFTER CORRECTION 2026-08-19.
Computable GAIL training pairs: ~27-30**, down from an uncorrected ~37-38 — a real, GOOD
correction, not a regression. Two of the 3 misattributed posts found in the tech-debt round
(§ below) were inflating the count doubly: fabricating an event, and widening the wrongful
owner's activity window enough to falsely pass other creators' straddle checks (Kohli's real
dated window is 2026-01-21→2026-06-26; one mis-owned post extended it ~6 months, and he sits as
the neighbor in 16 event-slots). Corrected, then independently re-verified from scratch by the
orchestrator a second time: **30** (fresh live pull, all 33 usable events including a newly
surfaced 2nd Ronaldo event × 170-pair graph × full neighbor content), against Track A's own
final figure of **27**. Both numbers are real and both clear the ≥20 floor — the gap is most
likely timing (new data landing between counts), not an error either side. **Recommendation: one
canonical, shared pair-counting script, not each track/session hand-rolling it separately** — this
is the second round running where independent recomputation gave a different number.

Notable pairs, re-confirmed post-correction: Kerala Blasters↔Mumbai City FC, all 5 previously-
blocked priority creators, Ronaldo↔LeBron now has 2 separate dated events producing pairs.

**⬆️ SUPERSEDED AGAIN 2026-08-21. Computable pairs: 52**, verified by the orchestrator running
Track A's own new canonical script (`pair_count.py`) directly against the live DB, not by
trusting a report. **This crosses the ~50-100 thesis-defensible tier**, not just the ≥20 floor —
a real, substantial jump from the ~27-30 two days prior. Full breakdown from the canonical
script: 137 event×neighbor checks evaluated, 49 dated sponsorship events, 37 events yielding at
least one pair, 23 distinct directed / 20 undirected creator pairs, 170 collaboration edges.

**The jump was driven by one genuinely excellent technical discovery, not just more scraping**:
an Instagram post's shortcode IS its media ID in base64, and the media ID's high bits encode a
millisecond timestamp — the date was sitting inside the primary key the whole time. Fitted (not
guessed) against 881 independently-dated ground-truth posts (via `og:description`, so not
circular): the correct bit-shift lands 99.4% of dates within 72 hours, median error 0.5 days.
Filled NULLs only, self-checks and refuses to write if agreement drops below 95%, flagged
(didn't touch) 5 stored dates it found to conflict — **all 1,811 Instagram posts are now dated**,
up from 881 (49%). This is a zero-network-call fix, so it fully sidesteps the Instagram
adapter/throttle problem for dating purposes specifically. Combined with the recency-window
widening (183→1095 days) and the Reddit name-unblock cascading into real content growth, pairs
went 27→46 (shortcode fix alone)→48→50→**52**.

**Canonical pair-counting is now solved structurally, not just for this round**: `pair_count.py`
is the single definition, `loop_stats.py` imports it rather than keeping a second copy, and it
prints all 4 plausible readings of "how many pairs" explicitly (event-neighbor rows, directed
pairs, undirected pairs, events-yielding-a-pair) — this is what caused every prior recomputation
disagreement, now named instead of re-litigated each round.

**⛔ STANDING RULE 2026-08-21: `DEFAULT_RECENCY_DAYS = 1095` (3 years) is a hard ceiling — do
not widen further.** Track A flagged further widening as data-supported (the 3y+ Reddit band
scored 100% on-topic) and it was queued for approval; the user held it back on reflection and
capped it here explicitly. Reasoning worth keeping: this constant does two conceptually
different jobs at once — (1) how far back to look for historical sponsorship-event context
(where wide is genuinely fine, since a training pair is anchored to its own event's date, not
"today"), and (2) implicitly, how far back any *current-creator-status* feature might draw from
if built carelessly against the same pool (where 3-year-old data would misrepresent who a
creator is now). Job (1) justified the widening to 1095; job (2) is the reason not to go
further without first separating the two uses — **not yet done**, worth a real task before
either Track B's feature-building or Track A's collection touches this distinction again.

**✅ CLOSED 2026-08-22.** The duplicate "Athletics" creator merged cleanly (61 = 40+40-19 posts,
independently confirmed; creators 260→259) and its root cause fixed (`get_or_create_creator` now
has a guarded last-resort name key for handle-less creators, regression-tested against the
Saina/Sindhu collision it was designed to avoid — 3/3 tests pass). Both flagged misattributions
independently confirmed genuine (not false positives, resolved by voice: first-person athlete
content vs. third-person/sponsor-voice brand copy) — both already `creator_id: null`, no further
action needed. Final: **52 pairs holds, 259 creators, standing rule respected (window untouched
at 1095 days).**

**Still genuinely open, both explicitly waiting on the user, not Track A**: (1) Instagram's
*adapter* (distinct from the zero-network date-decode workaround) remains throttled — an 18-hour
cooldown didn't clear it, confirmed Instagram-side. The ownership-contamination census is stuck
at 690/1,752 (39.4%) as a result — durable, not at risk, won't finish on a same-day timescale.
(2) Further recency-window widening beyond 1095 days is data-supported but capped by standing
rule pending the current-status-vs-historical-context split (see the rule above) — not
re-opened without that split being designed first.

⇒ **Track A's work is in a clean, stable stopping state.** Track B has not yet trained against
the current 52-pair set — its last real run was against the much smaller pre-shortcode-fix
graph. This is the natural next move.

✅ **Tech-debt loop closed 2026-08-19 (5 cycles, all 3 items terminal).** Superseding the open
items above:

- **Position-matching: FIXED.** Root cause was worse than "which index" — Instagram's adapter
  hard-caps at its 12-post first-paint grid (confirmed: `--limit` 3/5/12 pass through exactly,
  15/20/25/40 all clamp to 12 — no pagination exists, not fixable adapter-side). Replaced with a
  caption-content join (refuses ambiguous matches) plus per-post `og:description`, verified
  end-to-end on a real creator (6/6 dated, 6/6 comment counts exact, 0 foreign posts written).
- ⚠️ **A worse bug surfaced during verification: Instagram profile grids mix in OTHER accounts'
  posts** (same bug class as the historic caption-authorship incident, new form). Measured:
  14.3% of random posts, 5.8% of sponsorship events. **Independently traced by the orchestrator
  to 2 of the 3 misattributed posts landing inside the P0.4 milestone**: `DLrSRdqTcEQ` (attributed
  to Kohli, actually anushkasharma's) and `DUkDWOYiL8x` (attributed to Kohli, actually
  duroflexworld's — a brand) each produced 2 rows in the recomputed 38-pair set (dates
  2025-07-03 and 2026-02-09). **RE-ATTRIBUTED 2026-08-19** — both re-pointed to their real
  owners (brands get no creator attribution, matching existing schema convention), `DW3hIgJDI3P`
  (reliancejewels) corrected too. **Full ownership audit run on a larger, unbiased sample: true
  contamination rate 14.1%** (184 verified, 26 misattributed — sponsored posts are actually
  *less* likely to be affected than average, 0% vs 3% baseline). Census incomplete — ~1,500 of
  1,752 posts still need checking, blocked on an Instagram throttle the audit itself
  accidentally triggered (caught and fixed: pacing reverted, a 12-strike abort now catches this
  in ~2 minutes instead of hours). Resume once the throttle clears.
  `DW3hIgJDI3P`'s `is_sponsored` is NULL but `has_paid_partnership_label` is TRUE, and the
  events query is `(is_sponsored OR has_paid_partnership_label)` -- so it did count toward the
  pair set before correction (verified against the live row 2026-08-19).
- **`account_classify.py`: CHARACTERIZED, not fixable with more keywords.** 4 held-out sets,
  scored honestly (not against the tuned suite): mean ~45% at first exposure, plateaus after
  tuning — a lexicon classifier ceiling, not a bug. 2 of the classifier's own prior "fixes" were
  found net-harmful and reverted (`_ATHLETE_CLASS`, an "use code" brand-marker that was
  misfiring on real creators' affiliate codes). Real, honest negative result — don't keep
  throwing keywords at it; a different approach would be needed to move past ~50%.
- **Reddit real-name gate: RESOLVED, 200 → 24 unresolvable.** 168 recovered via live Instagram
  re-fetch (now that dates/metadata work correctly) and 8 via verified Wikipedia; 168 + 8 + 24
  = 200. (Corrected 2026-08-19: an earlier draft credited "5 via YouTube description".
  **Zero** names were applied from that source -- 5 was its measured CEILING, i.e. how many
  name-gated creators own a YouTube channel at all. The source is real but capped:
  @jumper_aj_'s title is the useless "jumperAj" while its description names him in prose.)
  Creators with a real name: 43 → 211+. Reddit-attempted: 54 → 230 (20.8% → 88.8%).
  **New binding constraint surfaced, not yet solved**: names were never the only gate — Reddit's
  *recency window* now caps yield the same way Instagram's did. **DECIDED 2026-08-19: widen
  both Reddit's and Instagram's recency windows.** Two independent measurements pointed at the
  same cause: relevance INCREASES with post age (0-90d: 22% on-topic; 2y+: 100% on-topic) — the
  window excludes 133 highly-relevant results while keeping 31 low-relevance ones; separately,
  56 of 137 event×neighbor straddle checks fail *solely* because the neighbor has no pre-event
  activity, exactly what a 183-day window truncates. Widening doesn't reopen the earlier 88%
  Reddit-noise purge (a different, already-fixed cause — handle-shaped queries).
- ⚠️ **The "100% of 259 attempted on all 3 platforms" exhaustion bar (§1a) is confirmed
  unreachable as literally written** — 2 creators have no Instagram handle at all, ~5 have no
  searchable Reddit presence (niche sports, unsearchable single-word names). Revise §1a to
  exclude structurally-unreachable creators from the denominator rather than treat 100% as the
  bar.
- **Flagged for Track C**: brand-co-authored posts on creator grids are largely not labelled as
  sponsorships, though a brand co-authoring with a creator is close to the working definition.
  Worth a look, not yet actioned.

⇒ Track B is unblocked to attempt a real training run with a genuine, if still small, training
set (~27-30 pairs, see the top of this section). Not yet at the ~50-100 thesis-defensible tier —
treat this as a real but early attempt, not a validated model.

*Superseded text follows, kept for the record:*

~~Sponsorship events — signal confirmed, labeling pending~~ *(Track C, now unblocked)*
~~Still 0 in the DB (`is_sponsored` is Track C's to populate) but ≥4 genuine disclosures are now
present in real captions. Track C's re-label is the immediate next step, and those 4 known
disclosures are a concrete validation target — if the labeler misses them, that's a labeler bug,
not an absence of signal.~~

**⚠️ P0.5 — RESCOPED 2026-08-18, more serious than previously recorded.** The user's own instinct
("YT/Reddit deepening feels incomplete") was correct and the orchestrator quantified it directly
against the live DB: of 259 creators, **257 (99.2%) have an Instagram handle, but only 11 (4.2%)
have a YouTube handle on file**, and only **10 creators (3.9%) have any YouTube content at all** —
the same small original set from early phases, untouched since bulk promotion grew the creator
set 63→259. Reddit has content for 13 creators (5.0%, mostly via the topic-sub name-search
mechanism, which doesn't strictly need a discovered handle) but the pattern is the same: the
240+ bulk-promoted creators have essentially never had YouTube or Reddit attempted at all.

This is primarily a **YouTube discovery gap**, not a deepening-capacity problem — almost nobody
has a handle to deepen in the first place. Fix: search for each handle-less creator's actual
YouTube channel (by name/known aliases) and populate `youtube_handle` before attempting any
video fetch. Once found, YouTube deepening is safe to run **in parallel with Instagram** (official
API, no shared browser resource — confirmed safe per §3.6). Reddit's topic-sub search needs to run
for the same 240+ creators, but must run **sequentially after Instagram**, same tab-lease
constraint as always.

**✅ Progress 2026-08-18** — YouTube: 45 auto-matched handles caught and audited before sticking
(3 successive verification-rule failures found and fixed: circular self-match, corroboration-only,
namesake collision); 9 genuine handles applied, 36 `needs_review`, 44 confirmed absent. 89 of 248
searched, quota-capped (100 units/search, 10k/day budget) — expected to span several more rounds.
Instagram: blocked on a sustained 429 (3 consecutive after ~3.5h) — real, not a false alarm from
`opencli doctor` misreading a disconnected daemon as a throttle (checked separately, cause
confirmed distinct). Reddit: root cause found, not just a symptom — bulk promotion set
`creators.name = instagram_handle` for **231 of 264 creators** (topic-sub search queries by
`name`, so a handle-shaped name returns 0 results — proven directly: `"rohitsharma45"` → 0
results, `"Rohit Sharma"` → 10). 13 real names already recovered at zero network cost from
`instagram_profiles.full_name` / `youtube_channels.title`. **Real-name backfill for the remaining
231 is now the actual blocker for all Reddit work**, not a Reddit-side problem — flagged as the
next Track A priority given it's foundational (also likely affects any other name-based matching,
not just Reddit).

**⚠️ Incomplete cleanup, found by the orchestrator, not self-reported.** A separate bug this
round (`--platform reddit --handles <ig_handle>` treating an Instagram handle as a subreddit) was
caught and the `reddit_handles` pollution was cleaned — but the bug's `get_or_create_creator`
path had already created 5 new, fully blank creator rows (name only, no platform handles at all:
`delhipremierleaguet20`, `karanaujla`, `ptushaofficial`, `gujarat_titans`, `ajinkyarahane` — all
created at the identical timestamp 2026-08-17 19:46:58, all bridge-queue-shaped names). These
were never deleted — `creators` is 264 live, not 259. Needs a real DELETE, not just a field
cleanup, next round.

### P1 — blocking scale or quality

**P1.1 Discovery ceiling** *(Track A, Phase 2)*
Tag pages return 3–8 links regardless of requested cap ⇒ hashtags max out ≈213 candidates ever.
Fix: follower-graph expansion as primary (similar-accounts suggestions first, then *following*
lists slowly — elevated ban risk), team-roster extraction, brand-anchored discovery, and finally
*actually test* multi-word keyword search (never tried; one generic single-word test was
over-generalised across 25 cycles).

**P1.2 No content-relevance verification** *(Track A)*
Candidates were judged on bio keywords + follower count only; the post grid was never opened.
Accounts with 2 domain posts and a "certified coach" bio passed as high-confidence. Fix: open the
grid, require a clear majority of recent posts to be domain-relevant, record the actual ratio.

**P1.3 Substring keyword-matching bug class** *(Track A)*
Bare `"mp"` matched "Madhya Pradesh" and silently dropped valid candidates for ~14 cycles. Audit
**all** keyword matching for word-boundary errors — assume more exist.

**P1.4 Businesses/brands misclassified as creators** *(Track A)*
Gym chains, clothing brands, booking services pass the keyword filter. Add explicit account-type
classification: individual / team-or-club (keep) / business-brand (exclude) / media (exclude).

**~~P1.5 Duplicate creator rows~~ — NOT A PROBLEM.** Track A checked: only one creator claims
`"lebron"`, and a sweep across all `reddit_handles` found zero duplicated handles. The earlier
dedup migration already resolved it; this doc's claim was stale. Left here as a record that it
was checked, not assumed.

**✅ P1.6 UNBLOCKED 2026-08-22 — Track B trained on real data for the first time.** Fusion Layer
can now receive a real (if limited) spillover score; wiring it in is the immediate next Track C
task, not blocked anymore. See the Phase 1 round 3 findings directly below for what "real" means
here — genuine but small-N, honestly characterized, not a validated model yet.

**📌 REVIEW 2 BACKLOG — Track B Phase 1 round 3 findings (2026-08-22), deliberately deferred,
don't lose these:**
- **`co_occurs_with` edges: 0 → ~1,400+, independently confirmed by the orchestrator (319 Reddit
  posts now show genuine multi-creator overlap, up from a documented structural zero).** This
  consolidated the graph from 12 small clusters into 2, with a 185-node giant component (was 53).
  **`pair_count.py`'s adjacency may only draw from `creator_related_accounts` and miss this
  entirely** — if so, the current 54/57-pair figure is an undercount. Highest-value Review 2
  follow-up: check and fix this before trusting any future pair count as complete.
- **The 54-pair headline collapses to an effective N of 10 distinct creator-nodes** for the
  current per-node prediction target — 16 of the 34 lift-computable rows are all the same
  underlying Kohli signal (his Reddit engagement genuinely jumped starting 2026-08-05) measured
  from different anchor dates, not 16 independent examples. **Track B's own top-ranked fix**:
  redesign the target to be per-(event, neighbor) rather than per-node — turns those 16 rows into
  16 real signals. Likely bigger leverage than further data collection.
  - LOO-CV (N=10, the honest count): headline MSE 67.19 vs. 67.36 baseline — meaningless, one
    outlier fold (Kohli) is >99% of total error. Excluding it: 14% better than baseline on the
    other 9, real but statistically unprovable at N=9.
  - **Propensity model saturates to 1.000 on held-out nodes in all 10 folds** — the overlap
    identification assumption is not empirically satisfied by this run. Real, honestly
    documented limitation, not glossed over. Track B's second-ranked fix: normalize creator
    features before the propensity head.
  - Two real data-quality bugs found and fixed in the delta computation before they corrupted
    results: NULL→0 coalescing on sparse engagement columns was fabricating fake multi-million-
    percent phantom lifts; partial (non-random) missingness on `like_count` required both
    engagement columns present before treating a delta as computable.
- **Current framing for the thesis**: this is genuine pipeline/methods validation with honest
  small-N caveats, not yet a validated predictive result. Correct and sufficient for Review 1;
  the three items above are what closes the gap toward Review 2.

### P2 — known gaps, not yet blocking

- **⚠️ `reputation_score` / sentiment analysis — reframed 2026-08-16, still unbuilt.** The user
  clarified the actual intent behind Reddit collection: Reddit's role was never meant to be
  primarily co-occurrence (graph edges) — its value is unfiltered public opinion per creator,
  which is what `reputation_score` and the Temporal branch's Sentiment Propagation component
  need. **Reality check, confirmed against the code**: Reddit's only realized use in the ML
  pipeline to date IS the co-occurrence junction — sentiment analysis is 0% built, not partially
  built. This isn't a wrong turn Track A took; the Temporal branch (of the original two-branch
  design) has simply had zero attention while all focus went to the GAIL branch's "do we have
  any signal at all" crisis. Not the low-Reddit-volume's cause, though — that's structural (most
  athletes lack a dedicated subreddit), unrelated to the co-occurrence mechanism.
  **Bigger opportunity, previously unnoticed:** 19,843 YouTube comments and 13,097 Instagram
  comments are sitting completely unused for anything, sentiment or otherwise — a larger raw-opinion
  pool than Reddit's 9,480. **Next step (Track B, Temporal branch, not yet started):** sentiment
  analysis over `reddit_posts`+`reddit_comments`+`instagram_comments`+`youtube_comments` text per
  creator, aggregated into `reputation_score` + a time-series signal for Sentiment Propagation.
  Doesn't block or compete with GAIL/graph work; can start now on whichever creators already have
  decent comment volume, doesn't need more scraping first.
- **Temporal engagement-delta computation not built** *(B)* — the largest unbuilt GAIL piece;
  needs real sponsorship timestamps to compute before/after deltas around.
- **~15-row reconciliation gap** between Track A's own tally (~124) and the live sheet (139).
- **Permanently-dead handles** burning retry time: `athleanx`, `technicalguruji`,
  `delhicapitals`, `punjabkingsipl`. Mark dead, stop retrying.
- **Cross-platform temporal branch** (lag detection, Granger causality, sentiment propagation)
  is specified but largely unbuilt.
- **HLD diagram shows Twitter** instead of Instagram — fix before submission.
- **No auth on most endpoints**; basic `X-API-Key` exists on writes only.

---

## 6. THE PLAN — current state → thesis

**Mapped to the three milestones (re-scoped 2026-09-24):**

| Milestone | Phases that must land | The demo story it tells |
|---|---|---|
| **Review 1** | Phase 1 complete + Phase 2 to **~100 creators** — CLOSED | "End-to-end pipeline works on real data: here are real creators, a real graph, real recommendations." Small-but-real beats large-but-broken. |
| **Review 2** | **PendingWork Phases 1–6 (E1–E10 + S1–S8 + A1–A3) complete** | "Full pipeline with no placeholders: GAIL trains, Temporal + CLIP/BERT are live, fusion is calibrated, evaluation + graph UI work." |
| **Review 3 / Submission** | Improvements + full security pass + thesis/repo/HLD | Repo + paper + security fixes + Docker (deployable, not deployed). |

### 2026-09-24 plan — PendingWork Phases 1–6 ARE the Review-2 plan

Sequencing per the PendingWork doc (team of 3: Eesha = model core, Shimona = branch +
proof, Akshat = infra). Old PHASE 2–4 below are kept for the record but superseded for
Review 2 sequencing.

- **Phase 1 — unblock:** Akshat A1 then A2. Eesha E1, E2, E7, E9. Shimona begins S1.
  (A1 must land before Eesha touches `exposure.py` / `gail_loss.py`.)
- **Phase 2 — complete the claimed components:** Eesha E3, E6, E8, E10. Akshat A3, then
  done. Shimona continues S1, starts S2. Every specified component exists in code.
- **Phase 3 — new novelty:** Eesha E5 evidence check first (drop E5 if zero
  false-negatives, put time into E4 ablation instead), then E5 + E4. Shimona continues
  S1/S2, starts S8.
- **Phase 4 — prove it:** Shimona S4 in full + S7. Eesha supports ablations
  (single- vs multi-relational for E6, plain-MSE vs DR-supervised attention for E4).
- **Phase 5 — remove the placeholders:** Shimona finishes S2, then S3 (recalibrate
  `w1/w2/w3`, backfill fusionscore, remove `is_mock_data:true`, CI over all 3 branches),
  then S6. Eesha supports calibration, then S5 with Shimona.
- **Phase 6 — Temporal to completion:** Shimona finishes S1, propagation exercised,
  `risk_alerts.propagated_from_creator_id` actually populated — the dual framework is dual.

**Review 2 exit criteria:** E/S/A checklist in the 2026-09-24 re-scope above all done;
`npm run build` + `lint` + both `pytest` suites green (A2 gate); fusion has zero
hardcoded `0.5` inputs; S4 rank/score/baseline/ablation numbers exist (suggestive, not
significance-claimed at small N).

⚠️ **Review 1 is close and rewards examples over completeness.** Phase 1's outputs — the
interactive graph, a working recommendation flow on real data — *are* the Review 1 demo. Don't
defer them chasing scale. Equally: **~100 creators clears the Review 1 bar, so don't cut corners
on collection quality to exceed it.** See §1.

### PHASE 1B — Deepening before labeling *(sequencing decision, 2026-08-11)*

**Track C waits.** The orchestrator initially proposed running Track C immediately after the
caption fix; the user pushed back and was right. Recorded because the reasoning generalises:

- The question "does the treatment signal exist" was **already answered** by Track A finding four
  real disclosures manually — so Track C's re-label answers only the narrower "does the labeler
  catch them," which isn't urgent.
- Track C has found **new failure modes at every scale increase** (21 rows → 422 rows surfaced
  four real near-misses). Validating against 60 captions, then re-validating after deepening
  multiplies the data, makes the first pass mostly wasted.
- Deepening will introduce content shapes the current 60 captions don't represent — other media
  types, YouTube descriptions, Reddit bodies. **Edge cases found after Track C signs off are the
  expensive kind.**
- Deepening is the slow, session-bottlenecked, browser-bound step; labeling is a fast DB
  operation. **Slow-first is correct ordering.**
- We still have **no per-creator timings**, and every Phase 2 projection depends on them.

Order: A deepens (with a 5-creator pilot checkpoint for timings) → C labels once against
representative data → B builds the graph → D visualises.

### PHASE 1 — Validation *(now, days not weeks)*
**Question it answers:** does the pipeline produce the treatment signal GAIL needs?
Sequential relay, each step gated on the previous:

1. **A** — fix captions (P0.1) + backfill · build promote step (P0.3) · deepen the 19 approved ·
   write team→player rows (P0.2)
2. **C** — verify backfill landed (don't trust "done") · re-run labeling · report events
   before/after · verify resolvers return *resolved* edge counts
3. **B** — build the first real `HeteroData` · report real structure (degree distribution,
   isolated nodes, components) · GAT forward pass · inductive test on real topology · first real
   training attempt if events exist · **honest call on whether ~19 creators is sufficient**
4. **D** — build the interactive network graph on `/explainability` (honestly sparse if sparse)

**Exit criteria:** we know whether sponsorship events and edges materialise, and roughly how long
deepening one creator takes (needed to project feasibility).

### PHASE 2 — Scale data *(~3–4 weeks)*
- Resume discovery toward **1,000 sheet candidates** with the P1.1 mechanisms and P1.2/P1.3/P1.4
  quality fixes; add `brand_signals`.
- Batch flow: identify (cheap, sheet) → user curates async → **promote per 100 approved on the
  user's explicit signal** → deepen (IG ∥ YT concurrently, Reddit after IG releases the browser).
- Rejections trigger **automatic backfill** so the review pool never runs dry.
- Target **200–400 datapoints/creator** (revised down from 1,000 — breadth over depth).
- **Real success metrics — report every cycle alongside creator count:** sponsorship events
  (target 300+), real edges (target 500+), brands with real data. If creator count climbs while
  those stay flat, the loop is doing the wrong work.

### PHASE 3 — Train GAIL for real *(~2 weeks, B leads)*
- Build temporal engagement-delta computation (P2) — the training target.
- Fit the propensity model on real treated/untreated examples.
- Train GAIL end-to-end; apply causal regularisation; validate on held-out campaigns.
- Cross-platform temporal branch: lag detection + Granger causality on real timestamps.
- Report calibration honestly; **document identification assumptions (unconfoundedness, overlap)
  as acknowledged limitations, not solved problems.**

### PHASE 4 — Fusion + integration *(~1–2 weeks, C leads)*
- Close P1.6: wire real spillover scores into the fusion formula.
- Calibrate `w1/w2/w3` against held-out outcomes instead of placeholders.
- Confidence bounds from bootstrapped/ensemble variance.
- Sentiment propagation → risk flags in monitoring.

### PHASE 5 — Deployable + secure *(~1–2 weeks, D leads with C)*
Note the bar: **deployable, not deployed.** Public hosting is deliberately post-submission.
- Recommendation UI on real scores; explainability graph with real causal insights.
- Monitoring/alerts driven by real sentiment propagation.
- Dockerise the full stack; verify `docker build`/`run` actually works; smoke-test in a browser.
- **Security pass — explicitly required for submission:** auth beyond the write-only
  `X-API-Key`, no credentials in the repo or in chat history, rotate the Supabase password
  (it was pasted into chat 2026-08-11), review RLS/anon-key exposure on Supabase, dependency
  audit. Budget real time for this; it's a submission gate, not polish.

### PHASE 6 — Thesis writeup *(~2 weeks, reserve it — compulsory deliverable)*
- Methodology, results, and a genuinely honest limitations section: observational data,
  disclosure-based treatment labels, dataset scale, India-skewed sample, engagement-per-rupee
  rather than true ROI.
- Repo cleanup — it's a compulsory deliverable in its own right, not just the paper's appendix.
- Fix the HLD diagram (still shows Twitter instead of Instagram).
- Prepare the live demo (extra credit, worth having given Phase 5 makes it nearly free).

---

## 7. Scenario planning

**Best case:** captions backfill cleanly → real disclosures surface → team rosters populate edges
→ GAIL trains on real data → fusion scores become real → the app shows genuine recommendations
plus an interactive causal graph. A complete end-to-end thesis with honest limitations.

**Scenario C — good captions but still 0 sponsorships:** disclosure-tag detection isn't viable
for this population. **Candidate pivot:** redefine the treatment as *brand-tagged posts*
(`brand_id` set) regardless of disclosure text. Still defensible — brand tagging is a real,
observable commercial relationship — but it changes the thesis's treatment definition and must be
stated plainly in the writeup.
⛔ **NOT pre-approved. The user explicitly asked to be brought this decision if it happens**,
with Phase 1's actual numbers in hand. Do not have Track C start building it on a confirmed zero
— surface the finding and wait.

**Scenario D — captions unfixable:** revisit extraction entirely, or treat Instagram text as
unusable and lean on YouTube descriptions (which are API-sourced and not truncated).

**Worst case:** no treatment signal is ever found, GAIL never trains on real labels, and the
thesis becomes "we built a pipeline but couldn't validate the core method." The mistakes that
would have caused it, stated plainly so they aren't repeated: caption truncation went undetected
for ~2 weeks while collection ran on top of it; a 9-hour discovery loop optimised creator count
while the real blocker was elsewhere; `creator_related_accounts` sat empty the whole project with
nobody checking the table edges derive from; curl-only testing hid the CORS bug for 8 weeks.
**The common thread: verifying that code ran, rather than that data arrived.**

---

## 8. Standing rules (earned the hard way)

1. **Verify the consumer, not just the writer.** Most silent-zero failures came from two tracks
   agreeing a feature exists while the string/table/value each assumed differed. Read the
   consuming code before bulk-writing.
2. **"Enabled" ≠ reachable.** Docker, claude-in-chrome, and Apify were all reported available
   before they actually were. Restart, then verify by *using* it.
3. **Never trust a guessed handle.** ~4 of 5 guessed handles resolved to fan/unrelated accounts.
   Verify against the real API; a wrong handle pollutes a real creator's data.
4. **Data changes under claims.** A same-day-true statement can be false hours later (Track A's
   relevance purge invalidated Track C's co-occurrence example within one day). Re-query.
5. **Adversarial self-check every round.** Re-derive, don't re-assert. It has found real bugs
   every single time it's been run.
6. **Commit verified work as you go** — Track D went 3 rounds without committing real, tested code
   because it never asked.
7. **Report deviations in chat, not just in commit messages/docs.**
8. **Row counts ≠ resolved counts.** Report what the consumer actually resolves.

---

## 9. Questions — resolved & open

**Resolved 2026-08-11:**
- ✅ **Deadlines:** Review 1 late Aug–early Sep (≥50% + examples), Review 2 late Oct–early Nov
      (80–100%), submission late Nov–early Dec (complete, secure, deployable). See §1.
- ✅ **Deliverables:** repo + paper compulsory; live demo = extra credit; public deployment
      deliberately post-submission.
- ✅ **Scenario C:** *not* pre-approved — bring the decision back with real numbers.

**Still open:**
- [ ] **Review 1 demo shape** — once Phase 1 lands, decide what specifically gets shown. Likely
      the interactive graph + a live recommendation query on real creators, but worth choosing
      deliberately rather than demoing whatever happens to work.
- [ ] ~~Is ~19 creators enough to demo credibly at Review 1?~~ **Resolved: ~100 is the bar, and
      collection quality outranks demo density.** Track B's Phase 1 sufficiency call still
      matters — but for *model training* viability, not for demo adequacy.
