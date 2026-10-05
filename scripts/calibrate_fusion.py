"""Fusion calibration report (PendingWork S3). Read only: never writes to the database.

    python scripts\\calibrate_fusion.py
    python scripts\\calibrate_fusion.py --briefs "fitness" "cricket bat and gear"

Answers two questions with data, and says plainly what the data cannot answer.

1. Can the weights w1/w2/w3 be fitted to an outcome? The only labelled outcome is
   the engagement lift of the 10 creators GAIL was trained on. For those 10 the
   script checks whether sentiment or feature carry any association with it.
2. Does the choice of weights matter? For each brief it re-ranks all creators
   under every weight combination on a 0.1 grid and measures how far the top-10
   and the full ranking move from the current 0.4 / 0.3 / 0.3.

Also prints the width of the new three-branch confidence interval. The results are
saved to models/fusion_calibration.json. Takes about a minute (loads CLIP and BERT).
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

DEFAULT_BRIEFS = [
    "fitness", "cricket bat and gear", "chess coaching",
    "makeup and skincare", "smartphone reviews", "yoga and wellness classes",
]
BASELINE = (0.4, 0.3, 0.3)
STEP = 0.1


def weight_grid(step: float = STEP) -> list[tuple[float, float, float]]:
    n = round(1 / step)
    return [(a * step, b * step, (n - a - b) * step) for a, b in itertools.product(range(n + 1), repeat=2) if a + b <= n]


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    from ml.feature_score import _average_ranks

    ra, rb = _average_ranks(np.asarray(a, float)), _average_ranks(np.asarray(b, float))
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def final_scores(branches: np.ndarray, w) -> np.ndarray:
    """Same formula as app/fusion.py, without the clamp (ranking only)."""
    adj = np.where(branches[:, 1] < 0.3, -10.0, 0.0)
    return 100 * branches @ np.asarray(w) + adj


def top_overlap(a: np.ndarray, b: np.ndarray, k: int = 10) -> float:
    ta, tb = set(np.argsort(-a, kind="stable")[:k]), set(np.argsort(-b, kind="stable")[:k])
    return len(ta & tb) / k


def permutation_p(x: np.ndarray, y: np.ndarray, n: int = 20000, seed: int = 0) -> float:
    """Two-sided permutation p-value for the Spearman correlation of x and y."""
    rng = np.random.default_rng(seed)
    obs = abs(spearman(x, y))
    hits = sum(abs(spearman(x, rng.permutation(y))) >= obs for _ in range(n))
    return (hits + 1) / (n + 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefs", nargs="+", default=DEFAULT_BRIEFS)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    os.environ["DATABASE_URL"] = re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    from ml._scipy_compat import avoid_blocked_scipy_solver

    avoid_blocked_scipy_solver()
    from sqlmodel import Session, create_engine, select

    from app import creator_features as cf
    from app.fusion import compute_fusion_score, feature_uncertainty, sentiment_uncertainty
    from app.models import Creator
    from app.spillover import get_spillover_batch
    from app.temporal import get_temporal_batch
    from ml.creator_embeddings import QueryEmbedder
    from ml.feature_extraction import FeatureExtractor
    from ml.inference import _ensure_loaded

    art = cf.load_artifact()
    if art is None:
        sys.exit("models/creator_embeddings.npz not found: run scripts\\compute_creator_embeddings.py first")
    with Session(create_engine(os.environ["DATABASE_URL"])) as s:
        ids = [str(c.creator_id) for c in s.exec(select(Creator)).all()]
        sp = get_spillover_batch(ids)
        tm = get_temporal_batch(s)
    n = len(ids)
    spill = np.array([sp[c]["spillover_unit"] for c in ids])
    sent = np.array([tm.get(c, {}).get("sentiment_risk_score", 0.5) for c in ids])
    n_comments = np.array([tm.get(c, {}).get("n_comments", 0) for c in ids])
    sent_scored = np.array([tm.get(c, {}).get("basis") == "scored" for c in ids])
    print(f"{n} creators; spillover basis: " + ", ".join(f"{b} {sum(sp[c]['basis'] == b for c in ids)}" for b in ("trained", "inferred", "isolated", "placeholder")))
    print(f"sentiment scored for {int(sent_scored.sum())}, neutral for {n - int(sent_scored.sum())}")

    # ---- 1. is there an outcome to fit the weights to? --------------------------------
    ck = _ensure_loaded()
    order = ck["ckpt"]["graph"]["creator_ids_order"]
    target = ck["ckpt"]["tensors"]["target"].view(-1).numpy()
    lab = [(ids.index(c), target[i]) for i, c in enumerate(order) if c in ck["trained_set"] and c in ids]
    li = np.array([i for i, _ in lab]); lt = np.array([t for _, t in lab])
    print(f"\n1. LABELLED OUTCOMES: {len(lab)} creators have an observed engagement lift (the GAIL training set).")
    assoc = {}
    for name, v in (("spillover (in-sample, GAIL was fitted on these)", spill), ("sentiment", sent)):
        r = spearman(v[li], lt)
        assoc[name] = {"spearman": r, "perm_p": permutation_p(v[li], lt)}
        print(f"   {name:50s} Spearman with lift {r:+.2f}  permutation p = {assoc[name]['perm_p']:.2f}")
    print("   feature score is brief-dependent and the 10 outcomes carry no brief, so it cannot be checked here.")
    print("   => no held-out outcome exists for sentiment or feature, and 10 points cannot fit 3 weights.")

    # ---- 2. how much does the choice of weights matter? ----------------------------------
    print("\n2. WEIGHT SENSITIVITY (baseline 0.4 / 0.3 / 0.3, 0.1 grid, " + str(len(weight_grid())) + " combinations)")
    print("   'near' = every weight within 0.1 of the baseline; 'all' = the whole grid.")
    emb = QueryEmbedder.from_extractor(FeatureExtractor(max_thumbnails=5))
    grid = weight_grid()
    near = [w for w in grid if max(abs(a - b) for a, b in zip(w, BASELINE)) <= STEP + 1e-9]
    per_brief = {}
    feats, results = {}, {}
    for brief in args.briefs:
        res = cf.score_query(brief, art, emb)
        feat = np.array([res[c]["score"] if c in res else 0.5 for c in ids])
        feats[brief] = feat
        results[brief] = res
        B = np.column_stack([spill, sent, feat])
        base = final_scores(B, BASELINE)
        out = {}
        for tag, ws in (("near", near), ("all", grid)):
            ov = [top_overlap(base, final_scores(B, w)) for w in ws]
            rho = [spearman(base, final_scores(B, w)) for w in ws]
            out[tag] = {"top10_overlap_median": float(np.median(ov)), "top10_overlap_min": float(np.min(ov)),
                        "spearman_median": float(np.median(rho)), "spearman_min": float(np.min(rho))}
        # how the three branches rank relative to each other
        out["branch_spearman"] = {"spillover~sentiment": spearman(spill, sent), "spillover~feature": spearman(spill, feat),
                                  "sentiment~feature": spearman(sent, feat)}
        per_brief[brief] = out
        print(f"   {brief!r:32s} near: top-10 overlap median {out['near']['top10_overlap_median']:.1f} (min {out['near']['top10_overlap_min']:.1f}), "
              f"rank corr median {out['near']['spearman_median']:.2f} | all: top-10 median {out['all']['top10_overlap_median']:.1f} "
              f"(min {out['all']['top10_overlap_min']:.1f}), rank corr min {out['all']['spearman_min']:.2f}")

    # ---- 3. the new confidence interval ------------------------------------------------
    print("\n3. CONFIDENCE INTERVAL (three branches, quadrature), brief = " + repr(args.briefs[0]))
    feat0, res0 = feats[args.briefs[0]], results[args.briefs[0]]
    widths, covers_all = [], 0
    for i, c in enumerate(ids):
        f = res0[c]
        _, lo, hi, _, _ = compute_fusion_score(
            spill[i], sent[i], feat0[i],
            spillover_half_width=(sp[c]["unit_high"] - sp[c]["unit_low"]) / 2, spillover_basis=sp[c]["basis"],
            sentiment_half_width=sentiment_uncertainty(int(n_comments[i]) if sent_scored[i] else None),
            feature_half_width=feature_uncertainty(f["basis"]),
        )
        widths.append(hi - lo)
        covers_all += lo <= 0.001 and hi >= 99.999
    widths = np.array(widths)
    print(f"   interval width in points: min {widths.min():.1f}, median {np.median(widths):.1f}, max {widths.max():.1f}; "
          f"{covers_all} of {n} span the whole 0-100 range (was 187 of 187 before)")

    # ---- 4. what it means ----------------------------------------------------------------
    allmin = min(v["all"]["spearman_min"] for v in per_brief.values())
    nearmed = float(np.median([v["near"]["top10_overlap_median"] for v in per_brief.values()]))
    print("\n4. READING")
    print(f"   Moving each weight by up to 0.1 keeps a median {nearmed * 10:.0f} of the top 10; the full grid moves the rank correlation as low as {allmin:.2f}.")
    print("   Weights stay 0.4 / 0.3 / 0.3 as documented priors. They are NOT fitted: no outcome exists to fit them to.")

    report = {
        "labelled_outcomes": len(lab), "association_with_lift": assoc, "baseline_weights": BASELINE,
        "per_brief": per_brief, "ci_width_points": {"min": float(widths.min()), "median": float(np.median(widths)), "max": float(widths.max())},
        "ci_spans_whole_range": int(covers_all), "creators": n,
    }
    (ROOT / "models" / "fusion_calibration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nsaved models/fusion_calibration.json")


if __name__ == "__main__":
    main()
