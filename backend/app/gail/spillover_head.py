"""Spillover prediction head (GAIL working-doc Phase 2, Step 8: "Predict
Spillover Effects" — spillover = f(exposure, creator_features)).

A small MLP over [creator embedding, exposure] -> scalar predicted
engagement gain, per PROJECT_PLAN.md's off-the-shelf-methods preference.
Not trained against anything real yet (no real sponsorship events exist) —
see ml/training.py for how this composes with the rest of the GAIL model.
"""

from __future__ import annotations

import torch
from torch import nn


class SpilloverPredictionHead(nn.Module):
    def __init__(self, embedding_dim: int, hidden_dim: int = 16):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embedding_dim + 1, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, embeddings: torch.Tensor, exposure: torch.Tensor) -> torch.Tensor:
        x = torch.cat([embeddings, exposure.unsqueeze(-1)], dim=-1)
        return self.net(x).squeeze(-1)
