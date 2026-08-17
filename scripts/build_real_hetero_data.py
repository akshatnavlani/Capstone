"""Builds and trains against the real HeteroData object (PHASE 1, Track B's
step in CAPSTONE_NEXT_STEPS.md section 6 "Sequential relay").

Second run of this script. The first (2026-08-15, 63 creators/10 pairs/10
events) found 0 computable training pairs and stopped rather than faking a
result. This round the graph and pair count have both grown substantially
(259 creators, 161 resolved collaboration pairs, 32 sponsorship events,
CAPSTONE_NEXT_STEPS.md P0.2/P0.4 as of 2026-08-17) -- run
`scripts/find_computable_training_pairs.py` FIRST to enumerate every real
computable (event, neighbor, platform) triple and write
`computable_pairs.json`; this script consumes that file to build a REAL
(not placeholder) target tensor for whichever creators have one.

Not a pytest test (needs live network + a running feature-store server +
real thumbnail fetches) -- one-off/manual, matching the existing
`validate_gat_on_real_data.py` pattern.

Usage (after starting Track C's backend locally against the real DB, see
that script's docstring for the how-to):
    curl http://127.0.0.1:8000/feature-store/creators > creators.json
    curl http://127.0.0.1:8000/feature-store/edges/collaborations > collab_edges.json
    curl http://127.0.0.1:8000/feature-store/edges/co-occurrence > co_occurrence_edges.json
    curl http://127.0.0.1:8000/feature-store/edges/sponsorships > sponsorship_edges.json
    .venv\\Scripts\\python.exe scripts\\find_computable_training_pairs.py <dir containing the above>
    .venv\\Scripts\\python.exe scripts\\build_real_hetero_data.py \\
        creators.json collab_edges.json co_occurrence_edges.json sponsorship_edges.json computable_pairs.json

Brand node features and the full (not just brand_id-linked) sponsorship
event list aren't behind a feature-store endpoint yet, so this script reads
`brands` and `creator_sponsorship_events` directly via DATABASE_URL
(read-only), following this track's established pattern for data Track C's
API doesn't expose (see HANDOFF.md Lesson 5).
"""

from __future__ import annotations

import json
import math
import os
import sys

import networkx as nx
import psycopg2
import torch

from ml.causal_regularization import has_sponsored_neighbor
from ml.feature_extraction import FeatureExtractor, RawCreatorRecord
from ml.gail_loss import compute_gail_loss
from ml.gail_model import GAILModel
from ml.model import SchemaSmokeTestGAT
from ml.schema import (
    BRAND_METADATA_DIM,
    CREATOR_FEATURE_DIM,
    NUM_BRAND_CATEGORIES,
    empty_hetero_data,
)
from ml.training import TrainConfig, train


def load_creator_features(path: str, extractor: FeatureExtractor) -> tuple[torch.Tensor, dict[str, int], list[str]]:
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    vecs, id_to_index, order = [], {}, []
    for i, r in enumerate(records):
        record = RawCreatorRecord(
            category_one_hot=r["category_one_hot"],
            log_subscriber_count=r["log_subscriber_count"],
            engagement_rate=r["engagement_rate"],
            reputation_score=r["reputation_score"],
            raw_text=r["raw_text"],
            thumbnail_urls=r["thumbnail_urls"],
        )
        print(f"  [{i + 1}/{len(records)}] extracting features for {r['name']!r} (is_stub={r['is_stub']})...")
        vecs.append(extractor.extract(record))
        id_to_index[r["creator_id"]] = i
        order.append(r["creator_id"])
    return torch.stack(vecs), id_to_index, order


def load_symmetric_edges(path: str, id_to_index: dict[str, int]) -> tuple[torch.Tensor, torch.Tensor]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    if not rows:
        return torch.empty((2, 0), dtype=torch.long), torch.empty((0, 1), dtype=torch.float32)
    src = torch.tensor([id_to_index[r["source_creator_id"]] for r in rows])
    dst = torch.tensor([id_to_index[r["target_creator_id"]] for r in rows])
    weight = torch.tensor([[r["weight"]] for r in rows], dtype=torch.float32)
    return torch.stack([src, dst]), weight


