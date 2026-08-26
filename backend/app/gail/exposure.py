"""Exposure computation (GAIL working-doc Phase 2, Step 7: "Compute Learned
Exposure" — how exposed each creator is, based on sponsored neighbors and
attention weights). Weeks 11-13 de-risking work, built and tested against
dummy data since no real sponsorship events exist yet to train against.

Off-the-shelf per PROJECT_PLAN.md's stated preference: reuses PyG
GATConv's own `return_attention_weights` output (softmax-normalized per
destination node, already exactly the "personalized weight per
collaborator" GAIL Step 6 describes) rather than inventing a separate
attention mechanism.
"""

from __future__ import annotations

import torch
from torch import nn
from torch_geometric.nn import GATConv


class ExposureModule(nn.Module):
    def __init__(self, in_channels: int, hidden_channels: int = 16, heads: int = 1):
        super().__init__()
        self.attn_conv = GATConv(
            in_channels, hidden_channels, heads=heads, concat=False, add_self_loops=False
        )

    def forward(
        self, x: torch.Tensor, edge_index: torch.Tensor, treatment: torch.Tensor
    ) -> torch.Tensor:
        """`treatment`: (N,) — 1.0 for currently-sponsored creators, else 0.
        Returns per-creator exposure, (N,): attention-weighted sum of
        sponsored neighbors' treatment (GAIL doc: "traditional exposure" for
        1-of-3-sponsored-neighbors is 1/3; here the 1/3 uniform weight is
        replaced by a learned attention coefficient per neighbor).
        """
        if edge_index.size(1) == 0:
            return torch.zeros(x.size(0), device=x.device)

        _, (out_edge_index, alpha) = self.attn_conv(x, edge_index, return_attention_weights=True)
        alpha = alpha.mean(dim=1) if alpha.dim() > 1 else alpha  # average across heads

        src, dst = out_edge_index
        weighted_treatment = alpha * treatment[src]
        exposure = torch.zeros(x.size(0), device=x.device)
        exposure.index_add_(0, dst, weighted_treatment)
        return exposure
