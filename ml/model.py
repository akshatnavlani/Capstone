"""Heterogeneous GAT backbone — produces the per-node embeddings every other
GAIL component consumes.

This started life as `SchemaSmokeTestGAT`, a single-layer schema check whose
own docstring said "NOT the final GAIL model." It was then imported by
`GAILModel` and shipped, so the name and the single layer both outlived their
purpose. Renamed and given configurable depth; `SchemaSmokeTestGAT` remains as
a deprecated alias so callers on other branches keep working.

DEPTH. Each message-passing layer extends the receptive field by one hop. One
layer sees immediate neighbours only, which contradicted the specification's
"2-3 layers, multi-hop propagation" and mattered for spillover specifically:
sponsorship reaching a creator through an intermediary — A sponsored, B
collaborates with A, C collaborates with B — is invisible to a one-hop model.
`num_layers` now defaults to 2.

Not more than 2 by default. Each extra layer widens the receptive field but
also smooths node representations toward each other (over-smoothing), and on a
259-node graph with a 185-node giant component, 3 layers already reaches most
of it from most starting points. Depth is exposed as a hyperparameter rather
than fixed so the trade-off can be measured instead of assumed.

BACKBONE SWAP WARNING (unchanged, still applies). Swapping this for GraphSAGE
is NOT a drop-in class-name change: `torch_geometric.nn.SAGEConv` has no
`edge_attr`/`edge_dim` support at all (confirmed empirically 2026-08-09 —
passing edge_attr into a HeteroConv-wrapped SAGEConv raises TypeError). The
weighted `collaborates_with`/`co_occurs_with` relations here rely on GATConv's
edge_dim mechanism, which GraphSAGE has no equivalent for. A GraphSAGE backbone
will need either a small custom MessagePassing layer that folds edge weight
into the message (e.g. scale x_j by edge weight before mean aggregation) or
another way to inject edge weight — budget real time for this, don't assume
it's a one-line swap. See GRAPH_SCHEMA.md's "Why GAT over GraphSAGE" section.
"""

from __future__ import annotations

import torch
from torch import nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import GATConv, HeteroConv

from ml.schema import EDGE_TYPES, WEIGHTED_EDGE_TYPES

DEFAULT_NUM_LAYERS = 2


class HeteroGATBackbone(nn.Module):
    """Stacked heterogeneous GAT layers over the creator/brand graph.

    Args:
        hidden_channels: embedding width per node.
        heads: attention heads per relation (averaged, `concat=False`, so the
            output stays `hidden_channels` wide regardless of head count).
        num_layers: message-passing rounds, i.e. hops of receptive field.
    """

    def __init__(
        self,
        hidden_channels: int = 32,
        heads: int = 2,
        num_layers: int = DEFAULT_NUM_LAYERS,
    ):
        super().__init__()
        if num_layers < 1:
            raise ValueError(f"num_layers must be >= 1, got {num_layers}")
        self.num_layers = num_layers

        self.convs = nn.ModuleList()
        for _ in range(num_layers):
            convs = {}
            for edge_type in EDGE_TYPES:
                edge_dim = 1 if edge_type in WEIGHTED_EDGE_TYPES else None
                # (-1, -1) keeps input dims lazy, which matters beyond
                # convenience here: creator nodes carry 1289-dim multimodal
                # features while brand nodes carry profile metadata only, so
                # the two sides of a relation genuinely differ in width. Later
                # layers stay lazy for the same reason — they consume
                # hidden_channels rather than the raw feature dims.
                convs[edge_type] = GATConv(
                    (-1, -1),
                    hidden_channels,
                    heads=heads,
                    concat=False,
                    edge_dim=edge_dim,
                    add_self_loops=False,
                )
            self.convs.append(HeteroConv(convs, aggr="sum"))

    def forward(self, data: HeteroData) -> dict[str, torch.Tensor]:
        x_dict = data.x_dict
        edge_index_dict = data.edge_index_dict
        edge_attr_dict = {
            edge_type: data[edge_type].edge_attr
            for edge_type in WEIGHTED_EDGE_TYPES
            if "edge_attr" in data[edge_type]
        }

        for conv in self.convs:
            x_dict = conv(x_dict, edge_index_dict, edge_attr_dict=edge_attr_dict)
            # ReLU between every layer and after the last, matching the prior
            # single-layer behaviour (the exposure module and prediction head
            # were both built against non-negative embeddings).
            x_dict = {k: v.relu() for k, v in x_dict.items()}

        return x_dict


# Deprecated: kept so callers on other branches (scripts, backend) that still
# import the old name keep working. New code should use HeteroGATBackbone.
SchemaSmokeTestGAT = HeteroGATBackbone