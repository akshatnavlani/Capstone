"""Wires the GAT backbone, exposure module, propensity model, and
prediction head into a single forward pass — the piece that was missing
between "individually tested components" and "something a training loop
can actually optimize."
"""

from __future__ import annotations

import torch
from torch import nn
from torch_geometric.data import HeteroData

from app.gail.causal_regularization import PropensityScoreModel
from app.gail.exposure import ExposureModule
from app.gail.model import SchemaSmokeTestGAT
from app.gail.spillover_head import SpilloverPredictionHead


class GAILModel(nn.Module):
    def __init__(self, creator_feature_dim: int, hidden_channels: int = 16, heads: int = 2):
        super().__init__()
        self.backbone = SchemaSmokeTestGAT(hidden_channels=hidden_channels, heads=heads)
        self.exposure_module = ExposureModule(in_channels=hidden_channels, hidden_channels=hidden_channels)
        self.propensity_model = PropensityScoreModel(in_dim=creator_feature_dim, hidden_dim=hidden_channels)
        self.prediction_head = SpilloverPredictionHead(embedding_dim=hidden_channels)

    def forward(
        self, data: HeteroData, treatment: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        embeddings = self.backbone(data)["creator"]
        collab_edge_index = data["creator", "collaborates_with", "creator"].edge_index
        exposure = self.exposure_module(embeddings, collab_edge_index, treatment)
        propensity = self.propensity_model(data["creator"].x)
        prediction = self.prediction_head(embeddings, exposure)
        return prediction, exposure, propensity
