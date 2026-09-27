"""Synthetic HeteroData generator for schema validation.

Real data won't exist until Track A finishes Weeks 3-4 scraping, so this
builds a small graph of fake creators/brands with random features/edges to
confirm the schema in schema.py actually holds together end-to-end.
"""

from __future__ import annotations

import torch

from ml.schema import (
    BRAND_FEATURE_DIM,
    CREATOR_FEATURE_DIM,
    empty_hetero_data,
)


def make_dummy_hetero_data(
    num_creators: int = 6,
    num_brands: int = 3,
    avg_degree: int = 3,
    seed: int = 0,
) -> "HeteroData":
    gen = torch.Generator().manual_seed(seed)
    data = empty_hetero_data()

    data["creator"].x = torch.randn((num_creators, CREATOR_FEATURE_DIM), generator=gen)
    data["brand"].x = torch.randn((num_brands, BRAND_FEATURE_DIM), generator=gen)

    def symmetric_weighted_edges(n: int, num_pairs: int):
        # Unique unordered pairs, both directions populated with the SAME
        # weight, per the GRAPH_SCHEMA.md contract ("if creator A
        # collaborated with creator B, both (A,B) and (B,A) edges should be
        # present with the same weight"). Sampling from unique pairs (rather
        # than drawing (src, dst) independently at random) avoids the two
        # directions ending up with different weights by chance collision.
        all_pairs = torch.combinations(torch.arange(n), r=2)
        num_pairs = min(num_pairs, all_pairs.size(0))
        perm = torch.randperm(all_pairs.size(0), generator=gen)[:num_pairs]
        pairs = all_pairs[perm]
        weight = torch.rand((num_pairs, 1), generator=gen)
        edge_index = torch.cat([pairs.t(), pairs.flip(1).t()], dim=1)
        edge_attr = torch.cat([weight, weight], dim=0)
        return edge_index, edge_attr

    collab_index, collab_attr = symmetric_weighted_edges(num_creators, num_creators * avg_degree // 2)
    data["creator", "collaborates_with", "creator"].edge_index = collab_index
    data["creator", "collaborates_with", "creator"].edge_attr = collab_attr

    cooccur_index, cooccur_attr = symmetric_weighted_edges(num_creators, num_creators * avg_degree // 2)
    data["creator", "co_occurs_with", "creator"].edge_index = cooccur_index
    data["creator", "co_occurs_with", "creator"].edge_attr = cooccur_attr

    # num_brands=0 is a real case (e.g. loading real data before any brands
    # exist, per GRAPH_SCHEMA.md) -- torch.randint(0, 0, ...) raises, so
    # skip sponsor-edge generation entirely rather than forcing a phantom
    # minimum of 1. empty_hetero_data() already leaves these as (2,0).
    if num_brands > 0:
        num_sponsor_edges = max(1, num_brands * 2)
        brand_idx = torch.randint(0, num_brands, (num_sponsor_edges,), generator=gen)
        creator_idx = torch.randint(0, num_creators, (num_sponsor_edges,), generator=gen)
        data["brand", "sponsors", "creator"].edge_index = torch.stack([brand_idx, creator_idx], dim=0)
        data["creator", "sponsored_by", "brand"].edge_index = torch.stack([creator_idx, brand_idx], dim=0)

    return data
