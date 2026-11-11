"""Real-data check of GAIL-R on a field experiment with a KNOWN spillover.

Source: Cai, de Janvry and Sadoulet (2015), "Social Networks and the Decision
to Insure", AEJ: Applied 7(2). Replication data: Harvard Dataverse
doi:10.7910/DVN/CXDJM0 (download it yourself; it is not committed here).

The experiment. In 185 Chinese villages, households were randomly assigned to
one of four sessions about a new weather insurance: first or second round
(three days apart) x simple or intensive. The paper's spillover result
(Table 2, column 2): for second-round households with no other information,
going from 0% to 100% of named friends invited to a FIRST-round INTENSIVE
session raises take-up by 0.291 (SE 0.082), i.e. about +5.8 points per friend
at the average of ~5 friends.

How it maps onto GAIL-R.
  creator                  -> household
  collaborates_with edge   -> "this household named that one as a friend"
  sponsored collaborator   -> friend invited to a first-round intensive session
  neighbour's lift (y)     -> the second-round household's take-up (0/1)
  window                   -> village, so window fixed effects = village effects
  slope on collaborates_with is directly comparable with the paper's 0.291.

Friends who are not in the survey are kept as untreated nodes, so the share
of treated friends has the paper's denominator (all named friends).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from ml.gail_r import Observations
from ml.schema import CREATOR_FEATURE_DIM, CREATOR_METADATA_DIM, empty_hetero_data

PUBLISHED = {"slope": 0.2911852, "se": 0.0820022, "lo": 0.1292763, "hi": 0.4530942,
             "source": "Cai, de Janvry & Sadoulet (2015), Table 2 col. 2 (analysis.log line 964)"}

# Covariates of the paper's regression, in the 9 metadata slots GAIL-R's
# nuisance models read. `intensive` is the household's OWN session type.
COVARIATES = ["male", "age", "agpop", "ricearea_2010", "literacy", "intensive",
              "risk_averse", "disaster_prob", "network_obs"]
assert len(COVARIATES) == CREATOR_METADATA_DIM


@dataclass
class CaiData:
    data: object                 # HeteroData with creator.x and collaborates_with edges
    treatment: torch.Tensor      # (N,) 1 = invited to a first-round intensive session
    obs: Observations            # second-round, no-information households
    village: torch.Tensor        # (M,) village index of each observation
    address: torch.Tensor        # (M,) natural-village cluster of each observation (paper's SE)
    frame: pd.DataFrame          # the observation rows with covariates and exposure
    first_round: torch.Tensor    # (N,) bool, eligible for the first-round treatment
    node_village: torch.Tensor   # (N,) village of each node (-1 for friends outside the survey)
    first_round_share: torch.Tensor  # (M,) share of each observation's friends in the first round


def find_data_dir(root: str | Path) -> Path:
    root = Path(root)
    hits = list(root.rglob("0422survey.dta"))
    if not hits:
        raise SystemExit(f"0422survey.dta not found under {root}. Unzip the Dataverse download there.")
    return hits[0].parent


def load(root: str | Path) -> CaiData:
    d = find_data_dir(root)
    survey = pd.read_stata(d / "0422survey.dta", convert_categoricals=False)
    net = pd.read_stata(d / "0422allinforawnet.dta", convert_categoricals=False)
    # Same filter as rawnet.do: drop households that named nobody identifiable.
    net = net[~((net.network_missname == 1) & net.network_id.isna())].reset_index(drop=True)

    friends_out = net.groupby("id").size().rename("network_obs")
    survey = survey.merge(friends_out, left_on="id", right_index=True, how="left")

    # Nodes: every surveyed household, then one node per friend outside the survey
    # (each "99"/unknown name is its own node, since it may be anybody).
    ids = survey.id.astype("int64").tolist()
    index = {h: i for i, h in enumerate(ids)}
    src, dst = [], []
    extra = 0
    outside: dict[int, int] = {}
    for h, f in zip(net.id.astype("int64"), net.network_id):
        if h not in index:
            continue
        if pd.notna(f) and int(f) in index:
            s = index[int(f)]
        elif pd.notna(f) and int(f) != 99:
            if int(f) not in outside:
                outside[int(f)] = len(ids) + extra
                extra += 1
            s = outside[int(f)]
        else:
            s = len(ids) + extra
            extra += 1
        src.append(s)
        dst.append(index[h])
    n = len(ids) + extra

    treat = torch.zeros(n)
    treat[: len(ids)] = torch.tensor(((survey.delay == 0) & (survey.intensive == 1)).astype(float).values,
                                     dtype=torch.float32)
    # A few friends are missing from the survey file but their session is known
    # from the network file (as rawnet.do uses it); keep that assignment.
    first_round = torch.zeros(n, dtype=torch.bool)
    first_round[: len(ids)] = torch.tensor((survey.delay == 0).values)
    known = net[net.network_id.notna() & net.delay.notna()]
    for f, dl, it in zip(known.network_id.astype("int64"), known.delay, known.intensive):
        if f in outside:
            treat[outside[f]] = float(dl == 0 and it == 1)
            first_round[outside[f]] = bool(dl == 0)
    villages = {v: i for i, v in enumerate(sorted(survey.village.dropna().unique()))}
    node_village = torch.full((n,), -1, dtype=torch.long)
    node_village[: len(ids)] = torch.tensor([villages.get(v, -1) for v in survey.village])

    # Features: content block zero, the paper's covariates (standardised) in the metadata tail.
    meta = survey[COVARIATES].astype(float)
    ok = meta.notna().all(axis=1)
    z = ((meta - meta[ok].mean()) / meta[ok].std().replace(0, 1)).fillna(0.0).values
    x = torch.zeros(n, CREATOR_FEATURE_DIM)
    x[: len(ids), -CREATOR_METADATA_DIM:] = torch.tensor(z, dtype=torch.float32)

    data = empty_hetero_data()
    data["creator"].x = x
    data["brand"].x = torch.zeros(1, empty_hetero_data()["brand"].x.size(1))
    data["creator", "collaborates_with", "creator"].edge_index = torch.tensor([src, dst], dtype=torch.long)
    data["creator", "collaborates_with", "creator"].edge_attr = torch.ones(len(src), 1)

    # Observations: the paper's sample (delay == 1 & info_none == 1, complete cases).
    keep = (survey.delay == 1) & (survey.info_none == 1) & survey.takeup_survey.notna() & ok \
        & survey.network_obs.notna()
    rows = survey[keep].copy()
    node = torch.tensor([index[int(h)] for h in rows.id])
    vil = torch.tensor([villages[v] for v in rows.village])
    addr_codes = {a: i for i, a in enumerate(sorted(rows.address.unique()))}
    obs = Observations(node=node, window=vil, y=torch.tensor(rows.takeup_survey.values, dtype=torch.float32),
                       pre=torch.full((len(rows),), float("nan")))
    from ml.gail_r import uniform_share
    rows["exposure"] = uniform_share(data["creator", "collaborates_with", "creator"].edge_index,
                                     treat, n)[node].numpy()
    fr_share = uniform_share(data["creator", "collaborates_with", "creator"].edge_index,
                             first_round.float(), n)[node]
    return CaiData(data, treat, obs, vil, torch.tensor([addr_codes[a] for a in rows.address]), rows,
                   first_round, node_village, fr_share)


def ols_cluster(y: np.ndarray, X: np.ndarray, clusters: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OLS with Stata-style cluster-robust standard errors."""
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    u = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    for c in np.unique(clusters):
        s = X[clusters == c].T @ u[clusters == c]
        meat += np.outer(s, s)
    n, k, g = len(y), X.shape[1], len(np.unique(clusters))
    V = XtX_inv @ meat @ XtX_inv * (g / (g - 1)) * ((n - 1) / (n - k))
    return beta, np.sqrt(np.clip(np.diag(V), 0, None))


