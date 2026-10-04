"""Multi-relational exposure: treatment propagates through EVERY relation type,
each with its own learned attention and its own transmission share.

WHY. `ml/exposure.py` computes exposure over a single edge index, and
`GAILModel` passed it `collaborates_with` only. The ~1,414 `co_occurs_with`
edges in the schema reached the GNN backbone (so they shaped embeddings) but
carried no treatment at all: a creator connected to a sponsored creator purely
through co-occurrence received exposure exactly 0.0.

That is a modelling assumption, not a neutral default. It asserts that
audience-level co-mention transmits no sponsorship spillover whatsoever, which
is an empirical question nobody has answered for this domain.

    single-relation (before)   e_i = sum_j  alpha_ij * T_j
    multi-relational (here)    e_i = sum_r  beta_r * sum_j alpha^r_ij * T_j

Each relation r gets its own GATConv -- so what makes a collaboration edge
strong is learned independently of what makes a co-occurrence edge strong --
and `beta_r` is a learned scalar governing how much each channel contributes.

WHY beta IS A SOFTMAX. The mixing weights are stored as free logits and passed
through softmax, so they are non-negative and sum to 1. Three reasons:

  1. Interpretability. `beta_r` reads directly as "share of transmission
     carried by relation r" -- a finding about the domain (which relationship
     type actually carries sponsorship spillover), not just a parameter.
  2. Scale. Unconstrained weights let the model inflate exposure to shrink
     prediction error, which would fight `L_consistency` and `L_smooth`
     rather than cooperate with them.
  3. Identifiability. alpha is already softmax-normalized per destination
     node; an unconstrained beta on top would make (alpha, beta) jointly
     unidentifiable up to a scale factor per relation.

RENORMALIZATION OVER PRESENT RELATIONS. If a relation has no edges in the
graph it is dropped and beta is renormalized over the rest. Without this, a
graph carrying only collaboration edges would produce systematically SMALLER
exposure than the single-relation module did (because co-occurrence's share of
the softmax would be silently discarded), making this module non-comparable
with the prior one on the same data. With it, a single-relation graph
reproduces single-relation behaviour exactly.

CHECKPOINT COMPATIBILITY. This changes the parameter set, so checkpoints saved
from the single-relation model will not load into a model using this module.
Retraining is required; that is expected, not a bug.
"""

from __future__ import annotations

import torch
from torch import nn
from torch_geometric.nn import GATConv

# Relations through which treatment can propagate between creators. Brand-side
# edge types are excluded on purpose: `sponsors` / `sponsored_by` DEFINE the
# treatment vector T, so letting treatment also flow along them would feed the
# treatment signal back into its own exposure measure.
DEFAULT_EXPOSURE_RELATIONS = ("collaborates_with", "co_occurs_with")


