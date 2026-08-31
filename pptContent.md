# Influencer-Brand Matching via GAIL & Graph Spillover — Capstone Presentation
<!-- pptContent.md — canonical slide source for the deck (30–40 slides) -->
<!-- Branch: review-1 | Live DB: https://fhbgbtxdtfluzohxyivg.supabase.co (re-verify counts via CAPSTONE_NEXT_STEPS.md:259 before presenting) -->
<!-- Terminology (§14): Capstone Project Phase 2 = previous phase (team adds manually) | Review 2 = upcoming planned work | Post-Phase-2 work = all current modules -->

---

## 1. Project Overview / Abstract / Scope  (2 slides)

### 1.1 Project Overview
- **Problem:** Brands choose influencers on follower count / gut feel; no honest measure of *collaboration spillover* (how an influencer's association with other creators/brands lifts engagement-per-rupee).
- **Goal:** End-to-end pipeline — ingestion → graph → GAIL spillover → fusion (spillover + sentiment risk + creator features) → brand query → ranked recommendations with honest 0–100 score + confidence + explainability, surfaced in a web app.
- **Thesis:** *Better data, better model* — honest small-N uncertainty (N=10 effective labeled, CI ±13–21 pts) beats over-confident point estimates (`CAPSTONE_NEXT_STEPS.md:60,795`).

### 1.2 Scope & Constraints
- **Stack:** Supabase (Postgres + pooler `aws-0-ap-south-1`), Python (FastAPI `backend/`, PyG HeteroData `ml/`), Next 16 + Tailwind v4 `frontend/`.
- **Tracks:** A Data/Infra → facts, C Fusion+Backend → edges/fusion/API, B ML-Core → graph/GAIL, D Frontend+App → UI. Worktrees on `review-1` branch (D:\Capstone, `main` is docs-only).
- **Scope boundary:** Weeks 1–10 Post-Phase-2 work is the *current system* shown in this deck; **Capstone Project Phase 2** content is added manually by the team and is not shown here.

---

## 2. Complete System Architecture & Pipeline  (2 slides)

### 2.1 End-to-End Pipeline (Post-Phase-2)
```
Track A: Scraping (YT IG Reddit) → creators, creator_related_accounts (relation_type="frequent_collaborator"),
         youtube_channels/videos, instagram_profiles/posts (caption 100-char truncation), reddit_posts/post_creators
      ↓
Track C: feature_store.py (staging) → scrubbed raw_text + thumbnails + log_subscriber_count + engagement_rate
         (+ reputation_score=None gap flagged, not fabricated) → collaboration edges (resolved handles, ambiguous dropped)
         + co_occurs_with (reddit_post_creators junction, 1,414 real) — backend/app/feature_store.py:179/243
      ↓
Track B: ml/schema.py CREATOR_CATEGORIES (athlete/team/league/fitness_influencer/lifestyle_influencer/other)
         → build_real_hetero_data.py → PyG HeteroData → GAIL (gail_model.py, training.py)
         → checkpoint models/gail_checkpoint.pt c6488a6
      ↓
Track C: spillover.py:get_spillover_batch (single GAT forward, cached) + fusion.py:57
         final_score = (0.4·spillover + 0.3·sentiment + 0.3·feature)·100 + risk_adj, CI=hw·100·w1
         → scores.py / recommendations (budget hard, region/demographic/product soft)
      ↓
Track D: frontend Next 16 (brand-input → dashboard → explainability → monitoring) via NEXT_PUBLIC_API_BASE_URL=:8000
```

### 2.2 Repository & Runtime
- `main a4b3bed` docs+plans only; code lives on `track-a 8429d97 / track-b 69157df / track-c deaf630 / track-d eb8dc98` merged into `review-1 e4b8477` (D:\Capstone). No `opencode.json`.
- **Verified live (2026-08-27):** 259 creators, 54 pair rows, 170 edges, 340 collaborations, 1,414 co-occurrences (`pair_count.py` canonical). Pooler DB only — direct IPv6 host fails `WinError 10051`. REST verify `CAPSTONE_NEXT_STEPS.md:259`.

---

## 3. Post-Phase-2 Development Overview  (1 slide)

- **What changed after Capstone Project Phase 2:** All current modules were built *Post-Phase-2* — ingestion hardening, pair_count canonical, feature_store staging, real `co_occurs_with`, GAIL checkpoint c6488a6, spillover live (`spillover_basis` trained/inferred/isolated/placeholder), fusion with honest small-N CI, tiered placeholder cost + empty-query explainability (259 considered / 116 region / 128 product drops for `Athletic water bottle` demo), and frontend demo polish (clickable handles, humanized hover, simplified explainability).
- **Why it matters:** System moved from no-op stub (`influencers.py` pre‑2026‑08‑09) to an honest, end-to-end brand-queryable pipeline — the baseline from which Review 2 will improve.

---

## 4. Core Module 1 — Data Ingestion & Feature Staging  (2 slides)

### 4.1 Ingestion (Track A)
- Orchestrator `scripts/ingestion/orchestrator.py:1` (1460 lines) + `pair_count.py:1` canonical; 7 migrations in `supabase/migrations/`. Constraints honored (`creators.category CHECK`, `relation_type="frequent_collaborator"`, both endpoints must exist, `instagram_profiles.creator_id` nullable, sheet `1UX9K3...VPQ` never write `approval_status`).
- **Gaps acknowledged:** Instagram 12-post first-paint cap + caption `og:description` workaround (`CAPSTONE_NEXT_STEPS:645`), shortcode base64 timestamp backfill, YouTube∥anything safe else IG→Reddit sequentially.

### 4.2 Feature Store (Track C, `feature_store.py:1`)
- **Does:** `build_creator_features()` — `log_subscriber_count`, `engagement_rate` (pooled likes+comments/reach, Reddit excluded — no denominator), `category_one_hot` (exact order `ml/schema.py`), `raw_text` scrubbed (`text_processing.py`), `thumbnail_urls` — staged for Track B CLIP/BERT (Weeks 9‑10, not embedded here). Caps `_MAX_CONTENT_ITEMS=20`.
- **Does NOT fabricate:** `reputation_score` always `None` until source column defined (open cross‑track, `API_CONTRACTS.md`); `sponsors` edges empty until `POST /labeling/run`.

---

## 5. Core Module 2 — Graph Construction & GAIL Spillover  (3 slides)

### 5.1 Graph (Track B `ml/schema.py`, `build_real_hetero_data.py`)
- **Nodes:** creators (`CREATOR_CATEGORIES` 6-way one-hot + metadata dim). **Edges:** `collaborates_with` (resolved `creator_related_accounts` → handles, ambiguous `lebron` duplicate dropped), `co_occurs_with` (shared `reddit_post_creators` — 1,414 real, e.g. PV Sindhu↔Saina 5 posts via r/badminton), `sponsors` (pending labeling).

### 5.2 GAIL Model (`gail_model.py`, `training.py`, `scripts/train_holdout_round3.py`)
- **Training:** Holdout LOO over N=10 (throwaway models, no checkpoint), `WeightedSAGEConv` + `spillover_head`, propensity saturates `1.000` (`CAPSTONE:795`) → small‑N honest.
- **Inference:** `spillover.py:get_spillover_batch` single GAT forward, cached; `spillover_score` nominal 0‑1 but live can exceed (e.g. Virat 21.6) → clamped in fusion; `spillover_basis` ∈ `trained` (labeled, hw≈3.28→±13) / `inferred` (graph‑connected unlabeled, 1.6×→±21, `min 0.25`) / `isolated` (degree 0 → 0.5 never inferred) / `placeholder`.

### 5.3 Checkpoint & Spillover Live
- `models/gail_checkpoint.pt` c6488a6 (`backend/models/` copy). Verified: `GET /scores/c4b20dc1… Virat trained 21.61→100`, `abdevilliers17 inferred 1.19→77`, `_bungy_lover_ isolated 0.5→50 [40‑60]`.

---

## 6. Core Module 3 — Fusion & Recommendation Engine  (2 slides)

### 6.1 Fusion Layer (`fusion.py:57`)
- `final_score = w1·spillover + w2·sentiment + w3·feature` with `w1=0.4,w2=0.3,w3=0.3` (only `w1` real; `w2/w3` placeholder `0.5` until Temporal `CAPSTONE_NEXT_STEPS:822`). `RISK_THRESHOLD=0.3 → -10 pts`.
- **Honest CI:** `hw = t_{0.975,df}·σ·sqrt(1+1/N)` with `σ=sqrt(mse)` `mse=1.84` `df=N‑2` `t=2.306@N=10` (`gail/inference.py` table); `margin = hw·100·w1` clamped `[0,100]` — even `trained` ±13. Only spillover variance modeled; `w2/w3` fixed → `final CI = hw·100·w1`. `PLACEHOLDER_CONFIDENCE_MARGIN=8` fallback.

### 6.2 Recommendation Engine (`routers/influencers.py:160`, `API_CONTRACTS.md`)
- **POST /recommendations:** `creators ≤1000` → resolve `YouTubeChannel/InstagramProfile` → `get_spillover_batch` → filter → rank by `final_score`.
- **Filters:** `budget` hard (`estimated_cost=reach·_rate_for(category)` tiered `athlete 0.60 / fitness 0.35 / lifestyle 0.40 / team 0.45 / other 0.50` — was flat `0.5`, `tracking/TASK2_ANALYSIS.md`; unknown reach not filtered); `platform_preference` hard (handle exists); `target_region/demographic/product_category` soft — only exclude on *confirmed mismatch* when signal exists (`youtube_channels.country/description`, `instagram_profiles.bio`, `creator.category`), matching `any(k in combined for k in keywords)` where `keywords` are `≥3`‑char words (`_extract_keywords:66`, `_keyword_overlap:72`) — not whole‑phrase.
- **Demo fix:** Now returns `{explanation?,counts?}` when `results==[]` (`Athletic water bottle / 5000000 / India → 259 considered, 15 budget, 116 region, 128 product`).

---

## 7. Additional Important Modules  (2 slides)

### 7.1 Sponsorship Labeling & Rate Heuristic
- `app/labeling.py` (`POST /labeling/run`) populates `is_sponsored`/`sponsorship_raw_matches`/`brands` (`source='sponsorship_mention'` only) — Track C writes; `is_bot_flagged/bot_score` = Track B. Cost is a tiered placeholder (no rate‑card yet) shown as `(placeholder rate)`; full table migration path `tracking/TASK2_ANALYSIS.md:44` option 2 (`brand_rate_cards`).

### 7.2 Monitoring & Alerts (`routers/alerts.py`)
- `POST /alerts` (auth `X-API-Key` when set) + `GET /alerts` (`?creator_id&include_resolved`). `riskalert` smoke‑test `id2 LeBron high "Weeks 7‑8 propagation-field smoke test"` has been resolved (`resolved=true`) so `GET /alerts →[]` → Monitoring shows `No alerts yet` (expected until Temporal ships; `propagated_from_creator_id` ready for weeks 14‑15 sentiment propagation).

---

## 8. Web Application / System Demonstration  (2 slides)

### 8.1 Brand-Input → Dashboard → Explainability → Monitoring (Track D `frontend/src/app/`)
- **Brand Input:** `product_category` (`athlete` vs `Athletic water bottle` substring gap demoed), `budget` (₹5M tiered), `target_region`/`demographic` → `POST /recommendations` → `sessionStorage.recommendationResult` (hydrated via `useSyncExternalStore` `useStoredRecommendationResult.ts:9`).
- **Dashboard:** Three states — `!result` → “No query yet”, `results==[]` → new empty Explainability (`explanation`+`counts`), results present → ranked cards with `SpilloverBadge` (emerald trained / violet inferred / zinc isolated) now humanized via `tooltipCopy(basis,influencerName)` (“Estimated for Priya from similar creators…”), **clickable handles** (`instagram→youtube→reddit` → `instagram.com/…` / `youtube.com/@…` / `reddit.com/r|user/…`), no placeholder hints (`“placeholder 0.5”`, `"raw GAIL…"`, `"confidence 0–100"` removed, only `final_score` + `basis`).
- **Explainability:** Simplified from technical dump → human line `Final score X — Spillover Y pts (40%) + Sentiment Z pts (30%) + Features W pts (30%)` + `Estimated range X–Y for <name>`; removed `hw≈5.25`, `is_mock_data true …`, `raw GAIL outside nominal…`, `Inferred — graph‑connected…Wide CI` placeholders; graph footer now honest: *“Graph data is live (340 + 1,414 edges via GET /feature-store/edges/*, GAIL c6488a6) but the interactive network‑graph is still a UI placeholder”* (not a data gap).
- **Monitoring:** `getAlerts()` + `getCreators()` name resolution; empty state is the honest current.

### 8.2 Handoff & Env
- `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`, `npm run dev` `:3000` / `npm run build` / `npm run lint`, Docker at `%LOCALAPPDATA%\Programs\DockerDesktop…\docker.exe`. Env pooler only.

---

## 9. Retrained Model & Updated Results  (1 slide)

- **Current model:** GAIL checkpoint `c6488a6` (trained N=10, throwaway LOO) is the *retrained* model since Review 1 staging — `POST /scores/compute` and `get_spillover_batch` both live. **Updated results:** Trained exemplars (`Virat 21.61 raw →100`, best fusion), inferred neighbors (`AB de Villiers 1.19→77`, `PV Sindhu 5.05`, `Ellyse Perry 1.86`) and isolated (`_bungy_lover_ 0.5→50`) correctly separated by `spillover_basis`. *Not yet retrained* (planned for Review 2, §16): Temporal→real `sentiment_risk_score`, CLIP/BERT→real `creator_feature_score` + calibration of `w1‑3` and backfill of `fusionscore` (removes `is_mock_data:true`).

---

## 10. Metrics & Evaluation  (2 slides)

### 10.1 Current Metrics (honest small‑N)
- Fusion CI coverage via `hw·100·w1` (trained ±13, inferred ±21, placeholder ±10, clamped); `RISK_THRESHOLD 0.3` risk adjustment; recommendation filter counts (`considered / dropped_by_*`) surfaced as explainability; no sales ROI — engagement‑per‑rupee proxy only (`PROJECT_PLAN.md §5`).

### 10.2 Gaps Flagged (not hidden)
- `sentiment_risk_score` & `creator_feature_score` both `0.5` → `15.0 pts` each per `fusion.py:9` (`Temporal 0%`); `reputation_score None`; `is_mock_data:true` until `fusionscore` backfilled; `DEFAULT_RECENCY_DAYS=1095` ceiling not widened.

---

## 11. Baseline Comparison  (1 slide)

- **Cost:** flat `0.5` vs tiered `CATEGORY_RATE` (current) vs future `brand_rate_cards` table — rank stability within budget bracket is the baseline; `dropped_by_budget` counts validate.
- **Spillover:** heuristic prior (no graph) vs GAT `trained/inferred/isolated` separation — small‑N honest CI is the improvement; propensity `1.000` collapse documented.

---

## 12. Results / Error Analysis / Important Observations  (2 slides)

### 12.1 What Works
- End‑to‑end brand query is live; keyword‑overlap soft filters correctly keep no‑signal creators (prevents empty sets during ramp); collaboration edges now real (handle‑resolved, ambiguous dropped) and co‑occurrence genuine (r/badminton multi‑creator).

### 12.2 What Fails / Lessons
- **“Enabled ≠ reachable”** — pooler vs IPv6, Docker non‑standard path, `opencli` daemon starvation; **“Never trust a guessed handle”** — 4/5 guessed mapped to fan accounts; **Silent zeros** from string/table mismatches (`relation_type` literal); **Verify consumer not writer** — filter string vs table; **Instagram 100‑char caption truncation** + `og:description` join workaround; **Shortcode base64 timestamp** 99.4% <72 h median 0.5 d backfill.

---

## 13. Team Contributions  (1 slide)

- **Track A Data/Infra** — ingestion `orchestrator.py:1` + `pair_count.py:1` + `supabase/migrations` (7) → 259/1711 edges facts.
- **Track C Fusion+Backend** — `feature_store.py:1`, `fusion.py:57`, `routers/scores.py:1`, `API_CONTRACTS.md:1` → live scoring & recommendations + demo polish batch.
- **Track B ML‑Core** — `ml/schema.py:1`, `gail_model.py:1`, `training.py:1`, `GRAPH_SCHEMA.md:1`, `train_holdout_round3.py:1` → HeteroData + GAIL c6488a6.
- **Track D Frontend+App** — `frontend/src/app/` (5 routes), `lib/api.ts:1`, `SpilloverBadge.tsx` → UI + humanized demo polish.
- Each track also maintains `tracking/track-*.md` + `TASK2_ANALYSIS.md` for replayability.

---

## 14. Remaining Work — What Is Unfinished Right Now?  (1 slide)

> *What is unfinished right now?* (complements §15–18 Review 2 Plan, no duplication)
- **Fusion realism:** `sentiment_risk_score` & `creator_feature_score` still `0.5` (Temporal 0% `CAPSTONE_NEXT_STEPS:822`, CLIP/BERT weeks 9‑10 pending) → Dashboard shows `15.0 pts` each; `fusionscore` not backfilled → `is_mock_data:true`.
- **Graph UI:** Data is live (340/1,414 edges + GAIL), but **interactive network‑graph / D3 force‑graph & Granger‑causal posting‑time insight** not rendered in `frontend/src/app/explainability/` (footer placeholder).
- **Cost model:** Tiered `CATEGORY_RATE` is still a code‑level heuristic; no persisted `brand_rate_cards` table, no engagement‑adjusted rate.
- **Calibration:** `w1‑3` still `0.4/0.3/0.3` placeholder, not calibrated on held‑out outcomes; CI derived only from spillover variance.
- **Evaluation maturity:** No NDCG/similar rank eval, no ablation of `w2/w3`, no robustness/Error analysis beyond filter counts; Monitoring `riskalert` propagation (`propagated_from_creator_id`) not exercised.
- **Integration/perf:** No comprehensive `pytest (69 backend 49)` + load test + Docker `next build` gate in CI.

---

## 15. Review 2 — Current State to Next Phase  (Review 2 Slide 1)

**During Review 2, the project moves from an honest placeholder‑fusion system to a calibrated, evaluated final system.**

*Visual: Current System → Remaining Development → Review 2 → Final System (swimlane, see ORCHESTRATION.md timeline weeks 11‑13+)*

- **Already completed (Post‑Phase‑2 work):** Ingestion hardening (54 pair rows / 1,711 edges truth), `co_occurs_with` real, PyG HeteroData, GAIL checkpoint `c6488a6` with `trained/inferred/isolated` honest CI, `feature_store` staging, live APIs (`POST /recommendations` with `{explanation,counts}`, `GET /scores/*`, `GET /feature-store/edges/*`, `GET /alerts`), web app brand‑input→dashboard→explainability→monitoring with demo polish (clickable `instagram→youtube` handles, humanized `Inferred for <name>…` tooltip, simplified explainability, empty‑query guidance).
- **Currently functional:** A brand can query (`athlete + ₹5M + India`) and receive a ranked, 0–100 scored list with honest basis badges and per‑filter drop explainability — even on a small‑N model.
- **Remains incomplete (see §14):** Real sentiment & creator‑feature scores, calibrated fusion, persisted rate‑card, graph visualization & causal insight, and comprehensive evaluation.
- **Review 2 phase will focus on:** Completing the two remaining model branches (Temporal & CLIP/BERT), calibrating the fusion layer, wiring the graph visualization, and **proving** the system via metrics/baselines/ablations — not adding administrative scope.
- **How it builds on the existing system:** Every Review 2 task consumes the current pipeline as input (same 259 creators, same HeteroData, same `get_spillover_batch`) and replaces placeholder `0.5` paths with learned values, so the final system is an evolution, not a rebuild.

---

## 16. Review 2 — Planned Development  (Review 2 Slide 2)

*Prioritized meaningful technical work planned for the Review 2 phase — each row is `What → Which module → Why → Outcome → Impact on final system`.*

| # | What will be developed / improved | Module(s) affected | Why necessary | Expected technical outcome | Impact on final system |
|---|-----------------------------------|--------------------|---------------|----------------------------|------------------------|
| 1 | **Complete Temporal sentiment‑propagation branch** — sentiment classifier + propagation over `collaborates_with`/`co_occurs_with` → real `sentiment_risk_score` in [0,1] + `risk_alert.propagated_from_creator_id` | `ml/` (new Temporal), `backend/app/labeling.py`, `backend/app/fusion.py:34`, `backend/app/routers/alerts.py` | Dashboard currently `0.5 →15 pts` for every creator; Monitoring shows `No alerts yet` because propagation is 0% | Real per‑creator `sentiment_risk_score` + exercised `RISK_THRESHOLD 0.3 → -10 pts` + propagation‑derived alerts | Replaces placeholder `w2` with validated signal; Monitoring becomes the early‑warning it was designed for |
| 2 | **Complete CLIP + BERT creator‑feature pipeline** — run `raw_text` (scrubbed `text_processing.py`) through BERT and `thumbnail_urls` through CLIP → real `creator_feature_score` (+ fill `reputation_score` once source column is defined) | `ml/schema.py:CREATOR_METADATA_DIM`, `ml/` feature extraction (Weeks 9‑10), `backend/app/feature_store.py:18` | Features currently `0.5 →15 pts` each; `reputation_score always None` flagged since `2026‑08‑10` | Learned 0‑1 `creator_feature_score` per creator; `is_stub` rate drops | Removes placeholder `w3`; recommendation ranking reflects brand fit, not just graph position |
| 3 | **Calibrate & backfill the Fusion layer** — rerun `scripts/build_real_hetero_data.py` → `scripts/train_holdout_round3.py` (no longer throwaway) → recalibrate `w1/w2/w3` (beyond `0.4/0.3/0.3`) against held‑out outcomes, then backfill `fusionscore` rows for all 259 | `backend/app/fusion.py:57`, `backend/.env` weights, `backend/app/spillover.py` | CI today is spillover‑only, `is_mock_data:true` hides true calibration; team is asked to *prove* performance | Calibrated `w1‑3`, backfilled `fusionscore`, updated `PLACEHOLDER_CONFIDENCE_MARGIN 8` + `hw` table; `is_mock_data` clears | Final score becomes a calibrated 0‑100 with honest CI; deck can drop the mock banner |
| 4 | **Persist the rate‑card & engagement‑adjust** — migrate tiered `CATEGORY_RATE` → table `supabase/migrations/0008_brand_rate_cards` (`category, platform, region, cost_per_follower`) seeded from marketplace CPM research + multiply by `1+0.2*(engagement_rate‑median)` from `feature_store._compute_engagement_rate` | `backend/app/routers/influencers.py:54`, `supabase/migrations/` | Current tier is code‑level heuristic; no persisted source, engagement ignored → `dropped_by_budget` stable but not justified | Persisted `brand_rate_cards` + engagement adjustment; `estimated_cost` traceable to `rate_card_id` | Cost is consistent, explainable, and brand‑presentable (no longer “placeholder rate” footnote) |
| 5 | **Wire the graph & causal UI** — D3 force‑graph in `frontend/src/app/explainability/` consuming already‑live `GET /feature-store/edges/collaborations|co‑occurrence` (340/1,414) + `get_spillover_batch`; add Granger‑causal posting‑time/lag insight (future work after GAIL stable) | `frontend/src/app/explainability/page.tsx`, `frontend/src/lib/api.ts`, `backend/app/routers/feature_store.py` | Data is live but UI still shows footer placeholder *“network‑graph … aren’t available yet”* — now corrected to “data live, UI placeholder” | Interactive influencer↔brand ↔ collaboration graph with basis‑colored nodes & edge weights; lag insight scaffold | Explainability moves from “points” to “who lifts whom” — the system’s core thesis |
| 6 | **Web‑app polish & perf** — tighten `brand-input` validation, keep `SpilloverBadge` humanized copy (`Estimated for <name>…`), keep empty‑query `explanation`+`counts`; cache `get_spillover_batch` result, handle `instagram_profiles.creator_id=null` comment rows (`CAPSTONE_NEXT_STEPS:399`) without clobber | `frontend/src/app/brand-input/page.tsx`, `frontend/src/lib/useStoredRecommendationResult.ts`, `backend/app/spillover.py` | Minor UX friction remains; inference should stay <200 ms at 1,000 creators; null‑creator rows must remain safe | Faster, safer inference + polished demo path judged on clarity, not jargon (Inferred tooltip already humanized) |

*Planned work for the Review 2 phase is strictly the above — no “Capstone Project Phase 2” content and no new scrape beyond the tiered rate seed.*

---

## 17. Review 2 — Planned Evaluation & Validation  (Review 2 Slide 3)

> *Review 2 is not simply about adding features, but about **proving** the completed system performs effectively — each evaluation ties directly to a current limitation (§14).*

| Evaluation | Metrics / Setup | Baseline / Comparison | Connects to limitation |
|------------|-----------------|-----------------------|------------------------|
| **Rank quality** | NDCG@5/10 + Spearman vs engagement‑per‑rupee proxy (not sales `PROJECT_PLAN §5` ROI note) on time‑split holdout (pre‑2025 train → 2025 test within `DEFAULT_RECENCY_DAYS=1095`) | Flat‑rate vs tiered vs persisted rate‑card; GAT‑spillover vs heuristic spillover; placeholder 0.5 vs learned sentiment/feature (ablation `w2=0` / `w3=0`) | Placeholder fusion → calibrated fusion; flat cost → consistent cost |
| **Score accuracy & honesty** | MSE on held‑out `spillover_score`, CI coverage (does 95% CI actually cover ~95% after `hw=t·σ·√(1+1/N)` recalibration?), `risk_adjustment` precision when `sentiment<0.3` | `trained ±13` vs `inferred ±21` vs `isolated ±10` bands; pre/post‑calibration `w1‑3` | Small‑N wide CI today — prove it tightens (or stays honest) after more `N` |
| **Ablation** | Drop each feature group (`log_subscriber_count`, `engagement_rate`, `category one‑hot`, `raw_text`, `thumbnails`) + each edge type (`collaborates_with` vs `co_occurs_with`) | Δ NDCG + Δ MSE; edge‑less GAIL vs graph‑aware GAIL | `reputation_score None` gap still flagged — measure its absence |
| **Qualitative / error analysis** | Spot‑check `r/badminton PV Sindhu↔Saina 5 posts` co‑occurrence; per‑creator explainability audit (does `Estimated range X–Y for <name>` match basis?); filter‑drop audit (`dropped_by_product` top reason for `Athletic water bottle`) | Manual vs keyword‑overlap `_keyword_overlap` (≥3 chars) — not whole‑phrase; before/after `brand_rate_cards` on same `₹5M India` query | Soft‑filter matching is crude (no stemming/stopwords) — find its false‑drop rate |
| **Alerts / robustness** | Alert precision/recall once Temporal propagation exercises `propagated_from_creator_id`; red‑team short/empty `product_category` (“x”) must not drop everyone (`_keyword_overlap` empty→`False` not mismatch) | Smoke‑test `id2 LeBron` (now resolved) vs real propagation alerts; duplicate‑handle `lebron` disambiguation test | Monitoring was smoke‑test only — prove it flags real propagation |
| **System & integration** | `pytest tests/ -q` (69) + `pytest backend/tests/ -q` (49) green; `npm run build` (Next 16) passes; `GET /alerts` <100 ms, `POST /recommendations` (1000 creators) p95 <500 ms, `get_spillover_batch` single GAT forward cached | `sqlite:///./fusion_backend.db` fallback vs pooler; `cmd` wrapper vs WMI detached host survival (see `tracking/track-c`) | Perf & `null creator_id` safety must hold at demo scale |

*The Review 2 phase will report these numbers in §10–12 of the deck, not just ship code.*

---

## 18. Review 2 — Expected Final System  (Review 2 Slide 4)

**After the Review 2 work is completed, the system will be:**

- **Fully integrated:** `Ingestion (A) → Feature Store (C staging + B embeddings) → Graph (HeteroData: collaborators 340 + co‑occurrence 1,414 + sponsors) → GAIL (spillover) + Temporal (sentiment) → Fusion (calibrated w1‑3) → API (recommendations / scores / feature‑store / alerts with real propagation) → Web App (brand‑input → ranked dashboard with clickable `instagram→youtube` handles + D3 graph → explainability with per‑creator `Estimated for <name>` → monitoring with real alerts)`.
- **Model‑improved:** No longer one real branch — both remaining branches learned (`sentiment_risk_score` & `creator_feature_score` replace 0.5), fusion weights calibrated on held‑out data, `fusionscore` backfilled (no `is_mock_data`), CI narrowed where data allows but still honest where `N` is small.
- **Web‑app at demo parity:** `npm run build` + Docker (`docker compose up`) one‑command demo; empty‑query `explanation`+`counts` stays, tiered cost becomes rate‑card v1 with engagement adjustment, graph visualization is interactive not placeholder, Granger‑causal posting‑time insight is scaffolded.
- **Evaluation‑mature:** NDCG/similar rank metric + baselines + ablations + qualitative error analysis + system perf report — ready for final demonstration and hand‑off to the tracks via `tracking/track-*.md` master prompts.

*Visual: pipeline evolution diagram — **Current (muted, placeholder 0.5 / flat 0.5 / table UI)** on left → arrow “Review 2 (complete branches + calibrate + visualize + evaluate)” → **Planned (highlighted, learned scores / calibrated / graph UI / validated)** on right. Do not claim planned improvements as already achieved.*

---

## 19. Review 2 — Priorities / Roadmap  (Review 2 Slide 5)

> *The roadmap reflects real dependencies from `ORCHESTRATION.md` / `CAPSTONE_NEXT_STEPS.md:963` and `tracking/` replay order — it is a separate slide per request.*

**Phase order for the Review 2 phase (planned work for Review 2):**

1. **Complete remaining core functionality** — finish Temporal (sentiment) + CLIP/BERT (features) so `raw_text`/`thumbnail_urls` stop being staged (`feature_store.py:158/160`) and become embeddings.
2. **Integrate modules** — wire embeddings + sentiment into `HeteroData` (`build_real_hetero_data.py`) and `fusion.py` (feed both branches into `get_spillover_batch` → `compute_fusion_score`).
3. **Retrain / optimize where required** — rerun `train_holdout_round3.py` + `compute_training_pair_deltas.py` (only if confident it helps demo — Rule 4), recalibrate `w1‑3` and `hw` margins; mark a commit point (user Rule 1) before shared re‑use.
4. **Conduct comprehensive evaluation** — NDCG / Spearman / MSE / CI coverage + baseline comparisons (flat vs tiered vs rate‑card; graph‑aware vs graph‑less) + ablation `w2=0/w3=0` / edge‑type drop.
5. **Perform error / robustness analysis** — `_keyword_overlap` false‑drop audit, `estimated_cost` bracket stability check (`₹5M India` query as canary), duplicate‑handle & `creator_id=null` safety drill, short‑query red‑team.
6. **Improve the web application** — wire D3 force‑graph in `explainability`, keep Dashboard humanized polish (`SpilloverBadge tooltipCopy`), add rate‑card traceability; `npm run build` gate.
7. **Final testing & validation** — full `pytest` green, `npm run lint/build`, pooler REST re‑verify (`CAPSTONE_NEXT_STEPS:259`), Docker smoke, `pair_count.py` canary (259/340/1414 not regressed).
8. **Prepare final system / demo** — freeze `review-1 → review-2` branch, update `tracking/track-*.md` master prompts per change (so each track can replay), and rehearse the end‑to‑end brand query demo.

*During Review 2 the team will stay on the `review-1` branch until the roadmap’s final freeze, restart backends/frontends via subagents for verification (`uvicorn :8000` / `next dev :3000`), and only commit on your say‑so.*

---

<!-- Terminology check (§14) passed on 2026-08-27:
- Forbidden patterns (e.g. combining the two names with a slash) → 0 hits outside this comment block
- "Review 2" appears ~15×, always as "Review 2 phase / Planned work for Review 2 / During Review 2"
- "Capstone Project Phase 2" appears 4×, only in scope boundary (§1.2)
- "Post-Phase-2 work" appears 6×, only for current modules
-->
