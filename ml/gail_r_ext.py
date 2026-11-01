"""GAIL-R extensions E4 and E5. New file: ml/gail_r.py (branch merge-eesha-ml) is left as it is.

E4  Attention supervised by the causal-estimation error.
    GAIL-R already trains the relation attention through the orthogonalised (residual-on-residual) loss, so the attention is supervised by the causal error and not by plain outcome
    error. `fit_gail_r_supervised` makes that choice explicit and lets it be switched, so the claim can be tested instead of asserted:
      supervision="causal"   loss on (y - m(X)) against slope * (exposure - e_hat(X)); the confounder-explained part is removed before attention is judged.
      supervision="plain"    loss on y against bias + slope * exposure; attention is rewarded for anything that predicts the outcome, including confounding.
    The ablation script compares the two (and uniform weights) where the true effect is known.

E5  Mismeasured treatment.
    A sponsored post that the rules miss makes a creator look unsponsored, so some "unexposed" observations were exposed and the exposure of the exposed is understated. `simex_gail_r`
    is MC-SIMEX (Kuechenhoff, Mwalili and Lesaffre 2006) for this one-sided misclassification: a label is kept with probability `recall`; extra misclassification at level lambda keeps a label
    with probability recall**lambda; the estimate is computed at lambda = 0 (as observed), and at several larger lambdas, and the trend is extrapolated back to lambda = -1, which
    stands for no misclassification. It needs the recall as an input (it cannot be learned from these data); the caller reports a range of recalls, not one value.
"""

from __future__ import annotations

import torch
from torch import nn

from ml.gail_r import (RELATIONS, Observations, GAILR, _gather, nuisance_features, oof_ridge, uniform_share)
from ml.placebo import placebo_penalty


def fit_gail_r_supervised(data, treatments: list[torch.Tensor], obs: Observations, supervision: str = "causal", placebo_weight: float = 30.0,
                          shrink: float = 100.0, epochs: int = 200, lr: float = 1e-2, k_pcs: int = 16, ridge_lam: float = 1.0, seed: int = 0) -> dict:
    """GAIL-R with LEARNED attention and a switch for what supervises it. Returns the same keys as fit_gail_r (`ate`, `att`, `tau`, `slopes`, `n_exposed`)."""
    if supervision not in ("causal", "plain"):
        raise ValueError("supervision must be 'causal' or 'plain'")
    n = data["creator"].x.size(0)
    X = nuisance_features(data["creator"].x, k_pcs)[obs.node]
    m_hat = oof_ridge(X, obs.y, obs.node, lam=ridge_lam, seed=seed)
    U_win = [torch.stack([uniform_share(data["creator", r, "creator"].edge_index, t, n) if ("creator", r, "creator") in data.edge_types else torch.zeros(n)
                          for r in RELATIONS], dim=1) for t in treatments]
    U = _gather(U_win, obs)
    e_hat = oof_ridge(X, U, obs.node, lam=ridge_lam, seed=seed)
    y_res = obs.y - m_hat
    has_pre = ~torch.isnan(obs.pre)

    torch.manual_seed(seed)
    model = GAILR()
    bias = nn.Parameter(torch.zeros(()))
    opt = torch.optim.Adam([*model.parameters(), bias], lr=lr)
    for _ in range(epochs):
        opt.zero_grad()
        E = _gather(model.exposures(data, treatments), obs)
        if supervision == "causal":
            loss = (y_res - ((E - e_hat) * model.slopes).sum(1)).pow(2).mean()
        else:
            loss = (obs.y - bias - (E * model.slopes).sum(1)).pow(2).mean()
        loss = loss + shrink * (E - U).pow(2).mean()
        if placebo_weight > 0 and int(has_pre.sum()) >= 2:
            loss = loss + placebo_weight * placebo_penalty((E * model.slopes).sum(1)[has_pre], obs.pre[has_pre])
        loss.backward()
        opt.step()
    with torch.no_grad():
        E = _gather(model.exposures(data, treatments), obs)
        tau = (E * model.slopes).sum(1)
    exposed = U[:, 0] > 0
    return {"ate": float(tau.mean()), "att": float(tau[exposed].mean()) if exposed.any() else float("nan"), "n_exposed": int(exposed.sum()), "tau": tau,
            "slopes": dict(zip(model.relations, model.slopes.detach().tolist()))}


def drop_labels(treatments: list[torch.Tensor], keep_prob: float, generator: torch.Generator) -> list[torch.Tensor]:
    """Keep each sponsored label (value 1) with probability keep_prob; 0 stays 0 (one-sided misclassification)."""
    out = []
    for t in treatments:
        kept = (torch.rand(t.shape, generator=generator) < keep_prob).to(t.dtype)
        out.append(t * kept)
    return out


def _quadratic_to_minus_one(lams: list[float], vals: list[float]) -> float:
    """Least-squares quadratic through (lambda, value), evaluated at lambda = -1."""
    a = torch.tensor([[1.0, l, l * l] for l in lams], dtype=torch.float64)
    coef = torch.linalg.lstsq(a, torch.tensor(vals, dtype=torch.float64).unsqueeze(1)).solution.squeeze(1)
    return float(coef[0] - coef[1] + coef[2])


def simex_gail_r(data, treatments: list[torch.Tensor], obs: Observations, recall: float, lambdas=(0.5, 1.0, 1.5, 2.0), draws: int = 8, seed: int = 0, **fit_kw) -> dict:
    """MC-SIMEX correction of GAIL-R for labels missed with probability 1 - recall. Uses uniform attention (the fit the bootstrap uses), so it is fast.

    Returns the naive estimate (lambda 0), the SIMEX-corrected estimate (quadratic extrapolation to lambda -1) and the whole curve, for the average effect (`ate`), the effect on the
    exposed (`att`) and each relation slope."""
    from ml.gail_r import fit_gail_r
    if not 0.0 < recall <= 1.0:
        raise ValueError("recall must be in (0, 1]")
    g = torch.Generator().manual_seed(seed)
    naive = fit_gail_r(data, treatments, obs, uniform=True, seed=seed, **fit_kw)
    keys = {"ate": lambda f: f["ate"], "att": lambda f: f["att"], **{f"slope_{r}": (lambda f, r=r: f["slopes"][r]) for r in RELATIONS}}
    curve = {k: [keys[k](naive)] for k in keys}
    lams = [0.0]
    for lam in lambdas:
        fits = [fit_gail_r(data, drop_labels(treatments, recall ** lam, g), obs, uniform=True, seed=seed, **fit_kw) for _ in range(draws)]  # same seed: only the labels vary
        lams.append(float(lam))
        for k, fn in keys.items():
            vals = [fn(f) for f in fits if fn(f) == fn(f)]  # drop NaN
            curve[k].append(sum(vals) / len(vals) if vals else float("nan"))
    corrected = {}
    for k, vals in curve.items():
        ok = [(l, v) for l, v in zip(lams, vals) if v == v]
        corrected[k] = _quadratic_to_minus_one([l for l, _ in ok], [v for _, v in ok]) if len(ok) >= 3 else float("nan")
    return {"recall": recall, "lambdas": lams, "curve": curve, "naive": {k: v[0] for k, v in curve.items()}, "corrected": corrected}