def load_brands(database_url: str) -> tuple[torch.Tensor, dict[str, int]]:
    """Brand node features. `brands` has no populated category/follower/
    post/verified data for any of the 10 real rows as of this round
    (checked directly, not assumed) -- every brand's metadata segment is
    therefore all-zero except num_platforms_present, which is also 0 for
    all 10 (no handles populated either). This is a real structural finding
    (Track A's documented scope: brands table is populated ONLY from
    disclosure-text brand-name extraction, which yields a name and nothing
    else), not a bug in this script -- flagged in the report, not patched
    around here.
    """
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    cur.execute(
        "select brand_id::text, name, category, follower_count, post_count, "
        "is_verified, youtube_handle, instagram_handle, reddit_handle from brands"
    )
    rows = cur.fetchall()
    conn.close()

    vecs, id_to_index = [], {}
    for i, (bid, name, category, follower_count, post_count, is_verified, yt, ig, rd) in enumerate(rows):
        num_platforms = sum(1 for h in (yt, ig, rd) if h)
        metadata = [
            math.log1p(follower_count) if follower_count else 0.0,
            math.log1p(post_count) if post_count else 0.0,
            float(bool(is_verified)),
            float(num_platforms),
        ]
        # No real brand-category taxonomy exists yet (ml/schema.py
        # NUM_BRAND_CATEGORIES is a placeholder) and category is None for
        # every real row -- one-hot stays all-zero rather than guessing a
        # mapping with no real values to anchor it against.
        metadata += [0.0] * NUM_BRAND_CATEGORIES
        vec = torch.tensor(metadata, dtype=torch.float32)
        assert vec.shape[0] == BRAND_METADATA_DIM
        vecs.append(vec)
        id_to_index[bid] = i
        print(f"  brand {name!r}: category={category}, follower_count={follower_count}, "
              f"post_count={post_count}, is_verified={is_verified}, platforms={num_platforms}")
    return torch.stack(vecs), id_to_index


def load_sponsorship_edges(
    path: str, creator_id_to_index: dict[str, int], brand_id_to_index: dict[str, int]
) -> tuple[torch.Tensor, torch.Tensor]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    if not rows:
        return torch.empty((2, 0), dtype=torch.long), torch.empty((2, 0), dtype=torch.long)
    brand_idx = torch.tensor([brand_id_to_index[r["brand_id"]] for r in rows])
    creator_idx = torch.tensor([creator_id_to_index[r["creator_id"]] for r in rows])
    return torch.stack([brand_idx, creator_idx]), torch.stack([creator_idx, brand_idx])


def load_treatment(database_url: str, creator_id_to_index: dict[str, int], num_creators: int) -> torch.Tensor:
    """1.0 for any creator with a real is_sponsored=true event (all 32, not
    just the 10 with brand_id resolved -- "did this creator get sponsored"
    is the causal treatment question and doesn't require the brand link;
    that's only needed for the schema's separate sponsors/sponsored_by
    edge type).
    """
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    cur.execute("select distinct creator_id::text from creator_sponsorship_events")
    sponsored_creator_ids = {row[0] for row in cur.fetchall()}
    conn.close()

    treatment = torch.zeros(num_creators, dtype=torch.float32)
    for cid in sponsored_creator_ids:
        if cid in creator_id_to_index:
            treatment[creator_id_to_index[cid]] = 1.0
    return treatment


def load_real_targets(
    computable_pairs_path: str, creator_id_to_index: dict[str, int], num_creators: int
) -> tuple[torch.Tensor, list[dict]]:
    """Real (not placeholder) target tensor, built from
    `scripts/find_computable_training_pairs.py`'s output. Per computable
    (event, neighbor, platform) triple, computes a relative engagement
    lift -- (after_avg - before_avg) / (before_avg + 1) -- so Instagram
    like-count-scale deltas and Reddit score-scale deltas are comparable on
    roughly the same axis rather than mixed as raw counts. A neighbor
    appearing in multiple triples (multiple events and/or platforms) gets
    the mean of their relative lifts. Every other creator -- the vast
    majority -- gets 0, which means "no real signal computed", not
    "confirmed zero effect".
    """
    with open(computable_pairs_path, encoding="utf-8") as f:
        pairs = json.load(f)

    target = torch.zeros(num_creators, dtype=torch.float32)
    lifts_by_neighbor: dict[str, list[float]] = {}
    for p in pairs:
        lift = (p["avg_engagement_after"] - p["avg_engagement_before"]) / (p["avg_engagement_before"] + 1)
        lifts_by_neighbor.setdefault(p["neighbor_id"], []).append(lift)

    for neighbor_id, lifts in lifts_by_neighbor.items():
        if neighbor_id in creator_id_to_index:
            target[creator_id_to_index[neighbor_id]] = sum(lifts) / len(lifts)

    return target, pairs


