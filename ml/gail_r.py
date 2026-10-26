"""GAIL-R: orthogonalised (R-learner) training of GAIL's exposure effect.

WHY. The original GAIL head predicts the outcome from [embedding, exposure]
with one network. On ~400 creators with 1,289-d features that network
memorises every outcome within ~50 epochs (training MSE 0.02 against a noise
variance of 0.25 in the semi-synthetic benchmark), so nothing is left for
exposure to explain and the learned effect collapses to ~0, even when the true
effect is large. Cross-fitting the old model does not help: it memorises the
training fold just the same.

WHAT CHANGES. Robinson's decomposition (the R-learner / double machine
learning):

    y - m(X)  =  sum_r slope_r * (e_r - e_r_hat(X))  +  noise

  * m(X) and e_r_hat(X) are predicted OUT-OF-FOLD, with folds split by creator,
    so no creator's own outcome is used to predict it. A creator cannot memorise
    a residual it never saw.
  * e_r is the per-relation exposure (share of a creator's neighbours under
    relation r that are sponsored), weighted by GAIL's relation-specific
    attention. slope_r is the effect of relation r; a relation can come out at
    0, which the old softmax beta could not express.
  * Attention is shrunk toward uniform weights; it departs from uniform only as
    far as the data supports. In the semi-synthetic benchmark, unshrunk
    attention fitted noise (co-mention slope swinging -0.5 to +0.5 by seed).
  * The placebo penalty (ml.placebo) is applied to the learned effect against
    the pre-period lift, so a link whose "effect" also explains changes BEFORE
    the sponsorship is shrunk.

The per-observation effect is tau = sum_r slope_r * e_r; the estimate is its
mean, with a creator-level (cluster) bootstrap interval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import nn

from ml.gail_model import GAILModel
from ml.placebo import placebo_penalty
from ml.schema import CREATOR_FEATURE_DIM, CREATOR_METADATA_DIM

RELATIONS = ("collaborates_with", "co_occurs_with")


@dataclass
class Observations:
    """One row per (creator, window) outcome."""

    node: torch.Tensor    # (M,) creator index
    window: torch.Tensor  # (M,) index into the list of treatment vectors
    y: torch.Tensor       # (M,) outcome lift
    pre: torch.Tensor     # (M,) pre-period lift, NaN where unavailable

    def subset(self, idx: torch.Tensor) -> "Observations":
        return Observations(self.node[idx], self.window[idx], self.y[idx], self.pre[idx])


def nuisance_features(x: torch.Tensor, k: int = 16) -> torch.Tensor:
    """Low-capacity inputs for the nuisance models: the metadata tail plus the
    top-k principal components of the content (CLIP/BERT) features. The full
    1,289-d vector would let a ridge model overfit 400 creators."""
    meta = x[:, -CREATOR_METADATA_DIM:]
    content = x[:, :-CREATOR_METADATA_DIM]
    c = content - content.mean(0)
    k = min(k, c.size(0) - 1, c.size(1))
    if k <= 0:
        return meta
    _, s, v = torch.linalg.svd(c, full_matrices=False)
    pcs = c @ v[:k].T / s[:k].clamp(min=1e-6) * math.sqrt(c.size(0))
    return torch.cat([meta, pcs], dim=1)


def oof_ridge(X: torch.Tensor, Y: torch.Tensor, groups: torch.Tensor, k: int = 5,
              lam: float = 1.0, seed: int = 0) -> torch.Tensor:
    """Out-of-fold ridge predictions, folds split by `groups` (creator) so a
    creator's rows are never used to predict that creator."""
    uniq = groups.unique()
    g = torch.Generator().manual_seed(seed)
    fold_of = dict(zip(uniq.tolist(), torch.randint(0, k, (len(uniq),), generator=g).tolist()))
    fold = torch.tensor([fold_of[int(v)] for v in groups])
    Z = torch.cat([torch.ones(X.size(0), 1), X], dim=1)
    eye = torch.eye(Z.size(1))
    eye[0, 0] = 0.0  # do not shrink the intercept
    out = torch.zeros_like(Y)
    for f in range(k):
        tr, te = fold != f, fold == f
        if not te.any():
            continue
        if not tr.any():
            out[te] = Y.mean(0)
            continue
        beta = torch.linalg.solve(Z[tr].T @ Z[tr] + lam * eye, Z[tr].T @ Y[tr])
        out[te] = Z[te] @ beta
    return out


def uniform_share(edge_index: torch.Tensor, treatment: torch.Tensor, n: int) -> torch.Tensor:
    """Unweighted share of each node's in-neighbours that are sponsored (0 if none)."""
    src, dst = edge_index
    num = torch.zeros(n).index_add_(0, dst, treatment[src].float())
    den = torch.zeros(n).index_add_(0, dst, torch.ones(src.size(0)))
    return torch.where(den > 0, num / den.clamp(min=1.0), torch.zeros(n))


