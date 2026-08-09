import torch

from ml.causal_regularization import (
    PropensityScoreModel,
    consistency_penalty,
    doubly_robust_weights,
    has_sponsored_neighbor,
    laplacian_smoothness_penalty,
    overlap_penalty,
)
from ml.dummy_data import make_dummy_hetero_data
from ml.schema import CREATOR_FEATURE_DIM


def test_propensity_model_output_in_unit_interval():
    model = PropensityScoreModel(in_dim=CREATOR_FEATURE_DIM, hidden_dim=16)
    x = torch.randn(10, CREATOR_FEATURE_DIM)
    out = model(x)
    assert out.shape == (10,)
    assert (out >= 0).all() and (out <= 1).all()


def test_propensity_model_plain_logistic_regression_variant():
    model = PropensityScoreModel(in_dim=CREATOR_FEATURE_DIM, hidden_dim=None)
    x = torch.randn(5, CREATOR_FEATURE_DIM)
    out = model(x)
    assert out.shape == (5,)


def test_overlap_penalty_zero_when_scores_centered():
    scores = torch.full((10,), 0.5)
    assert overlap_penalty(scores).item() == 0.0


def test_overlap_penalty_positive_for_extreme_scores():
    scores = torch.tensor([0.001, 0.999, 0.5])
    penalty = overlap_penalty(scores, eps=0.05)
    assert penalty.item() > 0.0


def test_doubly_robust_weights_matches_manual_calc():
    treatment = torch.tensor([1.0, 0.0])
    propensity = torch.tensor([0.5, 0.25])
    weights = doubly_robust_weights(treatment, propensity, clip_eps=0.0)
    # treated: 1/p = 1/0.5 = 2.0 ; untreated: 1/(1-p) = 1/0.75 = 1.333...
    expected = torch.tensor([2.0, 1.0 / 0.75])
    assert torch.allclose(weights, expected, atol=1e-5)


def test_doubly_robust_weights_clips_extreme_propensity():
    treatment = torch.tensor([1.0])
    propensity = torch.tensor([0.0])  # would divide by zero unclipped
    weights = doubly_robust_weights(treatment, propensity, clip_eps=0.05)
    assert torch.isfinite(weights).all()


def test_laplacian_smoothness_penalty_zero_for_constant_values():
    node_values = torch.full((4,), 3.0)
    edge_index = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]])
    edge_weight = torch.tensor([1.0, 1.0, 0.5, 0.5])
    penalty = laplacian_smoothness_penalty(node_values, edge_index, edge_weight)
    assert penalty.item() == 0.0


def test_laplacian_smoothness_penalty_positive_for_varying_values():
    node_values = torch.tensor([0.0, 10.0, 0.0])
    edge_index = torch.tensor([[0, 1], [1, 0]])
    edge_weight = torch.tensor([1.0, 1.0])
    penalty = laplacian_smoothness_penalty(node_values, edge_index, edge_weight)
    assert penalty.item() > 0.0


def test_laplacian_smoothness_penalty_zero_not_nan_for_empty_edges():
    # Real bug found 2026-08-10 while wiring this into ml/gail_loss.py:
    # .mean() over an empty tensor is NaN, and 0 real collaboration edges
    # is the actual live-data state right now, not a hypothetical.
    node_values = torch.randn(5)
    edge_index = torch.empty((2, 0), dtype=torch.long)
    edge_weight = torch.empty((0, 1))
    penalty = laplacian_smoothness_penalty(node_values, edge_index, edge_weight)
    assert penalty.item() == 0.0


def test_has_sponsored_neighbor_and_consistency_penalty_hand_built_graph():
    # 3 creators: 0 is sponsored, 1 collaborates with 0 (has a sponsored
    # neighbor, namely 0), 2 has no collaborations at all (no sponsored
    # neighbor). Note "has_sponsored_neighbor" is about a node's NEIGHBORS,
    # not the node itself — 0 is sponsored but its only neighbor (1) isn't,
    # so 0 also has no sponsored neighbor and should be penalized too.
    creator_is_sponsored = torch.tensor([1.0, 0.0, 0.0])
    collab_edge_index = torch.tensor([[0, 1], [1, 0]])  # 0<->1 collaboration

    neighbor_flags = has_sponsored_neighbor(collab_edge_index, creator_is_sponsored)
    assert neighbor_flags.tolist() == [False, True, False]

    exposure = torch.tensor([0.9, 0.7, 0.6])  # nodes 0 and 2 wrongly have nonzero exposure
    penalty = consistency_penalty(exposure, neighbor_flags)
    # nodes 0 and 2 (no sponsored neighbor) contribute: mean(0.9^2, 0.6^2) = 0.585
    assert torch.allclose(penalty, torch.tensor(0.585), atol=1e-5)


def test_consistency_penalty_zero_when_all_nodes_have_sponsored_neighbor():
    exposure = torch.tensor([5.0, 5.0])
    all_true = torch.tensor([True, True])
    assert consistency_penalty(exposure, all_true).item() == 0.0


def test_regularization_terms_run_end_to_end_on_dummy_hetero_data():
    # Integration check against the actual schema-generated graph, not just
    # hand-built examples — confirms shapes/dtypes from ml/dummy_data.py are
    # actually compatible with every regularization function.
    data = make_dummy_hetero_data(num_creators=8, num_brands=3, seed=1)
    num_creators = data["creator"].x.size(0)

    propensity_model = PropensityScoreModel(in_dim=CREATOR_FEATURE_DIM, hidden_dim=16)
    propensity = propensity_model(data["creator"].x)
    assert overlap_penalty(propensity).item() >= 0.0

    # Stand-in treatment label: a creator counts as "sponsored" if it has an
    # incoming `sponsors` edge from any brand. Real is_sponsored labels are
    # Track C's Weeks 7-8 deliverable per GRAPH_SCHEMA.md; this is only a
    # placeholder so the regularization terms have something to run against.
    sponsor_edge_index = data["brand", "sponsors", "creator"].edge_index
    creator_is_sponsored = torch.zeros(num_creators)
    creator_is_sponsored[sponsor_edge_index[1]] = 1.0

    treatment_weights = doubly_robust_weights(creator_is_sponsored, propensity)
    assert treatment_weights.shape == (num_creators,)
    assert torch.isfinite(treatment_weights).all()

    collab_edge_index = data["creator", "collaborates_with", "creator"].edge_index
    collab_edge_weight = data["creator", "collaborates_with", "creator"].edge_attr
    fake_exposure = torch.rand(num_creators)
    smoothness = laplacian_smoothness_penalty(fake_exposure, collab_edge_index, collab_edge_weight)
    assert smoothness.item() >= 0.0

    neighbor_flags = has_sponsored_neighbor(collab_edge_index, creator_is_sponsored)
    consistency = consistency_penalty(fake_exposure, neighbor_flags)
    assert consistency.item() >= 0.0
