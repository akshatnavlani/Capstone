import torch

from ml.gail_loss import GAILLossWeights, compute_gail_loss


def test_combined_loss_shape_and_components():
    torch.manual_seed(0)
    predicted = torch.randn(5)
    target = torch.randn(5)
    propensity = torch.rand(5)
    edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]])
    edge_weight = torch.tensor([1.0, 1.0, 0.5, 0.5])
    has_sponsored_neighbor_mask = torch.tensor([True, True, False, True, True])

    total, components = compute_gail_loss(
        predicted, target, propensity, edge_index, edge_weight, has_sponsored_neighbor_mask
    )

    assert total.dim() == 0
    assert not torch.isnan(total)
    for key in ("prediction", "overlap", "smoothness", "consistency", "total"):
        assert key in components


def test_perfect_prediction_symmetric_graph_gives_near_zero_loss():
    # Predicted == target (zero prediction loss), constant node values
    # (zero smoothness), centered propensity (zero overlap), all nodes have
    # a sponsored neighbor (zero consistency) -- every term should vanish.
    predicted = torch.full((4,), 2.0)
    target = torch.full((4,), 2.0)
    propensity = torch.full((4,), 0.5)
    edge_index = torch.tensor([[0, 1], [1, 0]])
    edge_weight = torch.tensor([1.0, 1.0])
    has_sponsored_neighbor_mask = torch.tensor([True, True, True, True])

    total, components = compute_gail_loss(
        predicted, target, propensity, edge_index, edge_weight, has_sponsored_neighbor_mask
    )

    assert abs(total.item()) < 1e-6
    assert all(abs(v) < 1e-6 for v in components.values())


def test_zero_weight_isolates_prediction_term_only():
    predicted = torch.tensor([1.0, 2.0, 3.0])
    target = torch.tensor([0.0, 0.0, 0.0])
    propensity = torch.tensor([0.001, 0.999, 0.5])  # would normally trigger overlap penalty
    edge_index = torch.tensor([[0, 1], [1, 0]])
    edge_weight = torch.tensor([1.0, 1.0])
    has_sponsored_neighbor_mask = torch.tensor([False, False, False])  # would normally trigger consistency

    weights = GAILLossWeights(prediction=1.0, overlap=0.0, smoothness=0.0, consistency=0.0)
    total, components = compute_gail_loss(
        predicted, target, propensity, edge_index, edge_weight, has_sponsored_neighbor_mask, weights
    )

    expected_prediction_loss = ((predicted - target) ** 2).mean().item()
    assert abs(total.item() - expected_prediction_loss) < 1e-6


def test_handles_empty_collaboration_edges_without_nan():
    # The real graph's actual current state (0 real collaboration edges) --
    # must not silently produce NaN and poison the whole loss.
    predicted = torch.randn(3)
    target = torch.randn(3)
    propensity = torch.rand(3)
    edge_index = torch.empty((2, 0), dtype=torch.long)
    edge_weight = torch.empty((0, 1))
    has_sponsored_neighbor_mask = torch.tensor([False, False, False])

    total, components = compute_gail_loss(
        predicted, target, propensity, edge_index, edge_weight, has_sponsored_neighbor_mask
    )

    assert not torch.isnan(total)
    assert components["smoothness"] == 0.0
