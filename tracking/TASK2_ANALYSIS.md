# Task 2 — Analysis: Mock Data & Placeholder Rates (review-1 branch)

## 1. Why sentiment/risk and feature score show mock / placeholder data

**Observed UI:** Dashboard `ScorePart` shows:
- `Sentiment / Risk 15.0 pts — placeholder 0.5 (Temporal 0%)` (`frontend/src/app/dashboard/page.tsx:121` + `frontend/src/app/explainability/page.tsx:92`)
- `Creator Features 15.0 pts — placeholder 0.5` (`dashboard/page.tsx:127` + `explainability/page.tsx:97`)
- Explainability per-creator footer: `Confidence bounds 0–100 (basis: inferred, hw≈5.25 → ±21pts wide; sentiment is still placeholder per CAPSTONE_NEXT_STEPS:822). is_mock_data true — at least one creator lacked a stored FusionScore…` (`explainability/page.tsx:100`)

**Root cause — three layers, all intentional placeholders per project timeline:**

1. **Fusion weights `backend/app/fusion.py:7`:** `final_score = w1*spillover + w2*sentiment_risk + w3*creator_feature` with `w1=0.4 w2=0.3 w3=0.3`. Only `w1` (spillover via GAIL checkpoint `c6488a6`, `backend/app/spillover.py:get_spillover_batch`) is real. `w2`/`w3` are **fixed 0.5** because their branches are 0% built — see `CAPSTONE_NEXT_STEPS.md:822` ("Temporal 0% built") and `fusion.py:9` comment. That is why every creator's contribution is `0.3*0.5*100 = 15.0 pts` regardless of creator.

2. **Feature store gaps `backend/app/feature_store.py:18`:** Track B's `ml/schema.py:1` expects `reputation_score` in `CREATOR_METADATA_DIM` (`log_subscriber_count + engagement_rate + reputation_score + category one-hot`), but no Track A table has a `reputation_score` source column (`feature_store.py:18` "Always None here"). `raw_text`/`thumbnail_urls` are staged (scrubbed via `app/text_processing.py:scrub_text`) for Track B's Weeks 9-10 CLIP+BERT step (`feature_store.py:5` "does NOT compute CLIP/BERT embeddings itself"), but those embeddings are not yet materialized — so `creator_feature_score` has no real model output and Track C falls back to 0.5 in `routers/influencers.py:117` (`score.sentiment_risk_score if score else 0.5`).

3. **`is_mock_data` flag `routers/influencers.py:271`:** `is_mock_data = using_mock_creators or any_score_missing`. `using_mock_creators` is False on live DB (259 creators), but `any_score_missing` is True because `FusionScore` rows are missing for many creators (the fusion table was never backfilled after the GAIL checkpoint landed). Result: the response is marked mock and the banner `frontend/src/app/dashboard/page.tsx:58` shows. The `confidence bounds … is_mock_data true` line in `explainability/page.tsx:109` is per-request (not per-creator — see Q2 below) but rendered inside each card, so it looks hardcoded.

**Why not just fabricate values:** The team deliberately left these as `0.5` with `is_mock_data:true` rather than inventing sentiment/feature scores, so the demo honestly shows the gap (`CAPSTONE_NEXT_STEPS.md:60` thesis: "better data, better model" — small-N wide CI already surfaced).

**Path to rectifying it (no new scraping needed, retrain is the lever):**

- **Short-term (demo-safe, no retrain):** Keep 0.5 but hide the placeholder sublabels in the UI (Task 3-2) and surface a single honest banner ("Sentiment & feature scores are staged — real model lands Weeks 9-10") instead of per-card mock noise. This is what Task 3 does.
- **Medium-term (requires Track B retrain + Track C backfill):**
  1. Track B builds Temporal branch (sentiment propagation, weeks 14-15 per `monitoring/page.tsx:43` comment) → produces `sentiment_risk_score` in [0,1] per creator (threshold `RISK_THRESHOLD=0.3` in `fusion.py:34` then maps to `RISK_PENALTY_POINTS=10`).
  2. Track B runs CLIP (thumbnails) + BERT (`raw_text` from `feature_store.py:158`) per `GRAPH_SCHEMA.md` Weeks 9-10 → populates `creator_feature_score` and `reputation_score` (needs a defined source column, e.g. follower-growth or brand-safety signal).
  3. Track C runs `scripts/train_holdout_round3.py` / `compute_training_pair_deltas.py` with the new inputs, recalibrates `w1/w2/w3` (currently placeholder 0.4/0.3/0.3, see `backend/.env` / `app/config.py`), and backfills `FusionScore` rows for all 259 creators so `any_score_missing` → False.
  4. After that, remove the `0.5` fallbacks in `routers/influencers.py:117-119` and the `is_mock_data` banner will naturally disappear.
