"""Run the spillover effect estimators on exported data folders (real + planted-effect controls) and save models/spillover_effect_check.json.

Each folder holds creators.json, collab_edges.json, co_occurrence_edges.json, training_pair_deltas.json (see make_unexposed_controls.py, which adds
the unexposed comparison group and builds the planted worlds). The planted worlds are the pass/fail check: the estimator must find nothing at
effect 0 and find the large planted effect. Lifts are clipped to +/-5 (heavy tails). Read only on the database (list of sponsored creators).

    python scripts/run_spillover_check.py [--out results.json] <dir_real> <dir_beta_0.0> <dir_beta_0.5> <dir_beta_1.0>
(default output: models/spillover_effect_check.json)
"""
import json
import os
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import psycopg2
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml.spillover_effect import aipw_cross_fit, bootstrap_effects  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CLIP = 5.0


def load(data_dir: str):
    d = Path(data_dir)
    creators = json.load(open(d / "creators.json", encoding="utf-8"))
    ids = [c["creator_id"] for c in creators]
    idx = {c: i for i, c in enumerate(ids)}
    url = os.environ.get("DATABASE_URL") or dotenv_values(Path(__file__).resolve().parents[1] / ".env")["DATABASE_URL"]
    cur = psycopg2.connect(url).cursor()
    cur.execute("select distinct creator_id::text from creator_sponsorship_events")
    own = {r[0] for r in cur.fetchall()}
    neigh = defaultdict(set)
    for f in ("collab_edges.json", "co_occurrence_edges.json"):
        for e in json.load(open(d / f, encoding="utf-8")):
            neigh[e["target_creator_id"]].add(e["source_creator_id"])
            neigh[e["source_creator_id"]].add(e["target_creator_id"])
    t = np.array([1.0 if neigh[c] & own else 0.0 for c in ids])
    deg = np.array([len(neigh[c]) for c in ids], dtype=float)
    num = lambda k: [float("nan") if c[k] is None else float(c[k]) for c in creators]  # noqa: E731
    cov = np.column_stack([np.array([c["category_one_hot"] for c in creators], dtype=float), num("log_subscriber_count"),
                           num("engagement_rate"), num("reputation_score"), np.log1p(deg), [1.0 if c in own else 0.0 for c in ids]])
    cov = cov[:, ~np.isnan(cov).all(0)]                      # drop columns that are empty for every creator
    cov = np.where(np.isnan(cov), np.nanmedian(cov, axis=0), cov)
    cov = (cov - cov.mean(0)) / np.where(cov.std(0) > 0, cov.std(0), 1.0)
    lifts = defaultdict(list)
    for r in json.load(open(d / "training_pair_deltas.json", encoding="utf-8")):
        if r.get("mean_lift") is not None:
            lifts[r["neighbour_id"]].append(r["mean_lift"])
    lab = np.array(sorted(idx[c] for c in lifts if c in idx))
    y = np.zeros(len(ids))
    for c, v in lifts.items():
        if c in idx:
            y[idx[c]] = st.mean(v)
    y[lab] = np.clip(y[lab], -CLIP, CLIP)
    return cov, t, y, lab


def main() -> int:
    args = sys.argv[1:]
    out_path = Path(__file__).resolve().parents[1] / "models" / "spillover_effect_check.json"
    if "--out" in args:
        i = args.index("--out")
        out_path = Path(args[i + 1])
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return 1
    results = {}
    for d in args:
        cov, t, y, lab = load(d)
        out = bootstrap_effects(cov, t, y, lab)
        ate, err = aipw_cross_fit(cov, t, y, lab)
        out.update(n_labelled=int(len(lab)), n_exposed=int(t[lab].sum()), aipw=ate, aipw_se=err)
        name = Path(d).name
        results[name] = out
        lo, hi = out["difference_in_means_ci"]
        alo, ahi = out["adjusted_ci"]
        print(f"{name:9s} n={out['n_labelled']} exposed={out['n_exposed']} | diff-in-means {out['difference_in_means']:+.3f} [{lo:+.3f}, {hi:+.3f}] "
              f"{'EXCLUDES 0' if out['difference_in_means_excludes_zero'] else 'includes 0'} | adjusted {out['adjusted']:+.3f} [{alo:+.3f}, {ahi:+.3f}] "
              f"{'EXCLUDES 0' if out['adjusted_excludes_zero'] else 'includes 0'} | AIPW {ate:+.3f} (se {err:.3f})")
    json.dump(results, open(out_path, "w", encoding="utf-8"), indent=1)
    print("saved", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
