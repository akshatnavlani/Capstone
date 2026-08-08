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

# Creator category taxonomy, matching Track A's `creators.category` enum
# (origin/track-a-data-infra:SCHEMA.md, confirmed 2026-08-08). NOT confirmed
# as the right taxonomy for brand nodes — see GRAPH_SCHEMA.md "Open items".
CREATOR_CATEGORIES = (
    "athlete",
    "team",
    "league",
    "fitness_influencer",
    "lifestyle_influencer",
    "other",
)
NUM_CATEGORIES = len(CREATOR_CATEGORIES)

# creator metadata: log_subscriber_count, engagement_rate, reputation_score
CREATOR_METADATA_DIM = 3 + NUM_CATEGORIES
CREATOR_FEATURE_DIM = CLIP_DIM + BERT_DIM + CREATOR_METADATA_DIM

# PLACEHOLDER — replace once Track A publishes a `brands` table, see
# GRAPH_SCHEMA.md ("brand" node section). Direction is resolved (user
# decided on real brand scraping, not text-derived approximation; Track A is
# adding the table this week) but it hasn't landed yet. Everything below —
# BERT-of-marketing-copy, budget_tier, shared category taxonomy — is a guess
# for dummy-data validation only, not a confirmed contract. Do not build
# Track A/C-facing code against these exact dims until GRAPH_SCHEMA.md's
# brand section is rewritten against real columns.
BRAND_METADATA_DIM = 1 + NUM_CATEGORIES  # PLACEHOLDER: budget_tier + category one-hot
BRAND_FEATURE_DIM = BERT_DIM + BRAND_METADATA_DIM  # PLACEHOLDER, see above

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