- **Prerequisite check before retrain (rule 4):** Verify `feature_store.build_creator_features()` returns non-stub `raw_text`/`thumbnail_urls` for ≥ ~100 creators (today many `is_stub:true` due to Instagram caption truncation at 100 chars, `CAPSTONE_NEXT_STEPS.md:645`, and Reddit starvation — `AGENTS.md`). If still stub-heavy, retraining now would just learn on 0.5 again and waste a CUDA cycle — flag to user.

## 2. Placeholder rates — how defined, how to make consistent

**Current definition `backend/app/routers/influencers.py:54` & `backend/app/fusion.py:53` doc:**
```python
COST_PER_FOLLOWER_INR = 0.5  # placeholder cost heuristic
estimated_cost = reach * COST_PER_FOLLOWER_INR  # reach = max(subscriber_count, follower_count)
```
- `reach` comes from `YouTubeChannel.subscriber_count` or `InstagramProfile.follower_count` (whichever larger, `_to_recommendation:140`).
- Hard budget filter: `if estimated_cost is not None and estimated_cost > request.budget: dropped_by_budget++` (`routers/influencers.py:210`). Unknown reach (`reach==0/None`) ⇒ `estimated_cost=None` ⇒ **not filtered** (can't judge ⇒ keep).
- Comment at `routers/influencers.py:50` explicitly says "no real rate-card/pricing data exists yet … revisit once real campaign cost data is available (PROJECT_PLAN.md Section 5's ROI note: engagement-per-rupee, not sales)".
- Side effect seen in Task 1 fix: small reach 5k → ₹2.5k passes ₹5M filter easily, while 272M Virat → ₹136M filtered heavily — ordering is correct but magnitude is arbitrary because the scalar is uniform.

**Why inconsistent today:**
- Flat 0.5 ignores category (`athlete` vs `fitness_influencer` rate cards differ 3-5× in practice), platform (`youtube` CPM vs `instagram` vs `reddit` karma), region buying power, and engagement rate (5k highly-engaged micro > 100k dormant macro).
- No DB table backs it, so frontend shows it verbatim (`dashboard/page.tsx:84` "est. cost ₹… (placeholder rate)") which looks like a real quote.

**Path to consistency (no scraping, just modeling + config):**

1. **Tiered placeholder (immediate, no schema):** Replace single scalar with a small lookup keyed by `(category, platform)` — e.g. `{"athlete":0.6, "fitness_influencer":0.35, "team":0.45, "lifestyle_influencer":0.4, "other":0.5}` × `{"youtube":1.0, "instagram":0.9, "reddit":0.2}` and cap `estimated_cost` at `reach*base*platform_multiplier`. Keep calculation in `routers/influencers.py` and expose the tier in the breakdown so explainability can say "rate-card: athlete × instagram = 0.54". This makes same-budget queries rank-order stable even before a full DB table.

2. **Rate-card table (proper fix, small migration):** Create `supabase/migrations/0008_brand_rate_card.sql`:
   ```sql
   create table brand_rate_cards (
     category text check (category in ('athlete','team','league','fitness_influencer','lifestyle_influencer','other')),
     platform text check (platform in ('youtube','instagram','reddit')),
     region text, -- nullable, e.g. 'IN', 'US'
     cost_per_follower numeric not null, -- e.g. 0.35
     effective_from date default now(),
     primary key (category, platform, coalesce(region,'*'))
   );
   ```
   Seed from a one-off research sheet (not scrape) of public influencer marketplace CPMs, store in DB, and change `_to_recommendation` to `lookup_rate(creator.category, dominant_platform, target_region) * reach`. `POST /recommendations` then also returns the applied `rate_card_id` so the frontend banner changes from "(placeholder rate)" to "(rate-card v1, 2026-08-27)".
3. **Engagement adjustment (once `feature_store._compute_engagement_rate` has data):** Multiply by `1 + 0.2*(engagement_rate - median)` so 8% ER inflates cost vs 1.5% ER deflates — consistent with "ROI = engagement-per-rupee" thesis.
4. **Validation:** For a reference budget ₹5,000,000, the response `counts.dropped_by_budget` should be stable bracket (\~10-20 dropped) across product categories after the tier change — verify via the same `curl -X POST … /recommendations` used in Track C's change-log verification.

**Demo recommendation now (Rule 4 — retrain confidence):** Retraining the GAIL/Temporal model **will not fix cost consistency** — cost is not a learned parameter, it's a lookup. Do not retrain for this; apply the tiered placeholder (option 1, < 15 lines in `routers/influencers.py`) and/or the rate-card table (option 2, one migration). Flag retrain only if sentiment/feature real values become available per the Task 2-1 path above.