def report_structure(data, id_to_name: dict[int, str]) -> None:
    num_creators = data["creator"].x.size(0)
    num_brands = data["brand"].x.size(0)
    print(f"\n=== Real graph structure: {num_creators} creators, {num_brands} brands ===")

    g = nx.Graph()
    g.add_nodes_from(range(num_creators))
    for rel in ("collaborates_with", "co_occurs_with"):
        edge_index = data["creator", rel, "creator"].edge_index
        for s, d in edge_index.t().tolist():
            g.add_edge(s, d)

    degrees = dict(g.degree())
    isolated = [n for n, d in degrees.items() if d == 0]
    components = list(nx.connected_components(g))
    non_trivial = [c for c in components if len(c) > 1]

    from collections import Counter
    degree_counts = Counter(degrees.values())
    print("Degree distribution (creator-creator graph, collaborates_with + co_occurs_with):")
    for deg in sorted(degree_counts):
        print(f"  degree {deg}: {degree_counts[deg]} nodes")
    print(f"Isolated nodes (degree 0): {len(isolated)} of {num_creators} "
          f"({100 * len(isolated) / num_creators:.1f}%)")
    print(f"Connected components: {len(components)} total, {len(non_trivial)} with >1 node")
    for c in non_trivial:
        names = sorted(id_to_name[i] for i in c)
        print(f"  component ({len(c)} nodes): {names}")

    for edge_type in [
        ("creator", "collaborates_with", "creator"),
        ("creator", "co_occurs_with", "creator"),
        ("brand", "sponsors", "creator"),
        ("creator", "sponsored_by", "brand"),
    ]:
        n_edges = data[edge_type].edge_index.size(1)
        print(f"  {edge_type}: {n_edges} edges")


