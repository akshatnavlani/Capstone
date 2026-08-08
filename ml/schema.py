"""Heterogeneous graph schema for the GAIL branch (PROJECT_PLAN.md Section 3a).

Defines node types, edge types, and feature vector dimensions for the
creator/brand collaboration graph. This is the contract other tracks build
against — see GRAPH_SCHEMA.md for the human-readable version and open
questions for Track A (data pipeline) and Track C (fusion/backend).
"""

from __future__ import annotations

import torch
from torch_geometric.data import HeteroData

# --- Feature dimensions -----------------------------------------------------
# CLIP image embedding dim (openai/clip-vit-base-patch32 pooled output).
CLIP_DIM = 512

# BERT text embedding dim (bert-base-uncased pooled output).
BERT_DIM = 768

# Category taxonomy size (e.g. "Fitness", "Lifestyle", "Sports", ...).
# PLACEHOLDER pending Track A's finalized category list — see GRAPH_SCHEMA.md
# "Open items". Shared between creator niche and brand industry categories.
NUM_CATEGORIES = 8

# creator metadata: log_subscriber_count, engagement_rate, reputation_score
CREATOR_METADATA_DIM = 3 + NUM_CATEGORIES
CREATOR_FEATURE_DIM = CLIP_DIM + BERT_DIM + CREATOR_METADATA_DIM

# brand metadata: budget_tier
# ASSUMPTION (flagged in GRAPH_SCHEMA.md): brands get a BERT embedding of
# their product/marketing copy but no CLIP embedding, since Section 1 of
# PROJECT_PLAN.md does not scope any brand-side scraping (only creator-side
# YouTube/Instagram/Reddit collection). Revisit once Track A confirms.
BRAND_METADATA_DIM = 1 + NUM_CATEGORIES
BRAND_FEATURE_DIM = BERT_DIM + BRAND_METADATA_DIM

NODE_TYPES = ("creator", "brand")

# Edge types. Reverse edges are included explicitly (rather than relying on
# T.ToUndirected()/T.ToDirected() at load time) so the schema is unambiguous
# for Track A to populate directly.
EDGE_TYPES = (
    ("creator", "collaborates_with", "creator"),  # collaboration frequency, weighted
    ("creator", "co_occurs_with", "creator"),      # platform co-occurrence, weighted
    ("brand", "sponsors", "creator"),               # treatment edge (is_sponsored-derived)
    ("creator", "sponsored_by", "brand"),           # reverse of "sponsors", for message passing
)

# Edge types that carry a scalar edge_attr weight.
WEIGHTED_EDGE_TYPES = (
    ("creator", "collaborates_with", "creator"),
    ("creator", "co_occurs_with", "creator"),
)


def empty_hetero_data() -> HeteroData:
    """Return a HeteroData with the correct node/edge type structure and
    feature dims, but zero nodes/edges. Documents the contract in code —
    Track A's ETL output should be loadable into this shape.
    """
    data = HeteroData()

    data["creator"].x = torch.empty((0, CREATOR_FEATURE_DIM), dtype=torch.float32)
    data["brand"].x = torch.empty((0, BRAND_FEATURE_DIM), dtype=torch.float32)

    for edge_type in EDGE_TYPES:
        data[edge_type].edge_index = torch.empty((2, 0), dtype=torch.long)
        if edge_type in WEIGHTED_EDGE_TYPES:
            data[edge_type].edge_attr = torch.empty((0, 1), dtype=torch.float32)

    return data
