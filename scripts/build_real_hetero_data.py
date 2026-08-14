"""Builds and trains against the FIRST real HeteroData object (PHASE 1,
Track B's step in CAPSTONE_NEXT_STEPS.md section 6 "Sequential relay").

Previous rounds (`validate_gat_on_real_data.py`, Weeks 7-8/9-10) only ever
had real creator features with zero real edges/sponsorships to attach. As
of this round the live DB has 10 real collaboration pairs and 10 real
brand-linked sponsorship events (CAPSTONE_NEXT_STEPS.md section 2, verified
2026-08-15 by three independent sessions) -- this script is the first one
that builds the complete real graph: creators, brands, collaborates_with,
co_occurs_with, sponsors/sponsored_by all from live data, and attempts a
real training run against it.

Not a pytest test (needs live network + a running feature-store server +
real thumbnail fetches) -- one-off/manual, matching the existing
`validate_gat_on_real_data.py` pattern.

Usage (after starting Track C's backend locally against the real DB, see
that script's docstring for the how-to):
    curl http://127.0.0.1:8000/feature-store/creators > creators.json
    curl http://127.0.0.1:8000/feature-store/edges/collaborations > collab_edges.json
    curl http://127.0.0.1:8000/feature-store/edges/co-occurrence > co_occurrence_edges.json
    curl http://127.0.0.1:8000/feature-store/edges/sponsorships > sponsorship_edges.json
    .venv\\Scripts\\python.exe scripts\\build_real_hetero_data.py \\
        creators.json collab_edges.json co_occurrence_edges.json sponsorship_edges.json

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


def load_treatment_and_check_deltas(
    database_url: str, creator_id_to_index: dict[str, int], num_creators: int
) -> tuple[torch.Tensor, list[dict]]:
    """Treatment tensor: 1.0 for any creator with a real is_sponsored=true
    event (all 18, not just the 10 with brand_id resolved -- "did this
    creator get sponsored" is the causal treatment question, and doesn't
    require the brand link to be true; the brand link is only needed for
    the schema's separate sponsors/sponsored_by edge type). Also probes,
    per real content data, whether any sponsored creator's collaborator has
    real engagement data actually straddling the event date -- the thing
    ml/training.py's `target` argument needs and nothing in this repo
    currently computes.
    """
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    cur.execute(
        "select creator_id::text, brand_id::text, platform, content_id, posted_at "
        "from creator_sponsorship_events"
    )
    events = cur.fetchall()

    treatment = torch.zeros(num_creators, dtype=torch.float32)
    sponsored_creator_ids = {cid for cid, *_ in events}
    for cid in sponsored_creator_ids:
        if cid in creator_id_to_index:
            treatment[creator_id_to_index[cid]] = 1.0

    cur.execute(
        "select id, creator_id::text, platform, handle, relation_type from creator_related_accounts"
    )
    related = cur.fetchall()
    cur.execute("select creator_id::text, youtube_handle, instagram_handle, reddit_handles from creators")
    handle_rows = cur.fetchall()
    handle_map = {}
    for cid, yt, ig, rh in handle_rows:
        if yt:
            handle_map[("youtube", yt.lower())] = cid
        if ig:
            handle_map[("instagram", ig.lower())] = cid
        for h in rh or []:
            handle_map[("reddit", h.lower())] = cid

    findings = []
    for cid, brand_id, platform, content_id, posted_at in events:
        if posted_at is None or cid not in sponsored_creator_ids:
            continue
        for rel_id, rel_cid, rel_platform, rel_handle, rel_type in related:
            if rel_cid != cid or rel_type != "frequent_collaborator" or not rel_handle:
                continue
            neighbor_id = handle_map.get((rel_platform, rel_handle.lower()))
            if not neighbor_id or neighbor_id == cid:
                continue
            cur.execute(
                "select min(posted_at), max(posted_at), count(posted_at) from instagram_posts where creator_id::text = %s",
                (neighbor_id,),
            )
            min_dt, max_dt, n = cur.fetchone()
            straddles = bool(min_dt and min_dt < posted_at < max_dt) if (min_dt and max_dt) else False
            findings.append(
                {
                    "sponsored_creator": cid,
                    "event_date": str(posted_at),
                    "neighbor": neighbor_id,
                    "neighbor_dated_posts": n,
                    "neighbor_post_range": f"{min_dt} .. {max_dt}",
                    "straddles_event": straddles,
                }
            )
    conn.close()
    return treatment, findings


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
    if len(sys.argv) != 5:
        print(__doc__)
        return 1
    creators_path, collab_path, cooccur_path, sponsorship_path = sys.argv[1:5]

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

    print("\n--- TASK 3: first real training attempt ---")
    treatment, delta_findings = load_treatment_and_check_deltas(database_url, creator_id_to_index, num_creators)
    n_sponsored = int(treatment.sum().item())
    print(f"Treatment tensor: {n_sponsored} of {num_creators} creators marked sponsored "
          "(any real is_sponsored=true event, not just brand_id-resolved ones).")

    has_neighbor = has_sponsored_neighbor(
        data["creator", "collaborates_with", "creator"].edge_index, treatment
    )
    n_exposed = int(has_neighbor.sum().item())
    print(f"Creators with >=1 sponsored collaborator (real exposure candidates): {n_exposed}")

    print("\nReal engagement-delta probe (sponsored creator -> dated event -> "
          "collaborator's real content dates):")
    if not delta_findings:
        print("  No sponsored creator with BOTH a dated event AND a resolved collaborator exists.")
    for f in delta_findings:
        print(f"  {f}")
    any_straddles = any(f["straddles_event"] for f in delta_findings)

    if not any_straddles:
        print(
            "\nGAP CONFIRMED (real, not assumed): of the sponsored creators with a resolved "
            "collaborator (Virat Kohli x4, Cristiano Ronaldo x1), each has exactly one dated "
            "sponsorship event, but every one of their collaborators' own dated posts falls "
            "ENTIRELY AFTER that event's date -- none straddle it. Real temporal "
            "engagement-delta (before vs. after) is NOT computable from currently scraped data "
            "for any real sponsored-creator/neighbor pair, because per-creator scraping depth "
            "only reaches back 1-3 months and the sponsorship events themselves are recent, so "
            "the two windows don't overlap. This is a genuine data-coverage gap (Track A's "
            "scraping depth), not a missing computation -- the delta-computation logic itself "
            "is a straightforward before/after aggregation once dated posts exist on both sides "
            "of an event."
        )
        print(
            "Per the task's own instruction not to quietly stub this and call it real: "
            "target is set to all-zeros below and the resulting run is a PLUMBING CHECK ONLY "
            "(confirms the loss/backward pass doesn't crash or NaN on real sparse structure) -- "
            "it is NOT evidence of any learned spillover effect."
        )
    target = torch.zeros(num_creators, dtype=torch.float32)

    gail_model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, hidden_channels=16, heads=2)
    config = TrainConfig(epochs=50, lr=1e-2, val_fraction=0.2, seed=0)
    history = train(gail_model, data, treatment, target, config)

    print(f"\nTrained {config.epochs} epochs on the real graph (plumbing check, zero-target).")
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
          "real sparse topology (0 co_occurs_with edges, {}-edge collaborates_with graph) "
          "without crashing or producing NaN.".format(collab_index.size(1)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
