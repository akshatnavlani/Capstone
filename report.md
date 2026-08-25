# Track C Round Report — Real Spillover Wired (2026-08-26)

Commit: `65ec502` (P1.6 wired) on `track-c-fusion-backend`, vendoring `origin/track-b-ml-core:c6488a6` (`ml/inference.py` + `models/gail_checkpoint.pt`, 3.7M, prod model trained once on all 54 pairs, `effective N=10`, 259 nodes, `mse 1.84`).

Track B source: `ml/inference.py:load_predict` / `load_predict_batch` / `IsolatedCreatorError` with `t_{0.975,df}` table (2.306 at N=10), `hw = t*sqrt(mse)*sqrt(1+1/N)` base ≈3.28 min 0.15, inferred ×1.6 ≈5.25 min 0.25. Isolated (degree 0 on both `collaborates_with`+`co_occurs_with`) raises `IsolatedCreatorError` — do not fabricate.

---

## What wired (`backend/app/routers/scores.py:1`, `backend/app/fusion.py:57`, `backend/app/routers/influencers.py:237` — loader + fallback to `basis: placeholder`)

- Vendored `backend/app/gail/{inference.py,gail_model.py,schema.py,exposure.py,spillover_head.py,weighted_sage_conv.py,causal_regularization.py,model.py}` (patched `from ml.*` → `from app.gail.*`, `DEFAULT_CKPT` → `parents[2]/models/gail_checkpoint.pt`) + `backend/models/gail_checkpoint.pt`.
- Added `backend/app/spillover.py` wrapper: lazy `import torch` — on `FileNotFoundError`/`IsolatedCreatorError`/`KeyError`/`ImportError` returns `basis="placeholder"`/`"isolated"` with `spillover 0.5` and `wide CI 0.25` (never crash). `get_spillover_batch()` uses single GAT forward, cached.
- `backend/app/fusion.py:57` now honest: `margin = hw*100*w1` (`w1=0.4` only), clamped `[0,100]`; else fallback `±8`. Comment documents `N=10` wide intervals. `w1` only real, `w2` stays `0.5` placeholder — not recalibrated.
- `backend/app/schemas.py:41,184` added `SpilloverBasis = Literal["trained","inferred","placeholder","isolated"]` to `InfluencerRecommendation.spillover_basis` and `FusionScoreResponse.spillover_basis`; `POST /scores/compute` `spillover_score` now optional (auto-resolve if omitted).
- `backend/app/routers/scores.py:1` auto-resolves `get_spillover()` on `POST /compute` if `spillover_score is None`, persists `spillover_basis`, `GET /scores/{id}` live recomputes (not stale DB) and never 404s without placeholder — computes on-the-fly.
- `backend/app/routers/influencers.py:237` `POST /recommendations` batch-resolves via `get_spillover_batch` (single cached forward), `isolated→placeholder` never `inferred`, honest `spillover_basis` per row.
- `backend/app/models.py:250` + `backend/migrations/0003_add_fusion_spillover_basis.sql` (`spillover_basis varchar(12) default 'placeholder'`) applied live via pooler and via `init_db`.

---

## API shape change (`basis` + `confidence_low/high`, `w2` stays placeholder `CAPSTONE_NEXT_STEPS.md:822`)

Breaking but required — Track D must read `spillover_basis`:

```json
// InfluencerRecommendation & FusionScoreResponse now include:
{
  "spillover_basis": "trained" | "inferred" | "placeholder" | "isolated",
  "confidence_low": 0.0,
  "confidence_high": 100.0,
  "score_breakdown": {
    "spillover_score": 1.19,
    "sentiment_risk_score": 0.5,   // still placeholder, Temporal 0% (CAPSTONE_NEXT_STEPS.md:822)
    "creator_feature_score": 0.5,
    "weight_spillover": 0.4,
    "weight_sentiment_risk": 0.3,
    "weight_creator_feature": 0.3
  }
}
```

`spillover_basis` semantics (see `API_CONTRACTS.md` P1.6, `HANDOFF.md`):
- `trained` — in GAIL labeled N=10 set (`hw≈3.28` → `±13pts` on `final_score` via `w1=0.4`, still wide due N=10 + propensity `1.000` `CAPSTONE_NEXT_STEPS.md:795`).
- `inferred` — graph-connected but unlabeled, GAT inductive (`hw≈5.25` → `±21pts` wide, `1.6×`).
- `placeholder` — checkpoint missing / fallback `0.5` (`hw 0.25` → `±10pts`).
- `isolated` — degree 0 on both graphs → `0.5` with `±10pts`, never `inferred`, no crash.

`w2` (`sentiment_risk_score`) remains `0.5` placeholder — only `w1` real. Weights `0.4/0.3/0.3` not recalibrated. `confidence_low/high` already existed but now reflect honest `hw` when GAIL available, else fallback `±8`. Clamped `[0,100]` — even `trained` spans `0-100` at this N/mse.

Fallback: checkpoint missing / `torch` missing / `KeyError` / `IsolatedCreatorError` → `placeholder`/`isolated` — never 500.

---

## Verification — Task 1-4 explicitly confirmed

**Task 1 (loader + fallback):** `backend/app/spillover.py` wraps `app.gail.inference:load_predict`; `IsolatedCreatorError` → `isolated` not `inferred`; missing checkpoint/torch → `placeholder`. Verified via `TestClient` + live `get_spillover` for `c4b20… Virat` (trained), `89972… AB` (inferred), `78e48… _bungy` (isolated).

