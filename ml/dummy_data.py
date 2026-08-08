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

    def random_edges(num_edges: int, src_n: int, dst_n: int, self_loops_ok: bool):
        src = torch.randint(0, src_n, (num_edges,), generator=gen)
        dst = torch.randint(0, dst_n, (num_edges,), generator=gen)
        if not self_loops_ok:
            mask = src != dst
            src, dst = src[mask], dst[mask]
        return torch.stack([src, dst], dim=0)

    num_collab_edges = num_creators * avg_degree
    collab_index = random_edges(num_collab_edges, num_creators, num_creators, self_loops_ok=False)
    data["creator", "collaborates_with", "creator"].edge_index = collab_index
    data["creator", "collaborates_with", "creator"].edge_attr = torch.rand(
        (collab_index.size(1), 1), generator=gen
    )

    num_cooccur_edges = num_creators * avg_degree
    cooccur_index = random_edges(num_cooccur_edges, num_creators, num_creators, self_loops_ok=False)
    data["creator", "co_occurs_with", "creator"].edge_index = cooccur_index
    data["creator", "co_occurs_with", "creator"].edge_attr = torch.rand(
        (cooccur_index.size(1), 1), generator=gen
    )

    num_sponsor_edges = max(1, num_brands * 2)
    brand_idx = torch.randint(0, num_brands, (num_sponsor_edges,), generator=gen)
    creator_idx = torch.randint(0, num_creators, (num_sponsor_edges,), generator=gen)
    data["brand", "sponsors", "creator"].edge_index = torch.stack([brand_idx, creator_idx], dim=0)
    data["creator", "sponsored_by", "brand"].edge_index = torch.stack([creator_idx, brand_idx], dim=0)

    return data
