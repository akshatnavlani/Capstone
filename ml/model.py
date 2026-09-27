"""Smoke-test GAT model for schema validation.

NOT the final GAIL model (that lands in Weeks 11-13 per PROJECT_PLAN.md
Section 6). This just confirms the heterogeneous schema in schema.py
supports a basic attention-based forward pass with sane output shapes,
using PyG's off-the-shelf HeteroConv + GATConv.

Swapping this backbone for GraphSAGE later is NOT a drop-in class-name
change: `torch_geometric.nn.SAGEConv` has no `edge_attr`/`edge_dim` support
at all (confirmed empirically 2026-08-09 — passing edge_attr into a
HeteroConv-wrapped SAGEConv raises TypeError). The weighted
`collaborates_with`/`co_occurs_with` relations here rely on GATConv's
edge_dim mechanism, which GraphSAGE has no equivalent for. A GraphSAGE
backbone will need either a small custom MessagePassing layer that folds
edge weight into the message (e.g. scale x_j by edge weight before mean
aggregation) or another way to inject edge weight — budget real time for
this in Weeks 11-13, don't assume it's a one-line swap. See
GRAPH_SCHEMA.md's "Why GAT over GraphSAGE" section.
"""

from __future__ import annotations

import torch
from torch import nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import GATConv, HeteroConv

from ml.schema import EDGE_TYPES, WEIGHTED_EDGE_TYPES


class SchemaSmokeTestGAT(nn.Module):
    def __init__(self, hidden_channels: int = 32, heads: int = 2):
        super().__init__()
        convs = {}
        for edge_type in EDGE_TYPES:
            edge_dim = 1 if edge_type in WEIGHTED_EDGE_TYPES else None
            convs[edge_type] = GATConv(
                (-1, -1),
                hidden_channels,
                heads=heads,
                concat=False,
                edge_dim=edge_dim,
                add_self_loops=False,
            )
        self.conv1 = HeteroConv(convs, aggr="sum")

    def forward(self, data: HeteroData) -> dict[str, torch.Tensor]:
        x_dict = data.x_dict
        edge_index_dict = data.edge_index_dict
        edge_attr_dict = {
            edge_type: data[edge_type].edge_attr
            for edge_type in WEIGHTED_EDGE_TYPES
            if "edge_attr" in data[edge_type]
        }
        out = self.conv1(x_dict, edge_index_dict, edge_attr_dict=edge_attr_dict)
        return {k: v.relu() for k, v in out.items()}
