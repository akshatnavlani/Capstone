"""Semi-synthetic benchmark: the REAL creator graph, outcomes with a KNOWN effect.

WHY. Real-data estimates rest on 11 exposed observations from 6 creators, so
they cannot show that one estimator beats another. Here the graph and the
creator features are the real ones (read from models/gail_checkpoint.pt), but
treatment and outcomes are simulated, so the true spillover of every creator is
known and every method can be scored against it. This is the standard
evaluation for causal estimators on networks.

WHAT IS PLANTED (per replicate):
  * confounder c = the creator's (normalised) log follower count -- bigger
    creators are likelier to be sponsored AND have bigger engagement changes;
  * own sponsorship T ~ Bernoulli(0.1 + 0.5 * sigmoid(1.5 c));
  * spillover travels ONLY through collaborates_with, with a per-edge strength
    set by content similarity of the two creators (so attention can learn it);
    co_occurs_with carries no effect (true beta_co = 0);
  * outcome lift  y = c + category effect + EFFECT * e_collab + trend + noise,
    where e_collab = similarity-weighted share of a creator's collaborators
    that are sponsored;
  * scenario "pretrend": a pre-existing trend equal to TREND * (share of
    co-mentioned creators sponsored) appears in BOTH the pre-period lift and the
    outcome lift. It is not caused by any sponsorship, so a method that turns it
    into "spillover" is biased. This is the case the placebo penalty targets.

ESTIMAND. Mean over creators of the true effect of their observed exposure,
EFFECT * e_collab (0 for creators with no sponsored collaborator).

METRICS. Absolute error of the estimated mean effect, PEHE (root mean squared
error of the per-creator effect), and what each GAIL variant learned for
co_occurs_with (truth 0): the softmax share beta for GAIL v1, the effect slope
for GAIL-R.

SCOPE. A controlled test under stated assumptions; it does not show those
assumptions hold for real influencer data. Report it as such.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import torch

from ml.causal_regularization import doubly_robust_effect, has_sponsored_neighbor
from ml.gail_loss import GAILLossWeights, compute_gail_loss
from ml.gail_model import GAILModel
from ml.placebo import placebo_penalty
from ml.schema import CREATOR_FEATURE_DIM, CREATOR_METADATA_DIM, empty_hetero_data

EFFECT = 1.0
NOISE = 0.5
TREND = 1.0


@dataclass
class Graph:
    x: torch.Tensor          # normalised creator features (N, CREATOR_FEATURE_DIM)
    collab: torch.Tensor     # (2, E) directed
    coocc: torch.Tensor      # (2, E) directed
    brand_x: torch.Tensor


@dataclass
class World:
    data: object
    treatment: torch.Tensor     # own sponsorship (N,)
    interference: torch.Tensor  # 1 if any collab/co-occurs neighbour is sponsored
    y: torch.Tensor             # outcome lift
    y_pre: torch.Tensor         # pre-period (placebo) lift
    true_tau: torch.Tensor      # per-creator true effect of observed exposure

    @property
    def true_ate(self) -> float:
        return float(self.true_tau.mean())


def load_graph(checkpoint: Path) -> Graph:
    t = torch.load(checkpoint, map_location="cpu", weights_only=False)["tensors"]
    return Graph(t["creator_x_norm"].float(), t["collab_edge_index"], t["coocc_edge_index"],
                 t["brand_x"].float())


def fake_graph(n: int = 390, n_collab: int = 177, n_coocc: int = 708, seed: int = 0) -> Graph:
    """Stand-in with the real graph's size and sparsity, for tests and dry runs."""
    g = torch.Generator().manual_seed(seed)
    x = torch.randn(n, CREATOR_FEATURE_DIM, generator=g)

    def undirected(m):
        s = torch.randint(0, n, (m,), generator=g)
        d = torch.randint(0, n, (m,), generator=g)
        keep = s != d
        s, d = s[keep], d[keep]
        return torch.cat([torch.stack([s, d]), torch.stack([d, s])], dim=1)

    from ml.schema import empty_hetero_data as _e
    brand_dim = _e()["brand"].x.size(1)
    return Graph(x, undirected(n_collab), undirected(n_coocc), torch.zeros(1, brand_dim))


def _share_treated(edge_index, weight, treatment, n):
    """Weighted share of each node's in-neighbours that are treated (0 if none)."""
    src, dst = edge_index
    num = torch.zeros(n).index_add_(0, dst, weight * treatment[src])
    den = torch.zeros(n).index_add_(0, dst, weight)
    return torch.where(den > 0, num / den.clamp(min=1e-12), torch.zeros(n))


