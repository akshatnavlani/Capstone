# Capstone Project: Refined Premise & Flow

## Context

This document refines the original "Capstone Documents.md" (influencer-brand matching with a causal spillover model). The goal was to stress-test the premise — flaws, ambiguities, infeasibilities — without writing code yet. This is a **graduate-level thesis with a delayed start**, run by a **4-person team over ~6 months**, so the plan below is full-scope (not descoped) but leans on established, off-the-shelf techniques wherever possible to protect accuracy and timeline under pressure, per direction from this session.

Confirmed decisions (including after reviewing the HLD diagram):
- Team: 4 people, tracks = Data/Infra, ML-Core, Fusion+Backend, Frontend+App.
- Timeline: ~6 months (26 weeks) from now.
- GAIL = **Graph-Adaptive Interference Learning** (fixing the doc's inconsistent "Inference"/"Interference" wording — Interference is correct, since spillover *is* interference in the causal-inference sense).
- GAIL will be built on established techniques (GAT/GraphSAGE + standard causal-adjustment methods) rather than novel theory invented from scratch — faster, more defensible for a thesis under time pressure, still a legitimate contribution (rigorous application of established causal-ML methods to a novel domain).
- Data target: **minimum 1,000 datapoints/entity**, maximize count of influencers covered within the team's Month 1-2 collection window.
- **Platforms: YouTube + Instagram + Reddit only.** Twitter and Facebook are out of scope. Note: the HLD diagram's Layer 1 currently shows Twitter instead of Instagram — that's now a known mismatch between the diagram and the actual plan; **update the HLD image before submission/defense** so it doesn't contradict the rest of the thesis. Reddit's current API limitations (no anonymous endpoint, login-gated scraping) are accepted.
- Data collection uses `agent-reach`, parallelized via multiple sub-agents per platform, plus a Hermes automation agent for orchestration.
- **"Historical Data - Partnerships/Collaborations"** (the HLD's 4th Layer-1 source) is derived from scraped data itself — not manually compiled. Concretely, this means the disclosure-tag detection in Edge Preprocessing (`#ad`, `#sponsored`, etc. → `is_sponsored`) is the **sole source of treatment labels** for the entire causal model, not just a minor preprocessing step. This makes that specific detection step precision-critical — worth extra validation time, since undisclosed/untagged sponsorships will simply be invisible to GAIL as training signal.
- Bot detection: heuristic-based (not a trained ML classifier) — confirmed as sufficient.
- **Core model is a two-branch "Dual Framework"** (matches the HLD literally, reversing the earlier "fold into one model" note): a GAIL branch and a Cross-Platform Temporal branch run separately, then combine in a shared Causal Inference layer. See Section 3.
- **Sentiment Propagation** = network diffusion of sentiment/risk — when one influencer's sentiment shifts (e.g. a controversy), model how that risk propagates to closely-connected collaborators over time. Feeds directly into the Application Layer's Monitoring/Alerts feature.
- Fusion Layer: concrete weighted combination (spillover score + sentiment/risk score + creator feature score → final 0-100 score with confidence bounds), plus risk adjustment from the sentiment propagation branch — confirmed as the approach.

---

## 1. Data Collection

- **Sources:** YouTube Data API (primary — official, reliable, free quota) + Instagram/Reddit via `agent-reach` (OpenCLI-backed, session-based). Twitter and Facebook are explicitly out of scope.
- **Parallelization:** One sub-agent per platform (YouTube, Instagram, Reddit), coordinated by a Hermes orchestration agent that queues influencer targets and merges results into the DB. Note for build time: each platform's actual rate limit is tied to the logged-in account/session used by `agent-reach`, not to how many sub-agents call it — so real throughput scaling requires either multiple accounts/sessions per platform or accepting the single-session ceiling. Decide this in Week 1-2 (see timeline) since it changes how many influencers are realistically reachable.
- **Target:** minimum 1,000 datapoints/entity (posts, comments, metrics, thumbnails, timestamps); influencer count maximized based on actual Month 1-2 scraping velocity — treat the count as a rolling target, checked at the Week 4 and Week 8 checkpoints, not a fixed number decided today.
- **Coverage:** athletes, teams, leagues, fitness and lifestyle influencers, 5k+ followers, last 6 months of data (Jan-Jun 2026) as originally scoped.
- **Schema:** seed table (unique_id, name, cross-platform handles, prior endorsements) + per-platform tables (Instagram, YouTube, Reddit) keyed to the seed table — original design was sound, keep it.
- **Region/demographic targeting:** since third-party audience analytics aren't accessible via free APIs, approximate via proxy signals — bio text, comment language, hashtags, posting times/timezones.
- **"Historical Data - Partnerships/Collaborations"** is not a separately-sourced dataset — it's derived from the `is_sponsored` disclosure-tag labeling done in Edge Preprocessing (Section 2). This is the only source of treatment-event labels for GAIL, so the disclosure-detection logic (recognizing `#ad`, `#sponsored`, "in partnership with," etc., including variants/misspellings) needs real validation, not just a basic regex — it's load-bearing for the entire causal model, not a minor cleanup step.

## 2. Edge Pre-processing

As originally scoped: temporal normalization (UTC), text scrubbing (URLs/HTML/mentions), sponsorship labeling (`is_sponsored` binary), log-scaling of skewed metrics, CLIP+BERT feature extraction (thumbnails + text), cross-platform identity linking/de-duplication.

**Bot/fake-account detection:** heuristic-based, not a trained classifier (no labeled ground truth available to train/validate one reliably). Use: follower/following ratio outliers, account age, posting-frequency anomalies, engagement-rate vs. follower-count mismatches. Document this as a deliberate, defensible simplification in the thesis writeup.

## 3. Core Model: Dual Framework (GAIL branch + Cross-Platform Temporal branch → Causal Inference)

Matches the HLD literally: two parallel branches, each built on established, off-the-shelf components, combined by a shared Causal Inference layer.

### 3a. GAIL branch (Graph-Adaptive Interference Learning)

- **Graph structure:** heterogeneous graph — creator nodes and brand nodes; edges = collaboration frequency (weighted), platform co-occurrence.
- **Node features:** CLIP embeddings (thumbnail style/composition/production quality) + BERT embeddings (topics/tone/writing style) + metadata (subscriber count, category, engagement rate, reputation score).
- **Backbone architecture:** Graph Attention Network (GAT) or GraphSAGE, via PyTorch Geometric (PyG) — both established, well-documented, off-the-shelf. GAT's per-edge attention coefficients directly implement the "personalized spillover weight per collaborator" idea from the original doc (Step 6: Learn Attention Weights) without inventing new attention math.
- **Inductive setting:** GraphSAGE-style inductive aggregation so new influencer nodes can get embeddings without a full retrain — reduces retraining need but doesn't eliminate it; periodic fine-tuning as the graph evolves should still be planned for.
- **Training target:** predict engagement-gain (spillover) for a sponsored node's neighbors, supervised on historical sponsorship events (i.e., the disclosure-tag-derived "Historical Data" from Section 1/2).

### 3b. Cross-Platform Temporal branch

- **Profile Matching and Unified IDs:** reuses the Cross-Platform Linking module from Edge Preprocessing (Section 2) — same creator resolved across YouTube/Instagram/Reddit.
- **Temporal Modeling:** models posting-time patterns per creator per platform.
- **Lag Detection (12-24 hours):** tests whether posting the same/related content on one platform predicts engagement or sentiment shifts on another platform within a 12-24h window.
- **Sentiment Propagation:** network diffusion model — when one creator's sentiment/risk shifts (e.g. a controversy), estimate how that risk propagates to closely-connected collaborators over time. Output feeds directly into the Application Layer's Monitoring & Alerts feature (Section 5).

### 3c. Causal Inference (combiner)

Takes outputs from both branches:
- **Regularization** (applied to the GAIL branch, off-the-shelf techniques, not derived from scratch): *overlap/doubly-robust correction* for selection bias (brands favoring already-popular creators) via a standard propensity-score model (logistic regression or small MLP); *smoothness regularization* via standard graph Laplacian regularization; *consistency constraint* enforcing zero exposure for nodes with no sponsored neighbors.
- **Granger Causality** (applied to the Temporal branch): a well-established statistical test for whether one time series (e.g. platform-A posting/sentiment) helps predict another (platform-B engagement/sentiment) within the detected lag window — directly answers the doc's original question about whether cross-platform posting timing affects outcomes, using an off-the-shelf method rather than inventing new causal-timing theory.
- Output: **Combined Results**, passed to the Fusion Layer.

**Validation (both branches):** empirical — train/test split on historical campaigns, held-out accuracy/calibration reporting. Explicitly document identification assumptions (unconfoundedness, overlap) as acknowledged limitations in the thesis rather than claiming proof — standard, honest practice for applied causal ML work, and doesn't weaken the contribution.

## 4. Fusion Layer

Matches the HLD (Multi-Modal Fusion + Risk Adjustment → ROI Aggregator). Concrete instantiation (Option A) of "Combined Results" from Section 3c:

`final_score = w1 * spillover_score (GAIL branch) + w2 * sentiment/risk_score (Temporal branch, incl. sentiment propagation) + w3 * creator_feature_score`

with risk adjustment applied from the sentiment propagation output, producing a 0-100 score with confidence bounds (e.g., from bootstrapped or ensemble variance across the GNN's predictions). Weights (`w1..w3`) start as tunable hyperparameters, calibrated against held-out historical outcomes.

## 5. Application Layer

- Recommendation engine: influencer ranking + ROI breakdown (note: "ROI" here means engagement-per-rupee, since the data pipeline captures engagement metrics, not sales/conversion data — worth stating explicitly in the thesis to avoid overclaiming).
- Monitoring/alerts: risk flags and sentiment alerts, driven directly by the Temporal branch's sentiment propagation output (Section 3b) — a controversy detected for one creator surfaces as a risk flag for their closely-connected collaborators too, not just for themselves.
- Explainability: network visualization + causal insights (e.g., posting-time/lag effects from the Granger causality step) — build after the recommendation engine and fusion layer are stable; treat as the layer most likely to flex if the timeline tightens further.
- Output: a **Final Recommendation Report** per the HLD — decide whether this is purely an in-app view or also an exportable document (PDF/doc); not yet decided, low priority.
- Deployment: Dockerized, hosted — as originally planned.

---

## 6. Weekly Timeline (26 weeks / 6 months, 4 tracks)

Tracks: **A** = Data/Infra · **B** = ML-Core · **C** = Fusion+Backend · **D** = Frontend+App

| Weeks | A: Data/Infra | B: ML-Core | C: Fusion+Backend | D: Frontend+App | Cumulative % |
|---|---|---|---|---|---|
| 1-2 | Finalize DB schema; provision cloud DB; set up agent-reach sub-agents + Hermes orchestration; resolve account/session throughput plan | Set up PyG environment; design heterogeneous graph schema (creator/brand nodes, edge types) | Define API contracts; scaffold backend project (FastAPI + ORM) | Tech stack decision; wireframe brand-input flow + results dashboard | 5% |
| 3-4 | Begin bulk scraping: YouTube first, then Instagram/Reddit/Facebook in parallel via sub-agents | Prototype graph construction on sample data; validate GAT forward pass on toy graph | Build ingestion API endpoints (raw data → DB) | Build static UI shell; set up Docker deployment skeleton | 12% |
| 5-6 | Continue scraping; collect historical sponsorship/collab event data (needed for GAIL training pairs) | Implement causal regularization terms (propensity model, Laplacian smoothness, consistency constraint) | Build DB → feature-store pipeline | Begin brand-input form against mock data | 20% |
| 7-8 | Finish primary scraping pass; QA data completeness against 1k/entity floor, flag gaps | Begin bot-detection heuristics module | Text scrubbing + temporal normalization + sponsorship labeling pipeline | Continue UI build against mock API | 35% |
| 9-10 | Gap-filling scraping as needed; freeze v1 dataset; validate disclosure-tag (`is_sponsored`) detection quality, since it's the sole treatment-label source | Run CLIP + BERT feature extraction across dataset | Cross-platform identity linking / de-dup | Connect UI to preliminary real API responses | 45% |
| 11-13 | Pivot to Temporal branch: extend cross-platform linking into Temporal Modeling + Lag Detection (12-24h window) | Build GAIL branch: full graph, GAT/GraphSAGE backbone, first training run on historical sponsorship events | Scaffold fusion layer interfaces (Combined Results → spillover/sentiment/feature score inputs) | Build results/ranking display components | 55% |
| 14-15 | Implement Sentiment Propagation (network diffusion model) in the Temporal branch | Implement Causal Inference combiner: Regularization on GAIL branch, Granger Causality on Temporal branch; validate on held-out campaigns | Implement Fusion Layer (weighted combination + risk adjustment + confidence bounds) | Wire recommendation engine UI to fusion output | 65% |
| 16-17 | Support B on Causal Inference validation, or assist C/D as needed | Model refinement from integration/error analysis across both branches | Build sentiment/risk alert module driven by Sentiment Propagation output | Build monitoring/alerts UI + basic score-breakdown explainability | 72% |
| 18-19 | Final data refresh if needed | Model performance/calibration validation report | API hardening, error handling | Polish results dashboard; add network-graph explainability if on schedule | 82% |
| 20-21 | — | — | Bug fixing from full integration testing | UX polish; deferred features if ahead of schedule | 90% |
| 22-23 | — | — | Dockerize full stack; deploy; smoke-test | Begin thesis writeup (methodology, results, limitations) | 95% |
| 24-26 | — | — | — | Final polish, thesis writeup completion, demo prep, buffer | 100% |

Checkpoints (Week 4, 8, 13, 17, 21) are natural go/no-go points to re-baseline the influencer-count target and re-balance track workload if any track is ahead or behind.

## 7. Remaining open items

- **Update the HLD diagram asset itself**: it currently shows Twitter in Layer 1 instead of Instagram — fix before using it in the thesis/defense so it doesn't contradict the actual plan.
- **Final Recommendation Report**: decide whether this is purely an in-app view or also an exportable document — low priority, can be decided later.
