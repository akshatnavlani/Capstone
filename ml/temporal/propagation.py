"""Sentiment propagation (PendingWork S1): negative spillover.

A creator with a safety problem (e.g. a controversy) passes some of that risk
to their collaborators along the same edges GAIL uses (collaborates_with and
co_occurs_with). Risk decays by `alpha` per hop and is split across a node's
neighbours, so a hub does not pass its full shock to every neighbour.

`top_source` names the creator contributing the most risk to a node, which is
what populates risk_alerts.propagated_from_creator_id.
"""

from __future__ import annotations

import numpy as np

Edge = tuple[int, int, float]  # (source index, target index, weight)


def normalized_adjacency(
    n_nodes: int,
    edges_by_relation: dict[str, list[Edge]],
    relation_weights: dict[str, float] | None = None,
) -> np.ndarray:
    """Row-normalized, symmetrized, relation-weighted adjacency."""
    relation_weights = relation_weights or {}
    A = np.zeros((n_nodes, n_nodes))
    for relation, edges in edges_by_relation.items():
        w_rel = relation_weights.get(relation, 1.0)
        for src, dst, w in edges:
            A[src, dst] += w_rel * w
    A = np.maximum(A, A.T)
    np.fill_diagonal(A, 0.0)
    row_sums = A.sum(axis=1, keepdims=True)
    return np.divide(A, row_sums, out=np.zeros_like(A), where=row_sums > 0)


def risk_shock(safety: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Own risk in [0, 1]: 0 at or above `threshold`, 1 at safety 0. Only
    creators below the threshold propagate anything.
    """
    return np.clip((threshold - np.asarray(safety, dtype=float)) / threshold, 0.0, 1.0)


def propagation_matrix(A_norm: np.ndarray, alpha: float = 0.5, hops: int = 2) -> np.ndarray:
    """M[i, j] = how much of node j's shock reaches node i (self excluded)."""
    M = np.zeros_like(A_norm)
    power = np.eye(len(A_norm))
    for k in range(1, hops + 1):
        power = power @ A_norm
        M += (alpha**k) * power
    np.fill_diagonal(M, 0.0)
    return M


def propagate(shock: np.ndarray, M: np.ndarray) -> np.ndarray:
    return M @ np.asarray(shock, dtype=float)


def top_source(M: np.ndarray, shock: np.ndarray, node: int) -> int | None:
    """Index of the creator contributing most risk to `node`, or None."""
    contributions = M[node] * np.asarray(shock, dtype=float)
    j = int(np.argmax(contributions))
    return j if contributions[j] > 0 else None


def apply_propagated_risk(safety: np.ndarray, propagated: np.ndarray, beta: float = 0.5) -> np.ndarray:
    """Lower each creator's safety by `beta` times the risk reaching them."""
    return np.clip(np.asarray(safety, dtype=float) - beta * np.asarray(propagated, dtype=float), 0.0, 1.0)
