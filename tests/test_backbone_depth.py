"""Tests for HeteroGATBackbone depth (E7) and the rename (E9).

The test that carries the change is `test_two_layers_reach_two_hops`: it builds
a path A -> B -> C and checks that information from A reaches C only when the
backbone has two layers. Under the previous single-layer model it could not,
which matters for spillover specifically — a sponsorship reaching a creator
through an intermediary was structurally invisible.
"""

from __future__ import annotations

import pytest
import torch

from ml.dummy_data import make_dummy_hetero_data
from ml.model import DEFAULT_NUM_LAYERS, HeteroGATBackbone, SchemaSmokeTestGAT
from ml.schema import CREATOR_FEATURE_DIM, empty_hetero_data


def _path_graph() -> "object":
    """A -> B -> C, with C two hops from A and no direct A-C edge."""
    data = empty_hetero_data()
    x = torch.zeros(3, CREATOR_FEATURE_DIM)
    x[0, 0] = 1.0  # a marker that only node A carries
    data["creator"].x = x
    data["brand"].x = torch.zeros(1, data["brand"].x.size(1))

    edge_index = torch.tensor([[0, 1], [1, 2]], dtype=torch.long)
    data["creator", "collaborates_with", "creator"].edge_index = edge_index
    data["creator", "collaborates_with", "creator"].edge_attr = torch.ones(2, 1)
    return data


def test_default_is_two_layers():
    assert DEFAULT_NUM_LAYERS == 2
    assert HeteroGATBackbone().num_layers == 2


def test_two_layers_reach_two_hops():
    """One hop cannot carry A's signal to C; two hops can."""
    data = _path_graph()
    torch.manual_seed(0)

    one = HeteroGATBackbone(hidden_channels=8, heads=1, num_layers=1)
    two = HeteroGATBackbone(hidden_channels=8, heads=1, num_layers=2)

    # Isolate propagation from weight differences: compare each model against
    # ITSELF with A's marker feature removed. Only a model whose receptive
    # field reaches A can respond to that change at node C.
    blanked = _path_graph()
    blanked["creator"].x[0, 0] = 0.0

    one_delta = (one(data)["creator"][2] - one(blanked)["creator"][2]).abs().max()
    two_delta = (two(data)["creator"][2] - two(blanked)["creator"][2]).abs().max()

    assert one_delta.item() == pytest.approx(0.0, abs=1e-6), (
        "single-layer backbone must NOT see two hops"
    )
    assert two_delta.item() > 1e-6, "two-layer backbone must see two hops"


def test_layer_count_is_configurable():
    for n in (1, 2, 3):
        assert HeteroGATBackbone(num_layers=n).num_layers == n


def test_rejects_zero_layers():
    with pytest.raises(ValueError, match="num_layers must be >= 1"):
        HeteroGATBackbone(num_layers=0)


def test_output_shape_unchanged_by_depth():
    data = make_dummy_hetero_data(num_creators=8, num_brands=2)
    for n in (1, 2, 3):
        out = HeteroGATBackbone(hidden_channels=16, heads=2, num_layers=n)(data)
        assert out["creator"].shape == (data["creator"].num_nodes, 16)


def test_embeddings_stay_non_negative():
    """ReLU after every layer — the exposure module and prediction head were
    both built against non-negative embeddings."""
    data = make_dummy_hetero_data(num_creators=8, num_brands=2)
    out = HeteroGATBackbone(hidden_channels=16, num_layers=3)(data)
    assert (out["creator"] >= 0).all()


def test_deprecated_alias_still_resolves():
    """Callers on other branches still import the old name."""
    assert SchemaSmokeTestGAT is HeteroGATBackbone


def test_gail_model_passes_depth_through():
    from ml.gail_model import GAILModel

    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, num_layers=3)
    assert model.backbone.num_layers == 3