from ml.dummy_data import make_dummy_hetero_data
from ml.model import SchemaSmokeTestGAT
from ml.schema import BRAND_FEATURE_DIM, CREATOR_FEATURE_DIM, EDGE_TYPES, empty_hetero_data


def test_empty_hetero_data_has_correct_structure():
    data = empty_hetero_data()
    assert set(data.node_types) == {"creator", "brand"}
    assert set(data.edge_types) == set(EDGE_TYPES)
    assert data["creator"].x.shape == (0, CREATOR_FEATURE_DIM)
    assert data["brand"].x.shape == (0, BRAND_FEATURE_DIM)


def test_dummy_hetero_data_is_valid():
    data = make_dummy_hetero_data(num_creators=6, num_brands=3)
    data.validate(raise_on_error=True)
    assert data["creator"].x.shape == (6, CREATOR_FEATURE_DIM)
    assert data["brand"].x.shape == (3, BRAND_FEATURE_DIM)


def test_weighted_creator_edges_are_symmetric_with_matching_weight():
    # GRAPH_SCHEMA.md contract: if creator A collaborated with creator B,
    # both (A,B) and (B,A) edges must be present with the SAME weight.
    data = make_dummy_hetero_data(num_creators=6, num_brands=3)
    for edge_type in [
        ("creator", "collaborates_with", "creator"),
        ("creator", "co_occurs_with", "creator"),
    ]:
        edge_index = data[edge_type].edge_index
        edge_attr = data[edge_type].edge_attr
        weight_by_pair = {}
        for (src, dst), w in zip(edge_index.t().tolist(), edge_attr.tolist()):
            weight_by_pair[(src, dst)] = w
        for (src, dst), w in weight_by_pair.items():
            assert (dst, src) in weight_by_pair, f"{edge_type}: missing reverse edge for ({src},{dst})"
            assert weight_by_pair[(dst, src)] == w, f"{edge_type}: mismatched weight for ({src},{dst})"


def test_gat_forward_pass_produces_expected_shapes():
    num_creators, num_brands = 6, 3
    data = make_dummy_hetero_data(num_creators=num_creators, num_brands=num_brands)
    model = SchemaSmokeTestGAT(hidden_channels=16, heads=2)

    out = model(data)

    assert out["creator"].shape == (num_creators, 16)
    assert out["brand"].shape == (num_brands, 16)
    assert not out["creator"].isnan().any()
    assert not out["brand"].isnan().any()