def make_world(graph: Graph, scenario: str = "clean", seed: int = 0) -> World:
    g = torch.Generator().manual_seed(seed)
    x, n = graph.x, graph.x.size(0)
    meta = x[:, -CREATOR_METADATA_DIM:]
    c = meta[:, 0]                                   # log follower count (normalised)
    cat_effect = meta[:, 3:] @ (torch.randn(meta.size(1) - 3, generator=g) * 0.3)

    # Per-edge transmission strength from content similarity (fixed projection).
    proj = torch.randn(x.size(1) - CREATOR_METADATA_DIM, 4, generator=torch.Generator().manual_seed(1234))
    niche = x[:, :-CREATOR_METADATA_DIM] @ proj
    s, d = graph.collab
    w = torch.sigmoid(3.0 * torch.nn.functional.cosine_similarity(niche[s], niche[d], dim=1))

    treatment = (torch.rand(n, generator=g) < 0.1 + 0.5 * torch.sigmoid(1.5 * c)).float()
    e_collab = _share_treated(graph.collab, w, treatment, n)
    e_coocc = _share_treated(graph.coocc, torch.ones(graph.coocc.size(1)), treatment, n)
    trend = TREND * e_coocc if scenario == "pretrend" else torch.zeros(n)

    true_tau = EFFECT * e_collab
    y = c + cat_effect + true_tau + trend + NOISE * torch.randn(n, generator=g)
    y_pre = trend + NOISE * torch.randn(n, generator=g)

    data = empty_hetero_data()
    data["creator"].x = x
    data["brand"].x = graph.brand_x
    data["creator", "collaborates_with", "creator"].edge_index = graph.collab
    data["creator", "collaborates_with", "creator"].edge_attr = torch.ones(graph.collab.size(1), 1)
    data["creator", "co_occurs_with", "creator"].edge_index = graph.coocc
    data["creator", "co_occurs_with", "creator"].edge_attr = torch.ones(graph.coocc.size(1), 1)
    interference = has_sponsored_neighbor(torch.cat([graph.collab, graph.coocc], dim=1), treatment).float()
    return World(data, treatment, interference, y, y_pre, true_tau)


# --- Baselines ----------------------------------------------------------------


def naive_difference(world: World) -> dict:
    """Exposed minus unexposed mean outcome, no adjustment."""
    t = world.interference.bool()
    att = float(world.y[t].mean() - world.y[~t].mean())
    tau = torch.where(t, torch.full_like(world.y, att), torch.zeros_like(world.y))
    return {"ate": float(tau.mean()), "tau": tau}


def dr_without_graph(world: World) -> dict:
    """Doubly robust ATT with a binary 'has a sponsored neighbour' treatment:
    ridge outcome model + logistic propensity on creator metadata. Knows nothing
    about which link or relation carried the effect."""
    meta = world.data["creator"].x[:, -CREATOR_METADATA_DIM:]
    t, y = world.interference, world.y
    z = torch.cat([torch.ones(len(y), 1), meta], dim=1)
    ctrl = t == 0
    beta = torch.linalg.solve(z[ctrl].T @ z[ctrl] + 1e-2 * torch.eye(z.size(1)), z[ctrl].T @ y[ctrl])
    mu0 = z @ beta
    lr = torch.zeros(z.size(1), requires_grad=True)
    opt = torch.optim.LBFGS([lr], max_iter=200)

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(z @ lr, t) + 1e-3 * lr.pow(2).sum()
        loss.backward()
        return loss

    opt.step(closure)
    p = torch.sigmoid(z @ lr.detach()).clamp(0.05, 0.95)
    resid = y - mu0
    att = float((t * resid).sum() - ((1 - t) * p / (1 - p) * resid).sum()) / float(t.sum().clamp(min=1))
    tau = torch.where(t.bool(), torch.full_like(y, att), torch.zeros_like(y))
    return {"ate": float(tau.mean()), "tau": tau}


# --- GAIL variants ------------------------------------------------------------