**Task 2 (wide CI, tighter for trained but still wide):** `backend/app/fusion.py:57` comment + `spillover.py` `hw` derivation; live `mse 1.84 N=10 t=2.306 → base 3.28 inferred 5.25 → final `±13/±21pts` clamped `0-100` via `hw*100*w1`. See `API_CONTRACTS.md` P1.6+ Fusion.

**Task 3 (w2 stays placeholder):** `sentiment_risk_score` hard `0.5` in `recommendations` and `scores`; `fusion.py` doc states only `w1` real; `API_CONTRACTS.md` What's real table: `Spillover real`, `Sentiment-risk placeholder`.

**Task 4 (live Supabase pooler `CAPSTONE_NEXT_STEPS.md:440`):**

- `pytest backend/tests -q` **49 passed** (lazy GAIL import, no torch needed for CI) — `backend/.venv`.
- `curl /health` via `TestClient` with `workdir backend` (pooler `DATABASE_URL`):
```json
{"status":"ok","db_connected":true,"version":"0.1.0"}
```
- `curl /feature-store/edges/sponsorships` → 16 edges (reconciles `is_sponsored=true AND brand_id IS NOT NULL`).

**3 real JSON snippets from `GET /recommendations` (via `POST /recommendations` with live pooler) + `GET /scores/{id}`:**

Trained (GAIL labeled, still wide CI):
```json
// POST /recommendations {"product_category":"athlete","budget":200000000,"max_results":5} → top result
{
  "creator_id": "c4b20dc1-14f2-48e9-8bd5-7131af29049f",
  "name": "Virat Kohli",
  "category": "athlete",
  "youtube_handle": null,
  "instagram_handle": "virat.kohli",
  "reddit_handles": ["KingKohli","ViratKohli"],
  "final_score": 100.0,
  "confidence_low": 0.0,
  "confidence_high": 100.0,
  "spillover_basis": "trained",
  "estimated_reach": 272234883,
  "estimated_cost": 136117441.5,
  "score_breakdown": {
    "spillover_score": 21.615880966186523,
    "sentiment_risk_score": 0.5,
    "creator_feature_score": 0.5,
    "weight_spillover": 0.4,
    "weight_sentiment_risk": 0.3,
    "weight_creator_feature": 0.3
  }
}
// GET /scores/c4b20dc1... same basis trained
```

Inferred (graph-connected but unlabeled, wide CI):
```json
// GET /scores/89972049-1966-4f17-9c9d-e3343c62d090  (AB de Villiers)
{
  "creator_id": "89972049-1966-4f17-9c9d-e3343c62d090",
  "final_score": 77.6240062713623,
  "confidence_low": 0.0,
  "confidence_high": 100.0,
  "risk_adjustment": 0.0,
  "breakdown": {
    "spillover_score": 1.1906001567840576,
    "sentiment_risk_score": 0.5,
    "creator_feature_score": 0.5,
    "weight_spillover": 0.4,
    "weight_sentiment_risk": 0.3,
    "weight_creator_feature": 0.3
  },
  "spillover_basis": "inferred",
  "computed_at": "2026-08-25T20:27:48.567341Z",
  "is_placeholder_formula": true
}
// also via POST /recommendations {"product_category":"athlete","budget":5000000} → PV Sindhu inferred 8.59
```

Isolated/placeholder (degree 0, no crash, 0.5 ±10):
```json
// GET /scores/78e4817c-077f-4b4c-95de-2a8c043e5cf5  (_bungy_lover_.01)
{
  "creator_id": "78e4817c-077f-4b4c-95de-2a8c043e5cf5",
  "final_score": 50.0,
  "confidence_low": 40.0,
  "confidence_high": 60.0,
  "risk_adjustment": 0.0,
  "breakdown": {
    "spillover_score": 0.5,
    "sentiment_risk_score": 0.5,
    "creator_feature_score": 0.5,
    "weight_spillover": 0.4,
    "weight_sentiment_risk": 0.3,
    "weight_creator_feature": 0.3
  },
  "spillover_basis": "isolated",
  "computed_at": "2026-08-25T20:27:48.650986Z",
  "is_placeholder_formula": true
}
// also via POST /recommendations {"product_category":"fitness apparel","budget":5000000} → Nisha Kumari isolated
{
  "creator_id": "fab5e263-56c7-43df-b0b9-345a659ac005",
  "name": "Nisha Kumari",
  "spillover_basis": "isolated",
  "final_score": 50.0,
  "confidence_low": 40.0,
  "confidence_high": 60.0,
  "score_breakdown": {"spillover_score": 0.5, "sentiment_risk_score": 0.5, "creator_feature_score": 0.5, ...}
}
```

All three carry `spillover_basis` + `confidence_low/high` so Track D can distinguish `trained` vs `inferred` (wide) vs `isolated`/`placeholder` without guessing.

---

## What remains

- **Periodic `POST /labeling/run?force=true`** as Track A lands new content (routine, `is_sponsored` still the sole GAIL treatment; precision-first, manual spot-check `"sponsored by"` / `"in partnership with"` 4/4 Reddit false positives previously).
- **`brand_id` backfill** — 61 events → 16 edges; 45 still `brand_id IS NULL` incl. `mrbeast` `Db5rzczsSV5` (Old Navy) — Track A's extraction lag, not Track C.
- **Temporal/sentiment** (`w2`, `reputation_score` `CAPSTONE_NEXT_STEPS.md:808`, `co_occurs_with` now ~1400 real) — 0% built, next is Track B Temporal branch, not Track C recalibration.
- **No retrain in Track C, no `ml/` edits, no sentiment fake** — per spec.

---

*Track D pending until next session — will surface `PENDING_TRACK_D.md:1` first thing then.*
