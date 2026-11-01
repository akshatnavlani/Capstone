"""Fusion weights against a PROXY outcome (read only; never writes to the database). Writes models/fusion_calibration_proxy.json.

    python scripts\\calibrate_fusion_proxy.py [--brief fitness] [--min-comments 3000]

WHY. No sales or conversion data exists, so the weights w1/w2/w3 (spillover, sentiment, feature) cannot be fitted to a real outcome (see calibrate_fusion.py).
The nearest thing we hold is how much of a creator's audience writes comments that look like buying or asking where to buy (scripts/ingestion/purchase_intent.py):
buying-looking comments per 1,000 comments on the creator's YouTube videos. It is a proxy, not sales, and the sentiment branch is computed from the same comments, so a
link between the two can be partly mechanical. The result is therefore only an indication.

METHOD. For creators with at least --min-comments comments: (1) Spearman of each branch with the proxy; (2) the spread of each branch (a branch that barely varies cannot
carry a weight); (3) repeated 5-fold cross-validation BY CREATOR: pick the weights on the 0.1 grid that rank the training creators best against the proxy, then compare them
with the current 0.2 / 0.4 / 0.4 on the held-out creators. The fitted weights are worth adopting only if they beat the current ones on held-out creators in most repeats.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_fusion import BASELINE, final_scores, permutation_p, spearman, weight_grid  # noqa: E402


def load_env() -> None:
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if p.exists():
            m = re.search(r"^DATABASE_URL=(.+)$", p.read_text(encoding="utf-8"), re.M)
            if m:
                os.environ["DATABASE_URL"] = m.group(1).strip().strip('"')
                return
    sys.exit("DATABASE_URL not found in backend/.env or .env")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", default="fitness")
    ap.add_argument("--min-comments", type=int, default=3000)
    ap.add_argument("--repeats", type=int, default=200)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env()
    from ml._scipy_compat import avoid_blocked_scipy_solver

    avoid_blocked_scipy_solver()
    import psycopg2
    from sqlmodel import Session, create_engine, select

    from app import creator_features as cf
    from app.models import Creator
    from app.spillover import get_spillover_batch
    from app.temporal import get_temporal_batch
    from ml.creator_embeddings import QueryEmbedder
    from ml.feature_extraction import FeatureExtractor

    art = cf.load_artifact()
    if art is None:
        sys.exit("models/creator_embeddings.npz not found: run scripts\\compute_creator_embeddings.py first")
    with Session(create_engine(os.environ["DATABASE_URL"])) as s:
        ids = [str(c.creator_id) for c in s.exec(select(Creator)).all()]
        sp = get_spillover_batch(ids)
        tm = get_temporal_batch(s)
    spill = np.array([sp[c]["spillover_unit"] for c in ids])
    sent = np.array([tm.get(c, {}).get("sentiment_risk_score", 0.5) for c in ids])
    res = cf.score_query(args.brief, art, QueryEmbedder.from_extractor(FeatureExtractor(max_thumbnails=5)))
    feat = np.array([res[c]["score"] if c in res else 0.5 for c in ids])

    conn = psycopg2.connect(os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://"), connect_timeout=20)
    cur = conn.cursor()
    cur.execute("select v.creator_id::text, count(*) from youtube_comments c join youtube_videos v on v.video_id = c.video_id group by 1")
    total = dict(cur.fetchall())
    cur.execute("select creator_id::text, count(*) from purchase_intent_comments where platform = 'youtube' group by 1")
    buying = dict(cur.fetchall())
    conn.close()

    keep = [i for i, c in enumerate(ids) if total.get(c, 0) >= args.min_comments]
    y = np.array([1000.0 * buying.get(ids[i], 0) / total[ids[i]] for i in keep])
    B = np.column_stack([spill[keep], sent[keep], feat[keep]])
    n = len(keep)
    print(f"{n} creators with at least {args.min_comments} comments; brief {args.brief!r}; buying-looking comments per 1,000: median {np.median(y):.2f}, max {y.max():.1f}")

    out: dict = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "brief": args.brief, "creators_used": n, "min_comments": args.min_comments,
                 "proxy": "buying-looking comments per 1,000 YouTube comments (not sales)", "branches": {}}
    for k, name in enumerate(("spillover", "sentiment", "feature")):
        r = spearman(B[:, k], y)
        out["branches"][name] = {"spearman_with_proxy": round(r, 3), "permutation_p": round(permutation_p(B[:, k], y, n=5000), 4),
                                 "sd": round(float(B[:, k].std()), 4), "distinct_values": int(len(np.unique(B[:, k].round(6))))}
        print(f"  {name:10s} Spearman with proxy {r:+.2f} (p {out['branches'][name]['permutation_p']:.3f}); spread sd {B[:, k].std():.3f}, {out['branches'][name]['distinct_values']} distinct values")
    out["sentiment_vs_feature_spearman"] = round(spearman(B[:, 1], B[:, 2]), 3)

    grid = weight_grid()
    base_all = spearman(final_scores(B, BASELINE), y)
    best_all = max(grid, key=lambda w: np.nan_to_num(spearman(final_scores(B, w), y), nan=-9))
    out["in_sample"] = {"baseline_spearman": round(base_all, 3), "best_weights": best_all, "best_spearman": round(spearman(final_scores(B, best_all), y), 3)}
    print(f"  in-sample: current weights {BASELINE} Spearman {base_all:+.2f}; best on the grid {tuple(round(v, 1) for v in best_all)} Spearman {out['in_sample']['best_spearman']:+.2f} (optimistic: fitted and scored on the same creators)")

    rng = np.random.default_rng(0)
    diffs, chosen = [], []
    for _ in range(args.repeats):
        fold = rng.integers(0, 5, n)
        for f in range(5):
            tr, te = fold != f, fold == f
            if te.sum() < 8 or tr.sum() < 20:
                continue
            w = max(grid, key=lambda w: np.nan_to_num(spearman(final_scores(B[tr], w), y[tr]), nan=-9))
            chosen.append(w)
            diffs.append(np.nan_to_num(spearman(final_scores(B[te], w), y[te]), nan=0.0) - np.nan_to_num(spearman(final_scores(B[te], BASELINE), y[te]), nan=0.0))
    diffs = np.array(diffs)
    mean_w = tuple(round(float(np.mean([w[k] for w in chosen])), 2) for k in range(3))
    out["held_out"] = {"folds_scored": int(len(diffs)), "mean_gain_spearman_vs_current": round(float(diffs.mean()), 4), "share_folds_fitted_beats_current": round(float((diffs > 0).mean()), 3),
                       "ci95_gain": [round(float(np.percentile(diffs, 2.5)), 3), round(float(np.percentile(diffs, 97.5)), 3)], "mean_chosen_weights": mean_w}
    verdict = ("fitted weights beat the current ones on held-out creators in most folds" if diffs.mean() > 0.02 and (diffs > 0).mean() > 0.6
               else "fitted weights do NOT beat the current ones on held-out creators: keep the documented priors")
    out["verdict"] = verdict
    negative = [k for k, v in out["branches"].items() if v["spearman_with_proxy"] < 0 and v["permutation_p"] < 0.05]
    out["interpretation"] = ("Do NOT adopt automatically. " + (f"{', '.join(negative)} correlate NEGATIVELY with the buying-comment proxy, so the fit would switch them off. "
                             if negative else "") +
                             "The sentiment branch exists as a brand-safety guard, not as a predictor of buying interest, and the proxy shares its comments with it; the spillover branch takes only a few "
                             "distinct values. A proxy fit that drops brand safety and spillover is a sign the proxy is the wrong target for those branches, not that they carry no value. Keep the documented priors unless a real outcome becomes available.")
    print(f"  held-out: fitted minus current Spearman {diffs.mean():+.3f} (95% range {out['held_out']['ci95_gain'][0]:+.2f} to {out['held_out']['ci95_gain'][1]:+.2f}); "
          f"fitted wins in {100 * (diffs > 0).mean():.0f}% of folds; average chosen weights {mean_w}")
    print("  =>", verdict)
    out["limits"] = "proxy, not sales; sentiment and the proxy come from the same comments; spillover varies little (see distinct_values), so its weight is barely identifiable; one brief"
    (ROOT / "models" / "fusion_calibration_proxy.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("saved models/fusion_calibration_proxy.json")


if __name__ == "__main__":
    main()