def train_gail(world: World, relations=("collaborates_with", "co_occurs_with"), causal: bool = True,
               placebo_weight: float = 0.0, consistency: float = 0.1, epochs: int = 100,
               seed: int = 0) -> dict:
    """Train GAIL the way scripts/train_prod_model.py does, on one window.

    causal=False is the predictive ablation (plain MSE, effect read off the model
    with no AIPW correction) -- the stand-in for engagement-prediction GNNs.
    """
    torch.manual_seed(seed)
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, hidden_channels=16, heads=2,
                      exposure_relations=tuple(relations), propensity_metadata_only=True)
    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    data = world.data
    collab = data["creator", "collaborates_with", "creator"]
    weights = GAILLossWeights(consistency=consistency)
    mask = world.interference.bool()
    for _ in range(epochs):
        opt.zero_grad()
        pred, _, prop = model(data, world.treatment)
        loss, _ = compute_gail_loss(pred, world.y, prop, collab.edge_index, collab.edge_attr, mask, weights,
                                    treatment=world.interference if causal else None, dr_mode="aipw")
        if placebo_weight > 0:
            loss = loss + placebo_weight * placebo_penalty(pred - model.predict_unexposed(data), world.y_pre)
        loss.backward()
        opt.step()
    model.eval()
    with torch.no_grad():
        pred, _, prop = model(data, world.treatment)
        mu0 = model.predict_unexposed(data)
        gap = pred - mu0
        ate = (doubly_robust_effect(pred, mu0, world.y, world.interference, prop).mean()
               if causal else gap.mean())
    shares = model.transmission_shares()
    return {"ate": float(ate), "tau": gap, "beta_co": shares.get("co_occurs_with")}


def gail_r(world: World, seed: int, placebo_weight: float) -> dict:
    from ml.gail_r import Observations, fit_gail_r
    n = len(world.y)
    obs = Observations(torch.arange(n), torch.zeros(n, dtype=torch.long), world.y, world.y_pre)
    out = fit_gail_r(world.data, [world.treatment], obs, placebo_weight=placebo_weight, seed=seed)
    return {"ate": out["ate"], "tau": out["tau"], "beta_co": out["slopes"]["co_occurs_with"]}


METHODS = {
    "Naive difference": lambda w, s: naive_difference(w),
    "DR, no graph": lambda w, s: dr_without_graph(w),
    "GNN predictor (no causal training)": lambda w, s: train_gail(w, causal=False, seed=s),
    "GAIL v1 (current)": lambda w, s: train_gail(w, seed=s),
    "GAIL v1 + placebo": lambda w, s: train_gail(w, placebo_weight=1.0, seed=s),
    "GAIL-R": lambda w, s: gail_r(w, s, placebo_weight=0.0),
    "GAIL-R + placebo": lambda w, s: gail_r(w, s, placebo_weight=30.0),
}


def score(world: World, out: dict) -> dict:
    return {
        "ate_error": abs(out["ate"] - world.true_ate),
        "pehe": float((out["tau"] - world.true_tau).pow(2).mean().sqrt()),
        "beta_co": out.get("beta_co"),
    }


def run(graph: Graph, reps: int = 10, scenarios=("clean", "pretrend"), methods=None) -> dict:
    methods = methods or list(METHODS)
    results: dict = {}
    for scen in scenarios:
        results[scen] = {m: [] for m in methods}
        results[scen]["_true_ate"] = []
        for r in range(reps):
            world = make_world(graph, scen, seed=r)
            results[scen]["_true_ate"].append(world.true_ate)
            for m in methods:
                results[scen][m].append(score(world, METHODS[m](world, r)))
    return results


def summarise(results: dict) -> str:
    def ms(vals):
        t = torch.tensor(vals, dtype=torch.float64)
        return f"{t.mean():.3f} ± {t.std(unbiased=True) if len(vals) > 1 else 0:.3f}"

    lines = []
    for scen, by_method in results.items():
        true = by_method["_true_ate"]
        lines.append(f"\nScenario: {scen}   (true mean effect {ms(true)}, {len(true)} replicates)")
        lines.append(f"  {'method':38} {'|ATE error|':>16} {'PEHE':>16} {'co-mention (true 0)':>18}")
        for m, rows in by_method.items():
            if m.startswith("_"):
                continue
            b = [r["beta_co"] for r in rows if r["beta_co"] is not None]
            lines.append(f"  {m:38} {ms([r['ate_error'] for r in rows]):>16} "
                         f"{ms([r['pehe'] for r in rows]):>16} {ms(b) if b else '-':>18}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="GAIL semi-synthetic benchmark")
    ap.add_argument("--checkpoint", default="models/gail_checkpoint.pt",
                    help="real graph source; use --fake to run without one")
    ap.add_argument("--fake", action="store_true", help="random graph of the real graph's size")
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--out", default="models/semi_synthetic_results.json")
    args = ap.parse_args()

    graph = fake_graph() if args.fake else load_graph(Path(args.checkpoint))
    print(f"Graph: {graph.x.size(0)} creators, {graph.collab.size(1)} collab and "
          f"{graph.coocc.size(1)} co-occurs directed edges ({'fake' if args.fake else args.checkpoint})")
    results = run(graph, reps=args.reps)
    print(summarise(results))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2))
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
