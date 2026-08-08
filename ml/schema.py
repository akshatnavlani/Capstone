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

# Brand category is free-text/nullable in Track A's real `brands` table
# ("industry/vertical", not classified into a fixed enum yet) — NOT the same
# taxonomy as CREATOR_CATEGORIES. This count is still a placeholder pending
# Track A's real taxonomy; everything else below is grounded in real
# `brands` columns (origin/track-a-data-infra:supabase/migrations/
# 20260809010000_add_brands.sql, confirmed 2026-08-09).
NUM_BRAND_CATEGORIES = 5  # PLACEHOLDER pending Track A's brand-category taxonomy

# Rewritten 2026-08-09 against Track A's real `brands` table. The Weeks 3-4
# guess (BERT-of-marketing-copy + budget_tier) was wrong in KIND, not just in
# values: `brands` has no text/bio field at all — Track A's scope is
# "basic profile data" only (category, follower_count, post_count,
# is_verified, up to 3 platform handles), not brand content the way creator
# posts/captions are. So no CLIP, no BERT for brand nodes under the current
# scope — this is a real, structural feature-richness gap vs. creator nodes
# (1289-dim) that GRAPH_SCHEMA.md documents. Metadata:
# log_follower_count, log_post_count, is_verified, num_platforms_present
# (count of non-null youtube/instagram/reddit handles, 0-3).
BRAND_METADATA_DIM = 4 + NUM_BRAND_CATEGORIES
BRAND_FEATURE_DIM = BRAND_METADATA_DIM

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
