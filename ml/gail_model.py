"""Wires the GAT backbone, exposure module, propensity model, and
prediction head into a single forward pass — the piece that was missing
between "individually tested components" and "something a training loop
can actually optimize."

EXPOSURE RELATIONS. By default, treatment propagates through every
creator-to-creator relation in `DEFAULT_EXPOSURE_RELATIONS`, each with its own
attention parameters and a learned transmission share `beta_r`
(ml/multi_relation_exposure.py). Prior to this, exposure was computed over
`collaborates_with` alone and the ~1,414 `co_occurs_with` edges carried no
treatment — a modelling assumption that co-mention transmits nothing, asserted
rather than tested.

Pass `exposure_relations=("collaborates_with",)` to recover exactly the old
single-relation behaviour. That is the ablation arm: single-relation vs
multi-relational is what evidences whether the extra channel carries real
spillover, so the collapsed configuration has to stay reachable.
"""

from __future__ import annotations

import torch
from torch import nn
from torch_geometric.data import HeteroData

from ml.causal_regularization import PropensityScoreModel
from ml.model import SchemaSmokeTestGAT
from ml.multi_relation_exposure import (
    DEFAULT_EXPOSURE_RELATIONS,
    MultiRelationExposureModule,
)
from ml.spillover_head import SpilloverPredictionHead


class GAILModel(nn.Module):
    def __init__(
        self,
        creator_feature_dim: int,
        hidden_channels: int = 16,
        heads: int = 2,
        exposure_relations: tuple[str, ...] = DEFAULT_EXPOSURE_RELATIONS,
    ):
        super().__init__()
        self.exposure_relations = tuple(exposure_relations)
        self.backbone = SchemaSmokeTestGAT(hidden_channels=hidden_channels, heads=heads)
        self.exposure_module = MultiRelationExposureModule(
            in_channels=hidden_channels,
            hidden_channels=hidden_channels,
            relations=self.exposure_relations,
        )
        self.propensity_model = PropensityScoreModel(in_dim=creator_feature_dim, hidden_dim=hidden_channels)
        self.prediction_head = SpilloverPredictionHead(embedding_dim=hidden_channels)

    def _edge_index_dict(self, data: HeteroData) -> dict[str, torch.Tensor]:
        """Pull the creator->creator edge index for each exposure relation.

        Missing relations are omitted rather than defaulted to empty: the
        exposure module renormalizes beta over the relations actually present,
        so an absent relation must not be mistaken for one with zero edges.
        """
        out: dict[str, torch.Tensor] = {}
        for rel in self.exposure_relations:
            key = ("creator", rel, "creator")
            if key in data.edge_types:
                out[rel] = data[key].edge_index
        return out

    def forward(
        self, data: HeteroData, treatment: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        embeddings = self.backbone(data)["creator"]
        exposure = self.exposure_module(
            embeddings, self._edge_index_dict(data), treatment
        )
        propensity = self.propensity_model(data["creator"].x)
        prediction = self.prediction_head(embeddings, exposure)
        return prediction, exposure, propensity

    def transmission_shares(self) -> dict[str, float]:
        """Learned `beta_r` per relation — which relationship type carries
        spillover. Inspectable output, not just an internal parameter.
        """
        return self.exposure_module.beta_dict()