"""Held-out check of GAIL-R itself: does its spillover term explain engagement changes of creators it never saw? Offline; writes models/gail_r_holdout.json.

    python scripts/gail_r_holdout.py INPUTS.pt [--folds 5] [--repeats 20] [--out models/gail_r_holdout.json]

INPUTS.pt: the real graph, treatment windows and observations of a training run, saved by a one-line hook in a scratch copy of Eesha's train_prod_model.py (GAIL_DUMP_R) right before training.
The older held-out script (train_holdout_round3.py) scores the GAIL v1 predictor; GAIL-R is an effect estimator, so its fair out-of-sample test is the R-learner's own loss.

METHOD. Split CREATORS into folds (a creator's observations never straddle a split). On the training folds fit GAIL-R with uniform neighbour weights (the same fit the bootstrap uses), keeping its two
effect slopes (collaborates_with, co_occurs_with). On the held-out creators: predict the baseline change and the expected exposure from the training rows with ridge, then compare
  loss without effect term = mean(residual^2)      loss with effect term = mean((residual - sum slope_r * (exposure_r - expected exposure_r))^2)
where residual = observed change - predicted baseline. GAIN = 1 - loss_with / loss_without: above 0 means the effect term helped on unseen creators. Repeated with different fold splits; the interval
resamples creators. NULL: the same procedure with every observation given another window's exposure (a wrong-time placebo); its gain shows how much "help" appears by chance.
LIMITS: 11-18 observations have a sponsored collaborator, so almost every held-out row has exposure 0 and the gain is dominated by the few exposed rows; the interval is wide by construction.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ml.gail_r import RELATIONS, Observations, _gather, fit_gail_r, nuisance_features, uniform_share  # noqa: E402


def ridge_fit_predict(Xtr, Ytr, Xte, lam=1.0):
    Z = torch.cat([torch.ones(Xtr.size(0), 1), Xtr], dim=1)
    eye = torch.eye(Z.size(1))
    eye[0, 0] = 0.0
    beta = torch.linalg.solve(Z.T @ Z + lam * eye, Z.T @ Ytr)
    return torch.cat([torch.ones(Xte.size(0), 1), Xte], dim=1) @ beta


def one_split(data, treatments, obs, X, U, folds, seed):
    """Per-row held-out squared loss without and with the effect term, for one random split of creators."""
    g = torch.Generator().manual_seed(seed)
    creators = obs.node.unique()
    fold_of = dict(zip(creators.tolist(), torch.randint(0, folds, (len(creators),), generator=g).tolist()))
    fold = torch.tensor([fold_of[int(c)] for c in obs.node])
    without = torch.zeros(len(obs.y))
    withe = torch.zeros(len(obs.y))
    for f in range(folds):
        te, tr = fold == f, fold != f
        if not te.any() or tr.sum() < 20:
            continue
        fit = fit_gail_r(data, treatments, obs.subset(tr.nonzero().squeeze(1)), placebo_weight=0.0, seed=seed, uniform=True)
        slopes = torch.tensor([fit["slopes"][r] for r in RELATIONS])
        m_hat = ridge_fit_predict(X[tr], obs.y[tr].unsqueeze(1), X[te]).squeeze(1)
        e_hat = ridge_fit_predict(X[tr], U[tr], X[te])
        res = obs.y[te] - m_hat
        without[te] = res.pow(2)
        withe[te] = (res - ((U[te] - e_hat) * slopes).sum(1)).pow(2)
    return without, withe


def evaluate(data, treatments, obs, X, U, folds, repeats, seed0):
    diffs = torch.zeros(len(obs.y))
    gains = []
    for r in range(repeats):
        wo, wi = one_split(data, treatments, obs, X, U, folds, seed0 + r)
        diffs += (wo - wi) / repeats
        gains.append(float(1 - wi.sum() / wo.sum()))
    return diffs, gains


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--repeats", type=int, default=20)
    ap.add_argument("--out", default=str(ROOT / "models" / "gail_r_holdout.json"))
    args = ap.parse_args()
    blob = torch.load(args.inputs, weights_only=False)
    data, treatments = blob["data"], blob["treatments"]
    obs = Observations(node=blob["node"], window=blob["window"], y=blob["y"], pre=blob["pre"])
    n = data["creator"].x.size(0)
    X = nuisance_features(data["creator"].x, 16)[obs.node]
    U_win = [torch.stack([uniform_share(data["creator", r, "creator"].edge_index, t, n) if ("creator", r, "creator") in data.edge_types else torch.zeros(n) for r in RELATIONS], dim=1) for t in treatments]
    U = _gather(U_win, obs)
    exposed = U[:, 0] > 0
    print(f"{len(obs.y)} observations from {len(obs.node.unique())} creators in {len(treatments)} windows; {int(exposed.sum())} with a sponsored collaborator")

    diffs, gains = evaluate(data, treatments, obs, X, U, args.folds, args.repeats, 100)
    # wrong-window null: each row gets the exposure of a random other window for the same creator
    rng = np.random.default_rng(7)
    null_gains = []
    for k in range(args.repeats):
        shuffled = Observations(node=obs.node, window=torch.tensor(rng.permutation(obs.window.numpy())), y=obs.y, pre=obs.pre)
        Un = _gather(U_win, shuffled)
        _, g = evaluate(data, treatments, shuffled, X, Un, args.folds, 1, 500 + k)
        null_gains.append(g[0])

    creators = obs.node.unique()
    rows_of = [(obs.node == c).nonzero().squeeze(1) for c in creators]
    boots = []
    g = torch.Generator().manual_seed(11)
    for _ in range(2000):
        pick = torch.randint(0, len(creators), (len(creators),), generator=g)
        idx = torch.cat([rows_of[int(i)] for i in pick])
        boots.append(float(diffs[idx].mean()))
    res = {
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "observations": len(obs.y), "creators": len(creators), "windows": len(treatments), "exposed_observations": int(exposed.sum()),
        "folds": args.folds, "repeats": args.repeats,
        "gain_median": round(float(np.median(gains)), 4), "gain_range": [round(min(gains), 4), round(max(gains), 4)],
        "mean_loss_reduction_per_row": round(float(diffs.mean()), 5), "ci95_loss_reduction": [round(float(np.percentile(boots, 2.5)), 5), round(float(np.percentile(boots, 97.5)), 5)],
        "null_gain_median": round(float(np.median(null_gains)), 4), "null_gain_95th": round(float(np.percentile(null_gains, 95)), 4),
        "note": "gain = 1 - loss_with / loss_without on held-out creators; above 0 means the effect term helped. The null gives every row another window's exposure.",
        "limits": "only a handful of held-out rows have exposure above 0, so the interval is wide by construction",
    }
    print(json.dumps(res, indent=1))
    Path(args.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
