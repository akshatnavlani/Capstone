# Track B — ML-Core — Change Log (review-1 branch)

Owner: Track B (Graph construction PyG HeteroData, GAIL, bot detection, CLIP/BERT)
Branch: `review-1`
Standing rule: No new scraping. Model retrain only if confident it helps demo goal (user rule 4).

## Change Log

### 2026-08-27 — Initial tracking files created
- Created per-track tracking directory. No ML code changes yet.

### 2026-08-27 — Hosting confirmed
- Backend uses GAIL checkpoint `models/gail_checkpoint.pt` (also `backend/models/` copy) via `backend/app/spillover.py` -> `get_spillover_batch`.

---

## Master Prompt — Track B (update after each change)

> You are Track B (ML-Core) on branch `review-1`. Your ownership is `ml/schema.py:1`, `ml/gail_model.py:1`, `ml/training.py:1`, `GRAPH_SCHEMA.md:1`, `scripts/train_holdout_round3.py:1`, `scripts/build_real_hetero_data.py`.
>
> **Current state (review-1, 2026-08-27):**
> - GAIL checkpoint `c6488a6` is wired: `backend/app/spillover.py` calls `get_spillover_batch` (single GAT forward, cached) to produce `spillover_score` 0-1 nominal but live can be outside (e.g. Virat 21.6 — clamped later in fusion). `spillover_basis` ∈ {trained,inferred,isolated,placeholder}, CI hw: trained ±13pts, inferred ±21pts, isolated/placeholder ±10pts via `backend/app/fusion.py:57`.
> - `sentiment_risk_score` and `creator_feature_score` are still **placeholders 0.5** (Temporal 0% built per `CAPSTONE_NEXT_STEPS.md:822`, `ml/schema.py` reputation_score always null, CLIP/BERT weeks 9-10 not yet in this track). This is why Dashboard/Explainability show 15.0 pts each (0.3*0.5*100). See Task 2 answer below for rectification path (requires Temporal branch weights + real creator features, not just view change).
> - Graph: `co_occurs_with` 0->1,414 via historical pair logic; `collaborates_with` from `creator_related_accounts` where `relation_type="frequent_collaborator"`.
>
> **Replay instructions:**
> - No Track B code changes yet. If Change Log above gains entries (e.g. retrain with real sentiment/feature inputs, recalibrate fusion weights), apply diffs in order and re-run `python scripts/build_real_hetero_data.py` + `pytest tests/ -q` (69 tests) + verify checkpoint reload.