def replicate_paper(cd: CaiData) -> dict:
    """The paper's Table 2 col. 2 regression, rebuilt from our graph: take-up on
    the treated-friend share, covariates, friend-count dummies, village effects."""
    f = cd.frame
    cols = [np.ones(len(f)), f.exposure.values] + [f[c].astype(float).values for c in COVARIATES[:-1]]
    cols += [(f.network_obs == k).astype(float).values for k in range(1, 6)]
    vd = pd.get_dummies(f.village, drop_first=True).astype(float).values
    X = np.column_stack(cols + [vd])
    beta, se = ols_cluster(f.takeup_survey.values.astype(float), X, f.address.values)
    return {"slope": float(beta[1]), "se": float(se[1]), "n": int(len(f))}


def random_treatment(cd: CaiData, seed: int) -> torch.Tensor:
    """Pure-noise assignment: a random 54% (the real rate) of first-round
    households 'get' the intensive session, ignoring villages. It carries no
    information about take-up, so GAIL-R should average ~0 on it."""
    g = torch.Generator().manual_seed(seed)
    rate = float(cd.treatment[cd.first_round].mean())
    t = torch.zeros_like(cd.treatment)
    t[cd.first_round] = (torch.rand(int(cd.first_round.sum()), generator=g) < rate).float()
    return t


def permute_treatment(cd: CaiData, seed: int) -> torch.Tensor:
    """Re-draw who got a first-round intensive session, within each village and
    keeping each village's count: the experiment's own randomisation, rerun.

    For randomisation inference only. These fake assignments keep each village's
    share of intensive sessions, so a household's fake exposure still tracks
    (village share x its number of first-round friends), part of the real
    exposure. If spillover is real they therefore average ABOVE zero; what
    matters is where the real estimate falls in their distribution (p-value)."""
    g = torch.Generator().manual_seed(seed)
    t = cd.treatment.clone()
    for v in cd.node_village.unique():
        # v = -1 groups the few first-round friends missing from the survey (no village)
        idx = ((cd.node_village == v) & cd.first_round).nonzero().squeeze(1)
        if idx.numel() > 1:
            t[idx] = t[idx][torch.randperm(idx.numel(), generator=g)]
    return t
