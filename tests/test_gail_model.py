import torch

from ml.dummy_data import make_dummy_hetero_data
from ml.gail_model import GAILModel


def test_forward_pass_shapes():
    data = make_dummy_hetero_data(num_creators=6, num_brands=3)
    treatment = torch.zeros(6)
    treatment[0] = 1.0
    model = GAILModel(creator_feature_dim=data["creator"].x.size(1), hidden_channels=16, heads=2)

    prediction, exposure, propensity = model(data, treatment)

    assert prediction.shape == (6,)
    assert exposure.shape == (6,)
    assert propensity.shape == (6,)
    assert not prediction.isnan().any()
    assert not exposure.isnan().any()
    assert (propensity >= 0).all() and (propensity <= 1).all()


def test_forward_pass_with_zero_collaboration_edges():
    # The real graph's current actual state (0 real collaboration edges) --
    # must not crash the full model, not just the loss function in isolation.
    data = make_dummy_hetero_data(num_creators=5, num_brands=2, avg_degree=0)
    treatment = torch.zeros(5)
    model = GAILModel(creator_feature_dim=data["creator"].x.size(1), hidden_channels=16, heads=2)

    prediction, exposure, propensity = model(data, treatment)

    assert prediction.shape == (5,)
    assert torch.equal(exposure, torch.zeros(5))