class GAILR(nn.Module):
    """GAIL's backbone and relation-specific attention, with one effect slope
    per relation in place of the softmax beta + MLP head."""

    def __init__(self, hidden_channels: int = 16, heads: int = 2, relations=RELATIONS):
        super().__init__()
        self.relations = tuple(relations)
        base = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, hidden_channels=hidden_channels,
                         heads=heads, exposure_relations=self.relations)
        self.backbone = base.backbone
        self.exposure_module = base.exposure_module
        self._edge_index_dict = base._edge_index_dict
        self.slopes = nn.Parameter(torch.zeros(len(self.relations)))

    def exposures(self, data, treatments: list[torch.Tensor]) -> list[torch.Tensor]:
        """Per-relation exposure (N, R) for each treatment vector; one backbone pass."""
        emb = self.backbone(data)["creator"]
        eid = self._edge_index_dict(data)
        out = []
        for t in treatments:
            per = self.exposure_module.per_relation_exposure(emb, eid, t)
            out.append(torch.stack([per[r] for r in self.relations], dim=1))
        return out


def _gather(per_window: list[torch.Tensor], obs: Observations) -> torch.Tensor:
    stacked = torch.stack(per_window)            # (W, N, R)
    return stacked[obs.window, obs.node]          # (M, R)


def fit_gail_r(data, treatments: list[torch.Tensor], obs: Observations, placebo_weight: float = 30.0,
               shrink: float = 100.0, epochs: int = 200, lr: float = 1e-2, k_pcs: int = 16,
               ridge_lam: float = 1.0, seed: int = 0, uniform: bool = False) -> dict:
    """Fit GAIL-R and return the effect estimate.

    `uniform=True` replaces learned attention with uniform neighbour weights (no
    GNN pass), about 100x faster; used for the bootstrap, since the default
    shrinkage keeps learned attention close to uniform anyway.

    Returns a dict with `ate` (mean per-observation effect), `tau` (M,),
    `slopes` {relation: effect of going from 0% to 100% of that relation's
    neighbours sponsored}, and `placebo` (final penalty value)."""
    n = data["creator"].x.size(0)
    X = nuisance_features(data["creator"].x, k_pcs)[obs.node]
    m_hat = oof_ridge(X, obs.y, obs.node, lam=ridge_lam, seed=seed)
    U_win = [torch.stack([uniform_share(data["creator", r, "creator"].edge_index, t, n)
                          if ("creator", r, "creator") in data.edge_types else torch.zeros(n)
                          for r in RELATIONS], dim=1) for t in treatments]
    U = _gather(U_win, obs)
    e_hat = oof_ridge(X, U, obs.node, lam=ridge_lam, seed=seed)
    y_res = obs.y - m_hat
    has_pre = ~torch.isnan(obs.pre)

    torch.manual_seed(seed)
    model = GAILR()
    opt = torch.optim.Adam([model.slopes] if uniform else model.parameters(), lr=lr)

    def exposure():
        return U if uniform else _gather(model.exposures(data, treatments), obs)

    for _ in range(epochs):
        opt.zero_grad()
        E = exposure()
        loss = (y_res - ((E - e_hat) * model.slopes).sum(1)).pow(2).mean()
        if not uniform:
            loss = loss + shrink * (E - U).pow(2).mean()
        if placebo_weight > 0 and int(has_pre.sum()) >= 2:
            gap = (E * model.slopes).sum(1)
            loss = loss + placebo_weight * placebo_penalty(gap[has_pre], obs.pre[has_pre])
        loss.backward()
        opt.step()

    with torch.no_grad():
        E = exposure()
        tau = (E * model.slopes).sum(1)
        pen = (placebo_penalty(tau[has_pre], obs.pre[has_pre]) if int(has_pre.sum()) >= 2
               else torch.zeros(()))
    return {
        "ate": float(tau.mean()),
        "tau": tau,
        "slopes": dict(zip(model.relations, model.slopes.detach().tolist())),
        "placebo": float(pen),
    }


def cluster_bootstrap(data, treatments, obs: Observations, B: int = 200, seed: int = 0,
                      **fit_kw) -> dict:
    """Percentile interval from resampling CREATORS with replacement (all of a
    creator's observations move together), refitting each time with uniform
    attention (see `fit_gail_r`)."""
    g = torch.Generator().manual_seed(seed)
    creators = obs.node.unique()
    rows_of = {int(c): (obs.node == c).nonzero().squeeze(1) for c in creators}
    ates = []
    for b in range(B):
        pick = creators[torch.randint(0, len(creators), (len(creators),), generator=g)]
        idx = torch.cat([rows_of[int(c)] for c in pick])
        ates.append(fit_gail_r(data, treatments, obs.subset(idx), seed=seed + b + 1,
                               uniform=True, **fit_kw)["ate"])
    t = torch.tensor(ates)
    return {"lo": float(t.quantile(0.025)), "hi": float(t.quantile(0.975)), "se": float(t.std()), "B": B}
