"""Training loop boilerplate (GAIL working-doc Step 11: "Update the
Network" via gradient descent, repeated across historical partnerships).
No real training pairs exist yet (Weeks 11-13 gap analysis, GRAPH_SCHEMA.md)
so this is proven against dummy data with a synthetic, deterministic
target — enough to confirm the plumbing (gradients flow, loss decreases,
train/val split works) without claiming anything about real-world accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import torch
import torch.nn.functional as F
from torch_geometric.data import HeteroData

from ml.causal_regularization import has_sponsored_neighbor
from ml.gail_loss import GAILLossWeights, compute_gail_loss
from ml.gail_model import GAILModel


@dataclass
class TrainConfig:
    epochs: int = 100
    lr: float = 1e-2
    val_fraction: float = 0.2
    seed: int = 0
    loss_weights: GAILLossWeights = field(default_factory=GAILLossWeights)


def train_val_split(num_nodes: int, val_fraction: float, seed: int) -> tuple[torch.Tensor, torch.Tensor]:
    """Always leaves at least 1 node for training, even for tiny graphs —
    a single-node graph gets an empty val split rather than crashing.
    """
    gen = torch.Generator().manual_seed(seed)
    perm = torch.randperm(num_nodes, generator=gen)
    n_val = max(0, min(int(round(num_nodes * val_fraction)), num_nodes - 1))
    return perm[n_val:], perm[:n_val]


def _indices_to_mask(indices: torch.Tensor, num_nodes: int) -> torch.Tensor:
    mask = torch.zeros(num_nodes, dtype=torch.bool)
    mask[indices] = True
    return mask


def train(
    model: GAILModel, data: HeteroData, treatment: torch.Tensor, target: torch.Tensor, config: TrainConfig | None = None
) -> list[dict]:
    config = config or TrainConfig()
    num_creators = data["creator"].x.size(0)
    train_idx, val_idx = train_val_split(num_creators, config.val_fraction, config.seed)
    train_mask = _indices_to_mask(train_idx, num_creators)

    collab_edge_index = data["creator", "collaborates_with", "creator"].edge_index
    collab_edge_weight = data["creator", "collaborates_with", "creator"].edge_attr
    has_sponsored = has_sponsored_neighbor(collab_edge_index, treatment)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.lr)

    history = []
    for epoch in range(config.epochs):
        # Full graph goes through the model every step (standard
        # transductive GNN practice) -- only the supervised MSE term is
        # restricted to train_mask via compute_gail_loss's prediction_mask.
        # Structural terms (smoothness/consistency) need every node's real
        # position in collab_edge_index, which a pre-subsetted tensor loses.
        model.train()
        optimizer.zero_grad()
        prediction, exposure, propensity = model(data, treatment)

        loss, components = compute_gail_loss(
            prediction,
            target,
            propensity,
            collab_edge_index,
            collab_edge_weight,
            has_sponsored,
            config.loss_weights,
            prediction_mask=train_mask,
            treatment=treatment,
        )
        loss.backward()
        optimizer.step()

        val_loss = float("nan")
        if val_idx.numel() > 0:
            model.eval()
            with torch.no_grad():
                val_prediction, _, _ = model(data, treatment)
                val_loss = F.mse_loss(val_prediction[val_idx], target[val_idx]).item()

        history.append({"epoch": epoch, "val_loss": val_loss, **components})

    return history
