import torch

from ml.exposure import ExposureModule


def test_exposure_zero_when_no_neighbors_are_sponsored():
    torch.manual_seed(0)
    x = torch.randn(3, 8)
    # 1<->0, 2<->0, neither 0 nor the neighbors are sponsored.
    edge_index = torch.tensor([[1, 2], [0, 0]])
    treatment = torch.zeros(3)
    module = ExposureModule(in_channels=8, hidden_channels=4)

    exposure = module(x, edge_index, treatment)

    assert exposure.shape == (3,)
    assert torch.allclose(exposure, torch.zeros(3), atol=1e-6)


def test_exposure_positive_when_a_neighbor_is_sponsored():
    torch.manual_seed(0)
    x = torch.randn(3, 8)
    edge_index = torch.tensor([[1, 2], [0, 0]])  # both point into node 0
    treatment = torch.tensor([0.0, 1.0, 0.0])  # node 1 is sponsored
    module = ExposureModule(in_channels=8, hidden_channels=4)

    exposure = module(x, edge_index, treatment)

    assert exposure[0].item() > 0.0  # node 0 has a sponsored neighbor (node 1)
    assert exposure[1].item() == 0.0  # node 1 has no incoming edges at all
    assert exposure[2].item() == 0.0  # node 2 has no incoming edges at all


def test_exposure_handles_empty_edge_index_without_crashing():
    x = torch.randn(4, 8)
    edge_index = torch.empty((2, 0), dtype=torch.long)
    treatment = torch.ones(4)
    module = ExposureModule(in_channels=8, hidden_channels=4)

    exposure = module(x, edge_index, treatment)

    assert exposure.shape == (4,)
    assert torch.equal(exposure, torch.zeros(4))


def test_exposure_is_symmetric_on_a_fully_symmetric_graph():
    # 4 nodes, identical features, complete graph (all pairs, both
    # directions) -- node 0 is sponsored. Nodes 1/2/3 are structurally and
    # featurally interchangeable, so they must get identical exposure.
    torch.manual_seed(0)
    x = torch.zeros(4, 8)  # identical features -> no asymmetry from features
    pairs = [(i, j) for i in range(4) for j in range(4) if i != j]
    edge_index = torch.tensor(pairs).t()
    treatment = torch.tensor([1.0, 0.0, 0.0, 0.0])
    module = ExposureModule(in_channels=8, hidden_channels=4)

    exposure = module(x, edge_index, treatment)

    assert torch.allclose(exposure[1], exposure[2], atol=1e-6)
    assert torch.allclose(exposure[2], exposure[3], atol=1e-6)
    assert exposure[1].item() > 0.0  # each of them has sponsored neighbor 0
