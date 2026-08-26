import torch

from ml.dummy_data import make_dummy_hetero_data
from ml.weighted_sage_conv import WeightedSAGEConv


def test_forward_pass_produces_expected_shape():
    data = make_dummy_hetero_data(num_creators=6, num_brands=3)
    edge_index = data["creator", "collaborates_with", "creator"].edge_index
    edge_weight = data["creator", "collaborates_with", "creator"].edge_attr

    conv = WeightedSAGEConv(in_channels=data["creator"].x.size(1), out_channels=16)
    out = conv(data["creator"].x, edge_index, edge_weight)

    assert out.shape == (6, 16)
    assert not out.isnan().any()


def test_edge_weight_actually_changes_output():
    # Proves the layer consumes edge_weight (unlike stock SAGEConv, which
    # can't at all) rather than silently ignoring it.
    torch.manual_seed(0)
    x = torch.randn(4, 8)
    edge_index = torch.tensor([[0, 1, 2], [1, 0, 1]])
    conv = WeightedSAGEConv(in_channels=8, out_channels=8)

    weight_a = torch.ones(3)
    weight_b = torch.tensor([1.0, 1.0, 5.0])  # scale up edge (2->1)

    out_a = conv(x, edge_index, weight_a)
    out_b = conv(x, edge_index, weight_b)

    assert not torch.allclose(out_a, out_b)


def test_generalizes_to_a_graph_with_more_nodes_without_retraining():
    # Same check applied to the GAT smoke-test model in the self-check:
    # same trained module, larger graph, no retrain — confirms this
    # prototype layer is inductive too, same structural reason as GAT
    # (parameters are shape-fixed nn.Linear layers, not per-node lookups).
    torch.manual_seed(0)
    small = make_dummy_hetero_data(num_creators=6, num_brands=3, seed=1)
    conv = WeightedSAGEConv(in_channels=small["creator"].x.size(1), out_channels=16)
    out_small = conv(
        small["creator"].x,
        small["creator", "collaborates_with", "creator"].edge_index,
        small["creator", "collaborates_with", "creator"].edge_attr,
    )
    assert out_small.shape == (6, 16)

    big = make_dummy_hetero_data(num_creators=20, num_brands=8, seed=2)
    out_big = conv(
        big["creator"].x,
        big["creator", "collaborates_with", "creator"].edge_index,
        big["creator", "collaborates_with", "creator"].edge_attr,
    )
    assert out_big.shape == (20, 16)