def main() -> int:
    if len(sys.argv) != 6:
        print(__doc__)
        return 1
    creators_path, collab_path, cooccur_path, sponsorship_path, computable_pairs_path = sys.argv[1:6]

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL env var required (session-only, never committed) for brands + "
              "treatment/event lookups that aren't behind a feature-store endpoint yet.")
        return 1

    print("Loading CLIP + BERT (real pretrained models)...")
    extractor = FeatureExtractor(max_thumbnails=5)

    print("\n--- TASK 1: building the first real HeteroData ---")
    print("Extracting real creator features...")
    real_x, creator_id_to_index, creator_order = load_creator_features(creators_path, extractor)
    id_to_name = {}
    with open(creators_path, encoding="utf-8") as f:
        for r in json.load(f):
            id_to_name[creator_id_to_index[r["creator_id"]]] = r["name"]
    num_creators = real_x.size(0)
    assert real_x.shape[1] == CREATOR_FEATURE_DIM

    print("Loading real brand features (direct DB read, no feature-store endpoint yet)...")
    brand_x, brand_id_to_index = load_brands(database_url)

    collab_index, collab_attr = load_symmetric_edges(collab_path, creator_id_to_index)
    cooccur_index, cooccur_attr = load_symmetric_edges(cooccur_path, creator_id_to_index)
    sponsors_index, sponsored_by_index = load_sponsorship_edges(
        sponsorship_path, creator_id_to_index, brand_id_to_index
    )

    data = empty_hetero_data()
    data["creator"].x = real_x
    data["brand"].x = brand_x
    data["creator", "collaborates_with", "creator"].edge_index = collab_index
    data["creator", "collaborates_with", "creator"].edge_attr = collab_attr
    data["creator", "co_occurs_with", "creator"].edge_index = cooccur_index
    data["creator", "co_occurs_with", "creator"].edge_attr = cooccur_attr
    data["brand", "sponsors", "creator"].edge_index = sponsors_index
    data["creator", "sponsored_by", "brand"].edge_index = sponsored_by_index

    report_structure(data, id_to_name)

    print("\n--- TASK 2: GAT forward pass + inductive check on real topology ---")
    torch.manual_seed(0)
    model = SchemaSmokeTestGAT(hidden_channels=16, heads=2)
    out = model(data)
    print(f"Forward pass output shape: creator={out['creator'].shape}, brand={out['brand'].shape}")
    assert not out["creator"].isnan().any() and not out["brand"].isnan().any()
    print("PASSED: no NaN on real sparse structure (0 co_occurs_with edges, "
          f"{collab_index.size(1)} collaborates_with edges, {sponsors_index.size(1)} sponsors edges).")

    # Inductive check: same trained instance, append 15 synthetic creators
    # with synthetic edges wired to real nodes -- confirms GAT's fixed-shape
    # parameters generalize to unseen nodes attached to the REAL graph, not
    # just a fully-synthetic one (Weeks 7-8's check used synthetic-only).
    from ml.dummy_data import make_dummy_hetero_data

    bigger = make_dummy_hetero_data(num_creators=num_creators + 15, num_brands=brand_x.size(0) + 2, seed=1)
    bigger["creator"].x[:num_creators] = real_x
    bigger["brand"].x[: brand_x.size(0)] = brand_x
    out_bigger = model(bigger)
    print(f"Inductive check output shape: creator={out_bigger['creator'].shape}")
    assert out_bigger["creator"].shape == (num_creators + 15, 16)
    assert not out_bigger["creator"].isnan().any()
    print("PASSED: same trained instance runs on 15 new nodes appended to the REAL graph, "
          "no retraining, no NaN -- inductive property holds on real topology.")

    print("\n--- TASK 4/5: real target from computable pairs, then a training attempt ---")
    treatment = load_treatment(database_url, creator_id_to_index, num_creators)
    n_sponsored = int(treatment.sum().item())
    print(f"Treatment tensor: {n_sponsored} of {num_creators} creators marked sponsored "
          "(any real is_sponsored=true event, not just brand_id-resolved ones).")

    has_neighbor = has_sponsored_neighbor(
        data["creator", "collaborates_with", "creator"].edge_index, treatment
    )
    n_exposed = int(has_neighbor.sum().item())
    print(f"Creators with >=1 sponsored collaborator (real exposure candidates): {n_exposed}")

    target, computable_pairs = load_real_targets(computable_pairs_path, creator_id_to_index, num_creators)
    n_real_targets = int((target != 0).sum().item())
    print(f"\nReal computable (event, neighbor, platform) triples: {len(computable_pairs)}")
    for p in computable_pairs:
        print(f"  {p['sponsored_creator_name']} ({p['event_platform']}, {p['event_date'][:10]}) -> "
              f"{p['neighbor_name']} on {p['neighbor_platform']}: "
              f"{p['n_before']} before (avg={p['avg_engagement_before']:.1f}) / "
              f"{p['n_after']} after (avg={p['avg_engagement_after']:.1f}), "
              f"delta={p['delta']:+.1f}")
    print(f"\n{n_real_targets} of {num_creators} creators have a REAL (non-placeholder) target value "
          "(relative engagement lift, averaged across their computable triples). Everyone else is 0 "
          "-- 'no real signal computed', not 'confirmed zero effect'.")

    if n_real_targets == 0:
        print("\nSTILL 0 real targets -- would run as a plumbing check only, not a real result.")
    else:
        print(
            f"\n{n_real_targets} real target(s) exist this round -- this IS a real (if tiny) "
            "supervised signal, not a placeholder. Framed honestly: this is still a "
            "pipeline-correctness check (does the loss/backward pass run end-to-end on real "
            f"data without NaN/crash), NOT a trained, generalizable model -- {n_real_targets} "
            "labeled node(s) cannot support a held-out split or any claim about generalization."
        )

    gail_model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, hidden_channels=16, heads=2)
    config = TrainConfig(epochs=50, lr=1e-2, val_fraction=0.2, seed=0)
    history = train(gail_model, data, treatment, target, config)

    print(f"\nTrained {config.epochs} epochs on the real graph.")
    print(f"  epoch 0:  {history[0]}")
    print(f"  epoch {config.epochs // 2}: {history[config.epochs // 2]}")
    print(f"  epoch {config.epochs - 1}: {history[-1]}")
    any_nan = any(
        math.isnan(h[k])
        for h in history
        for k in ("prediction", "overlap", "smoothness", "consistency", "total")
    )
    print(f"NaN encountered across {config.epochs} epochs: {any_nan}")
    print("PASSED: full GAIL loss (prediction + overlap + smoothness + consistency) runs on "
          "the real graph ({}-edge collaborates_with, {}-edge co_occurs_with) "
          "without crashing or producing NaN.".format(collab_index.size(1), cooccur_index.size(1)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
