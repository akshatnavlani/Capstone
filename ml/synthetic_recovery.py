"""Synthetic ground-truth recovery: does GAIL learn the right thing when we
control what "right" is?

WHY THIS EXISTS. Every real-data number this project can produce rests on ~10
effective labelled nodes. At that size, "our MSE is X" says almost nothing —
the honest answer to "how do you know the model works?" cannot come from the
real data alone. So we generate data where the true transmission weights and
the true spillover effect are KNOWN by construction, and ask whether training
recovers them. The real-data results are then reported with honest uncertainty
alongside a demonstration that the estimator recovers truth when truth exists.

WHAT IS PLANTED. The generator builds a graph where:

  * a per-node `confounder` drives BOTH the chance of being sponsored and the
    baseline outcome — the selection problem brands create by favouring
    already-popular creators, which is what the propensity model must undo;
  * the true per-edge transmission weight is a function of endpoint feature
    SIMILARITY, so a GAT attending over those features can in principle
    recover it (planting weights unrelated to features would make the task
    impossible rather than merely hard, and would prove nothing);
  * observed spillover is `baseline(confounder) + effect * sum_j w_true_ij * T_j`
    plus noise.

WHAT IS MEASURED. Two things, deliberately separated:

  `transmission_corr` -- Spearman correlation between learned attention and
      the planted per-edge weights, computed WITHIN each destination node's
      in-edges and then averaged (degree-weighted).

      The within-neighbourhood scoping is essential, not a detail. Attention is
      softmax-normalised per destination: a node with one in-edge gets alpha=1.0
      however weak that edge truly is, and a node with ten in-edges has alphas
      summing to 1 however strong its edges are. A correlation computed GLOBALLY
      across all edges is therefore dominated by node degree and would score near
      zero even for a perfectly trained model -- it measures the normalisation,
      not the model. Only ranking within one node's own neighbourhood is
      comparable, and that is also exactly what the explainability claim needs
      ("which of MY relationships drove MY spillover").

  `ceiling` (via `representational_ceiling`) -- the same metric after
      supervising attention DIRECTLY on the planted weights. Without it, a low
      score is unattributable: it could mean the task loss gives attention no
      pressure, or that the architecture cannot express those weights at all.
      Measured ceiling on the default world is ~+0.33, not ~+0.9: the backbone
      smooths neighbouring nodes toward each other, which washes out much of the
      pairwise distinction attention would need. Score task-loss recovery
      against that ceiling, never against 1.0.

  `effect_error` -- absolute error of the recovered spillover effect against
      the planted one, via the doubly robust estimator.

THE COMPARISON THIS ENABLES. `compare_supervision` trains the same
architecture twice, differing only in `dr_mode`, and reports both metrics for
each. That is the ablation behind the causal-supervision claim: if attention
supervised by the selection-corrected target recovers the planted weights no
better than plain MSE, the claim has no evidence and should be dropped. A null
result here is a real finding, not a failure of the harness.

SCOPE. This is a controlled demonstration, not a benchmark. It shows the
estimator can recover truth under its own assumptions; it does not show the
assumptions hold on real influencer data.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from ml.causal_regularization import doubly_robust_effect, has_sponsored_neighbor
from ml.gail_loss import GAILLossWeights, compute_gail_loss
from ml.gail_model import GAILModel
from ml.schema import CREATOR_FEATURE_DIM, empty_hetero_data


@dataclass
class SyntheticWorld:
    """A graph with known transmission weights and a known spillover effect."""

    data: object
    treatment: torch.Tensor
    target: torch.Tensor
    true_edge_weight: torch.Tensor
    edge_index: torch.Tensor
    true_effect: float
    confounder: torch.Tensor


def make_synthetic_world(
    num_creators: int = 120,
    avg_degree: int = 4,
    true_effect: float = 3.0,
    noise: float = 0.05,
    seed: int = 0,
) -> SyntheticWorld:
    """Build a world where transmission strength is driven by feature similarity."""
    g = torch.Generator().manual_seed(seed)

    # A low-dimensional latent "niche" drives both features and transmission:
    # creators in the same niche transmit strongly, across niches weakly. This
    # is the structure the attention mechanism is supposed to discover.
    niche = torch.randn(num_creators, 4, generator=g)
    features = torch.zeros(num_creators, CREATOR_FEATURE_DIM)
    features[:, :4] = niche
    features[:, 4:8] = torch.randn(num_creators, 4, generator=g) * 0.1  # distractors

    num_edges = num_creators * avg_degree
    src = torch.randint(0, num_creators, (num_edges,), generator=g)
    dst = torch.randint(0, num_creators, (num_edges,), generator=g)
    keep = src != dst
    src, dst = src[keep], dst[keep]
    edge_index = torch.stack([src, dst])

    # True transmission: cosine similarity of niches, squashed to (0, 1).
    sim = torch.nn.functional.cosine_similarity(niche[src], niche[dst], dim=1)
    true_edge_weight = torch.sigmoid(3.0 * sim)

    # Confounding: popular creators are likelier to be sponsored AND have
    # higher baseline engagement. Ignoring this inflates the apparent effect.
    confounder = torch.rand(num_creators, generator=g)
    true_propensity = 0.15 + 0.7 * confounder
    treatment = (torch.rand(num_creators, generator=g) < true_propensity).float()

    true_exposure = torch.zeros(num_creators)
    true_exposure.index_add_(0, dst, true_edge_weight * treatment[src])

    target = (
        2.0 * confounder
        + true_effect * true_exposure
        + torch.randn(num_creators, generator=g) * noise
    )

    data = empty_hetero_data()
    data["creator"].x = features
    data["brand"].x = torch.zeros(1, data["brand"].x.size(1))
    data["creator", "collaborates_with", "creator"].edge_index = edge_index
    data["creator", "collaborates_with", "creator"].edge_attr = true_edge_weight.unsqueeze(1)

    return SyntheticWorld(
        data=data,
        treatment=treatment,
        target=target,
        true_edge_weight=true_edge_weight,
        edge_index=edge_index,
        true_effect=true_effect,
        confounder=confounder,
    )


def within_neighbourhood_corr(
    learned: torch.Tensor,
    truth: torch.Tensor,
    dst: torch.Tensor,
    min_degree: int = 3,
) -> tuple[float, int]:
    """Degree-weighted mean Spearman within each destination's in-edges.

    See the module docstring for why a global correlation is the wrong metric
    here. Nodes with fewer than `min_degree` in-edges are skipped: ranking two
    items is not informative, and ranking one is vacuous.

    Returns (correlation, number of nodes scored).
    """
    corrs, weights = [], []
    for node in dst.unique():
        mask = dst == node
        degree = int(mask.sum())
        if degree < min_degree:
            continue
        corrs.append(_spearman(learned[mask], truth[mask]))
        weights.append(degree)
    if not corrs:
        return float("nan"), 0
    c = torch.tensor(corrs)
    w = torch.tensor(weights, dtype=torch.float)
    return float((c * w).sum() / w.sum()), len(corrs)


def representational_ceiling(
    world: "SyntheticWorld", hidden_channels: int = 64, epochs: int = 600, seed: int = 0
) -> float:
    """Best within-neighbourhood recovery achievable by supervising attention
    DIRECTLY on the planted weights.

    The positive control for this harness. A low task-loss score only means
    something once this number is known: it separates "the loss gives attention
    no pressure" from "the architecture cannot represent this".
    """
    torch.manual_seed(seed)
    model = GAILModel(
        creator_feature_dim=CREATOR_FEATURE_DIM,
        hidden_channels=hidden_channels,
        exposure_relations=("collaborates_with",),
    )
    conv = model.exposure_module.attn_convs["collaborates_with"]
    opt = torch.optim.Adam(
        list(model.backbone.parameters()) + list(conv.parameters()), lr=1e-2
    )
    dst = world.edge_index[1]

    # Target: per-destination softmax of the planted weights, i.e. the closest
    # thing to the truth that a softmax-normalised alpha is able to express.
    target = torch.zeros_like(world.true_edge_weight)
    for node in dst.unique():
        mask = dst == node
        target[mask] = torch.softmax(world.true_edge_weight[mask] * 4.0, dim=0)

    for _ in range(epochs):
        opt.zero_grad()
        emb = model.backbone(world.data)["creator"]
        _, (_, alpha) = conv(emb, world.edge_index, return_attention_weights=True)
        alpha = alpha.mean(dim=1) if alpha.dim() > 1 else alpha
        ((alpha - target) ** 2).mean().backward()
        opt.step()

    with torch.no_grad():
        emb = model.backbone(world.data)["creator"]
        _, (_, alpha) = conv(emb, world.edge_index, return_attention_weights=True)
        alpha = alpha.mean(dim=1) if alpha.dim() > 1 else alpha
    return within_neighbourhood_corr(alpha, world.true_edge_weight, dst)[0]


def _spearman(a: torch.Tensor, b: torch.Tensor) -> float:
    """Rank correlation over whatever subset is passed in."""
    ra = a.argsort().argsort().float()
    rb = b.argsort().argsort().float()
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denom = ra.norm() * rb.norm()
    return float((ra @ rb) / denom) if denom > 0 else 0.0


def _learned_edge_weights(model: GAILModel, world: SyntheticWorld) -> torch.Tensor:
    """Attention coefficients for the planted edges, in planted-edge order."""
    embeddings = model.backbone(world.data)["creator"]
    conv = model.exposure_module.attn_convs["collaborates_with"]
    _, (out_edge_index, alpha) = conv(
        embeddings, world.edge_index, return_attention_weights=True
    )
    alpha = alpha.mean(dim=1) if alpha.dim() > 1 else alpha
    # GATConv may reorder edges; align by (src, dst) so the comparison is
    # against the right planted weight rather than a shuffled one.
    if out_edge_index.shape == world.edge_index.shape and torch.equal(
        out_edge_index, world.edge_index
    ):
        return alpha.detach()
    key_out = out_edge_index[0] * (world.data["creator"].num_nodes + 1) + out_edge_index[1]
    key_true = world.edge_index[0] * (world.data["creator"].num_nodes + 1) + world.edge_index[1]
    order = torch.argsort(key_out)
    pos = torch.searchsorted(key_out[order], key_true)
    pos = pos.clamp(max=order.numel() - 1)
    return alpha.detach()[order[pos]]


def train_and_score(
    world: SyntheticWorld,
    dr_mode: str = "aipw",
    epochs: int = 300,
    lr: float = 1e-2,
    seed: int = 0,
) -> dict[str, float]:
    """Train on the synthetic world and score recovery of the planted truth."""
    torch.manual_seed(seed)
    model = GAILModel(
        creator_feature_dim=CREATOR_FEATURE_DIM,
        hidden_channels=16,
        exposure_relations=("collaborates_with",),
    )
    opt = torch.optim.Adam(model.parameters(), lr=lr)

    edge_weight = world.data["creator", "collaborates_with", "creator"].edge_attr.squeeze(-1)
    nbr_mask = has_sponsored_neighbor(world.edge_index, world.treatment)
    nbr_indicator = nbr_mask.float()
    weights = GAILLossWeights(prediction=1.0, overlap=0.1, smoothness=0.01, consistency=0.1)

    for _ in range(epochs):
        opt.zero_grad()
        prediction, _, propensity = model(world.data, world.treatment)
        loss, _ = compute_gail_loss(
            prediction,
            world.target,
            propensity,
            world.edge_index,
            edge_weight,
            nbr_mask,
            weights,
            treatment=nbr_indicator,
            dr_mode=dr_mode,
        )
        loss.backward()
        opt.step()

    model.eval()
    with torch.no_grad():
        prediction, _, propensity = model(world.data, world.treatment)
        mu_unexposed = model.predict_unexposed(world.data)
        effect = doubly_robust_effect(
            prediction, mu_unexposed, world.target, nbr_indicator, propensity
        ).mean()

    learned = _learned_edge_weights(model, world)
    corr, nodes_scored = within_neighbourhood_corr(
        learned, world.true_edge_weight, world.edge_index[1]
    )
    return {
        "transmission_corr": corr,
        "nodes_scored": nodes_scored,
        "effect_error": abs(float(effect) - world.true_effect),
        "final_loss": float(loss.detach()),
    }


def compare_supervision(
    world: SyntheticWorld | None = None, epochs: int = 300, seed: int = 0
) -> dict[str, dict[str, float]]:
    """Train the same architecture under each supervision mode and score both.

    This is the causal-supervision ablation. Identical seeds and identical
    architecture; only `dr_mode` differs, so any gap is attributable to the
    supervision signal rather than initialisation.
    """
    world = world or make_synthetic_world()
    return {
        mode: train_and_score(world, dr_mode=mode, epochs=epochs, seed=seed)
        for mode in ("ipw", "aipw")
    }


def main() -> None:
    """Run the full recovery report: ceiling first, then both supervision modes.

    The ceiling is printed first on purpose. A task-loss score only means
    something relative to what the architecture can express at all, so reading
    the supervision rows without it invites the wrong conclusion.
    """
    import argparse

    ap = argparse.ArgumentParser(description="GAIL synthetic ground-truth recovery")
    ap.add_argument("--creators", type=int, default=120)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skip-ceiling", action="store_true",
                    help="skip the positive control (faster, but scores become unreadable)")
    args = ap.parse_args()

    line = "-" * 64
    print(f"\n{line}\nGAIL synthetic recovery\n{line}")

    world = make_synthetic_world(num_creators=args.creators, seed=args.seed)
    print(f"\nPlanted world: {world.data['creator'].num_nodes} creators, "
          f"{world.edge_index.size(1)} edges, "
          f"{int(world.treatment.sum())} sponsored, true effect {world.true_effect}")

    ceiling = None
    if not args.skip_ceiling:
        print("\nMeasuring representational ceiling (supervising attention directly)...")
        ceiling = representational_ceiling(world, seed=args.seed)
        print(f"  ceiling: {ceiling:+.3f}")
        print("  = best within-neighbourhood recovery this architecture can reach.")

    print(f"\nTraining under each supervision mode ({args.epochs} epochs each)...")
    results = compare_supervision(world=world, epochs=args.epochs, seed=args.seed)

    print(f"\n{line}\nRESULT\n{line}")
    header = f"\n{'mode':6} {'attn corr':>10} {'% of ceiling':>13} {'effect err':>11} {'nodes':>6}"
    print(header)
    for mode, m in results.items():
        pct = f"{100 * m['transmission_corr'] / ceiling:>12.1f}%" if ceiling else f"{'n/a':>13}"
        print(f"{mode:6} {m['transmission_corr']:>+10.3f} {pct} "
              f"{m['effect_error']:>11.3f} {m['nodes_scored']:>6}")

    print("\n  attn corr   -- does attention rank each creator's own neighbours correctly?")
    print("  effect err  -- absolute error on the planted spillover effect.")
    if ceiling is not None:
        print(f"\n  Read scores against the ceiling ({ceiling:+.3f}), never against 1.0.")
    print()


if __name__ == "__main__":
    main()