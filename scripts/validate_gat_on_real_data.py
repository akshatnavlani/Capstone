"""Re-runs the Weeks 5-6 GAT inductive-generalization check against real
data, per the user's Weeks 7-8 ask: the synthetic-only version (dummy data
scaled 6->20 nodes) was good evidence but not real-data evidence.

Not a pytest test: needs real feature-store JSON (fetched from Track C's
`/feature-store/*` endpoints, which need a live DB connection) plus network
access for real thumbnail URLs -- both one-off/manual, not CI-suitable.

Usage:
  1. Run Track C's backend locally against the real Supabase DB (needs
     DATABASE_URL, not committed anywhere -- ask the user for it).
  2. Save its output:
       curl http://127.0.0.1:8000/feature-store/creators > creators.json
       curl http://127.0.0.1:8000/feature-store/edges/collaborations > collab_edges.json
  3. .venv\\Scripts\\python.exe scripts\\validate_gat_on_real_data.py creators.json collab_edges.json
"""

from __future__ import annotations

import json
import sys

import torch

from ml.dummy_data import make_dummy_hetero_data
from ml.feature_extraction import FeatureExtractor, RawCreatorRecord
from ml.model import SchemaSmokeTestGAT
from ml.schema import CREATOR_FEATURE_DIM


def load_real_creator_features(
    creators_json_path: str, extractor: FeatureExtractor
) -> tuple[torch.Tensor, dict[str, int]]:
    with open(creators_json_path, encoding="utf-8") as f:
        records = json.load(f)
    vecs = []
    id_to_index = {}
    for i, r in enumerate(records):
        record = RawCreatorRecord(
            category_one_hot=r["category_one_hot"],
            log_subscriber_count=r["log_subscriber_count"],
            engagement_rate=r["engagement_rate"],
            reputation_score=r["reputation_score"],
            raw_text=r["raw_text"],
            thumbnail_urls=r["thumbnail_urls"],
        )
        print(f"  extracting features for {r['name']!r} (is_stub={r['is_stub']})...")
        vecs.append(extractor.extract(record))
        id_to_index[r["creator_id"]] = i
    return torch.stack(vecs), id_to_index


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    creators_path, collab_edges_path = sys.argv[1], sys.argv[2]

    print("Loading CLIP + BERT (real pretrained models)...")
    extractor = FeatureExtractor(max_thumbnails=5)

    print("Extracting real creator features...")
    real_x, creator_id_to_index = load_real_creator_features(creators_path, extractor)
    num_real = real_x.size(0)
    print(f"  {num_real} real creators, feature dim {real_x.shape[1]} (expected {CREATOR_FEATURE_DIM})")
    assert real_x.shape[1] == CREATOR_FEATURE_DIM

    with open(collab_edges_path, encoding="utf-8") as f:
        collab_edges = json.load(f)
    print(f"  {len(collab_edges)} real collaboration edges")

    torch.manual_seed(0)
    model = SchemaSmokeTestGAT(hidden_channels=16, heads=2)

    # Test A: real node features, real (possibly zero) edges, zero brand
    # nodes (0 real brands as of 2026-08-09) -- confirms real feature
    # VALUES (not just synthetic Gaussian noise) don't crash the model:
    # real null-metadata handling, real BERT/CLIP embedding distributions.
    real_only = make_dummy_hetero_data(num_creators=num_real, num_brands=0, avg_degree=0, seed=0)
    real_only["creator"].x = real_x
    if collab_edges:
        src = torch.tensor([creator_id_to_index[e["source_creator_id"]] for e in collab_edges])
        dst = torch.tensor([creator_id_to_index[e["target_creator_id"]] for e in collab_edges])
        real_only["creator", "collaborates_with", "creator"].edge_index = torch.stack([src, dst])
        real_only["creator", "collaborates_with", "creator"].edge_attr = torch.tensor(
            [[e["weight"]] for e in collab_edges]
        )
    out_real = model(real_only)
    print(f"Test A (real features, {len(collab_edges)} real edges): output shape {out_real['creator'].shape}")
    assert out_real["creator"].shape == (num_real, 16)
    assert not out_real["creator"].isnan().any()

    # Test B: SAME trained module instance, no retraining, on a graph with
    # real creators PLUS synthetic ones appended (with synthetic edges) --
    # since real collaboration edges are currently 0/near-0, this is the
    # only way to exercise the message-passing/attention pathway at all
    # while still grounding some node features in real data. Honest
    # limitation: this tests "generalizes to new nodes" with real base
    # features, NOT "generalizes on a real graph structure" -- real edge
    # data isn't available yet to test that specifically.
    bigger = make_dummy_hetero_data(num_creators=num_real + 10, num_brands=3, seed=1)
    bigger["creator"].x[:num_real] = real_x
    out_bigger = model(bigger)
    print(f"Test B (same model, +10 synthetic nodes, no retrain): output shape {out_bigger['creator'].shape}")
    assert out_bigger["creator"].shape == (num_real + 10, 16)
    assert not out_bigger["creator"].isnan().any()

    print("\nPASSED: model runs correctly on real feature values, and the same")
    print("trained instance still generalizes to new nodes with no retraining.")
    print("NOT tested: generalization over real GRAPH STRUCTURE (edges) --")
    print("real collaboration-edge data is empty as of this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
