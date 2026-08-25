"""Prototype custom MessagePassing layer with edge-weight support (Weeks 5-6
de-risking work, GRAPH_SCHEMA.md "Why GAT over GraphSAGE").

`torch_geometric.nn.SAGEConv` has no edge_attr/edge_dim support at all
(confirmed in Weeks 3-4 — see GRAPH_SCHEMA.md). This is a small prototype
proving a GraphSAGE-style layer (self-transform + mean-aggregated neighbor
transform) CAN incorporate a scalar edge weight, by scaling neighbor
messages before mean aggregation — the standard way to add edge weights to
mean-aggregation GNNs. NOT production-ready (no bias term choices, no
normalization options, not benchmarked for accuracy) — the goal here is
only to confirm the approach works structurally, per the user's Weeks 5-6
ask, not to do Weeks 11-13's real implementation early.
"""

from __future__ import annotations

import torch
from torch import nn
from torch_geometric.nn import MessagePassing


class WeightedSAGEConv(MessagePassing):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__(aggr="mean")
        self.lin_self = nn.Linear(in_channels, out_channels)
        self.lin_neigh = nn.Linear(in_channels, out_channels)

    def forward(
        self, x: torch.Tensor, edge_index: torch.Tensor, edge_weight: torch.Tensor
    ) -> torch.Tensor:
        aggregated = self.propagate(edge_index, x=x, edge_weight=edge_weight, size=(x.size(0), x.size(0)))
        return self.lin_self(x) + self.lin_neigh(aggregated)

    def message(self, x_j: torch.Tensor, edge_weight: torch.Tensor) -> torch.Tensor:
        weight = edge_weight.view(-1, 1) if edge_weight.dim() == 1 else edge_weight
        return x_j * weight