class MultiRelationExposureModule(nn.Module):
    """Attention-weighted exposure aggregated across several relation types.

    Args:
        in_channels: embedding dim of the incoming node features.
        hidden_channels: GATConv output dim (the attention coefficients are
            what we use, so this mainly sets attention head capacity).
        heads: attention heads per relation. Coefficients are averaged across
            heads, matching `ml.exposure.ExposureModule`.
        relations: relation names to propagate treatment through, in a fixed
            order. The order is what `beta` indexes, so it is kept stable.
    """

    def __init__(
        self,
        in_channels: int,
        hidden_channels: int = 16,
        heads: int = 1,
        relations: tuple[str, ...] = DEFAULT_EXPOSURE_RELATIONS,
    ) -> None:
        super().__init__()
        if not relations:
            raise ValueError("need at least one relation to propagate treatment through")
        self.relations = tuple(relations)

        # One attention mechanism per relation -- this is the "heterogeneous
        # attention" half: W^r and a^r are not shared across relation types.
        self.attn_convs = nn.ModuleDict(
            {
                rel: GATConv(
                    in_channels,
                    hidden_channels,
                    heads=heads,
                    concat=False,
                    add_self_loops=False,
                )
                for rel in self.relations
            }
        )

        # Free logits; softmaxed in forward. Initialized at zero => uniform
        # shares, so training starts with no prior about which channel
        # transmits more and the data decides.
        self.mixing_logits = nn.Parameter(torch.zeros(len(self.relations)))

    @property
    def beta(self) -> torch.Tensor:
        """Current transmission share per relation, in `self.relations` order.

        Sums to 1 over ALL relations (not just those present in a given graph).
        This is the inspectable output: after training, `beta` answers which
        relationship type carries sponsorship spillover.
        """
        return torch.softmax(self.mixing_logits, dim=0)

    def beta_dict(self) -> dict[str, float]:
        """`beta` as a plain dict, for logging and checkpoint metadata."""
        return {rel: float(b) for rel, b in zip(self.relations, self.beta.detach())}

    def forward(
        self,
        x: torch.Tensor,
        edge_index_dict: dict[str, torch.Tensor],
        treatment: torch.Tensor,
    ) -> torch.Tensor:
        """Per-creator exposure, shape (N,).

        Args:
            x: (N, in_channels) node embeddings from the backbone.
            edge_index_dict: relation name -> (2, E_r) edge index. Missing or
                empty relations are skipped and beta is renormalized over the
                rest (see module docstring).
            treatment: (N,) 1.0 for currently-sponsored creators, else 0.

        Returns:
            (N,) exposure. Exactly 0 for any node with no treated neighbour in
            any relation, which is what `L_consistency` checks.
        """
        num_nodes = x.size(0)
        beta = self.beta

        present: list[tuple[int, str, torch.Tensor]] = []
        for idx, rel in enumerate(self.relations):
            edge_index = edge_index_dict.get(rel)
            if edge_index is not None and edge_index.numel() > 0 and edge_index.size(1) > 0:
                present.append((idx, rel, edge_index))

        if not present:
            # No usable edges anywhere: nothing can transmit. Returned via
            # x.sum() * 0 so the graph stays connected for autograd and this
            # path does not silently produce a gradient-free tensor.
            return x.sum() * 0.0 + torch.zeros(num_nodes, device=x.device)

        # Renormalize over present relations so a single-relation graph
        # reproduces single-relation scale (see module docstring).
        present_mass = beta[[idx for idx, _, _ in present]].sum()

        exposure = torch.zeros(num_nodes, device=x.device)
        for idx, rel, edge_index in present:
            _, (out_edge_index, alpha) = self.attn_convs[rel](
                x, edge_index, return_attention_weights=True
            )
            alpha = alpha.mean(dim=1) if alpha.dim() > 1 else alpha

            src, dst = out_edge_index
            weighted = alpha * treatment[src]

            per_relation = torch.zeros(num_nodes, device=x.device)
            per_relation.index_add_(0, dst, weighted)

            exposure = exposure + (beta[idx] / present_mass) * per_relation

        return exposure

    def per_relation_exposure(
        self,
        x: torch.Tensor,
        edge_index_dict: dict[str, torch.Tensor],
        treatment: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Unmixed exposure from each relation separately, for explainability.

        Returns the raw `sum_j alpha^r_ij * T_j` per relation WITHOUT the beta
        weighting, so the frontend can show how much of a creator's exposure
        came through collaboration versus co-occurrence. Not used in the
        forward pass; kept here so the decomposition cannot drift from it.
        """
        num_nodes = x.size(0)
        out: dict[str, torch.Tensor] = {}
        for rel in self.relations:
            edge_index = edge_index_dict.get(rel)
            per_relation = torch.zeros(num_nodes, device=x.device)
            if edge_index is not None and edge_index.numel() > 0 and edge_index.size(1) > 0:
                _, (out_edge_index, alpha) = self.attn_convs[rel](
                    x, edge_index, return_attention_weights=True
                )
                alpha = alpha.mean(dim=1) if alpha.dim() > 1 else alpha
                src, dst = out_edge_index
                per_relation.index_add_(0, dst, alpha * treatment[src])
            out[rel] = per_relation
        return out