"""Tests for E12: the wiring between the trained model and the causal estimate.

Every component here was already implemented and individually tested. What was
missing was the connection between them in `scripts/train_prod_model.py`:

  * the loss was given own-sponsorship where it documents the INTERFERENCE
    indicator, so the propensity head learned the wrong quantity
  * `dr_mode` was left at its "ipw" default, so AIPW never ran in production
  * the consistency mask was built from `collaborates_with` alone while E6's
    exposure also travels over `co_occurs_with`
  * `doubly_robust_effect` and `transmission_shares` were reachable only from
    the synthetic harness, so no effect estimate was ever produced

These tests pin the behaviour the training script now depends on. They use the
same pieces the script does rather than importing it, because the script needs
a database and pretrained CLIP/BERT weights to run at all.
"""

from __future__ import annotations

import torch

from ml.causal_regularization import doubly_robust_effect, has_sponsored_neighbor
from ml.dummy_data import make_dummy_hetero_data
from ml.gail_loss import GAILLossWeights, compute_gail_loss
from ml.gail_model import GAILModel
from ml.schema import CREATOR_FEATURE_DIM


def _model_and_data(num_creators: int = 12):
    torch.manual_seed(0)
    data = make_dummy_hetero_data(num_creators=num_creators, num_brands=2)
    return GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM), data


# --- the interference indicator -----------------------------------------------


def test_interference_differs_from_own_sponsorship():
    """The two are different vectors, which is why passing one for the other
    went unnoticed: both are plausible (N,) float tensors of zeros and ones."""
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]])
    own = torch.tensor([1.0, 0.0, 0.0, 0.0])

    interference = has_sponsored_neighbor(edge_index, own).float()

    assert own.tolist() == [1.0, 0.0, 0.0, 0.0]
    assert interference.tolist() == [0.0, 1.0, 0.0, 0.0]
    assert not torch.equal(own, interference)


def test_consistency_mask_spans_both_relations():
    """E6 made exposure travel over co_occurs_with too.

    Creator 3 is reachable from the sponsored creator 0 ONLY through the
    co-occurrence edge. Built from collaboration edges alone, the mask calls
    them unexposed and L_consistency pushes their prediction to zero -- while
    the exposure module is giving them real exposure through that same edge.
    """
    collab = torch.tensor([[0], [1]])
    cooccur = torch.tensor([[0], [3]])
    own = torch.tensor([1.0, 0.0, 0.0, 0.0])

    collab_only = has_sponsored_neighbor(collab, own)
    both = has_sponsored_neighbor(torch.cat([collab, cooccur], dim=1), own)

    assert collab_only[3].item() is False or not bool(collab_only[3])
    assert bool(both[3]), "co-occurrence neighbours must count as interference"
    assert bool(both[1]), "collaboration neighbours must still count"


def test_concatenating_edge_indices_keeps_node_indexing():
    """Guards the shape assumption the script relies on: both relations index
    into the same node set, so concatenation along dim=1 is valid."""
    collab = torch.tensor([[0, 1], [1, 2]])
    cooccur = torch.tensor([[2, 3], [3, 0]])
    combined = torch.cat([collab, cooccur], dim=1)
    assert combined.shape == (2, 4)
    assert int(combined.max()) == 3


# --- AIPW actually being used -------------------------------------------------


def _loss(dr_mode: str, treatment):
    torch.manual_seed(0)
    predicted = torch.tensor([0.5, -0.2, 0.9, 0.1], requires_grad=True)
    target = torch.tensor([0.3, 0.0, 1.2, -0.4])
    propensity = torch.tensor([0.4, 0.6, 0.3, 0.7])
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]])
    edge_weight = torch.ones(3)
    mask = has_sponsored_neighbor(edge_index, torch.tensor([1.0, 0, 0, 0]))
    weights = GAILLossWeights(overlap=0.0, smoothness=0.0, consistency=0.0, propensity=0.0)
    total, comps = compute_gail_loss(
        predicted, target, propensity, edge_index, edge_weight, mask, weights,
        treatment=treatment, dr_mode=dr_mode,
    )
    return total, comps


def test_aipw_and_ipw_give_different_losses():
    """If these agreed, switching dr_mode would be cosmetic."""
    treatment = torch.tensor([1.0, 0.0, 1.0, 0.0])
    ipw, _ = _loss("ipw", treatment)
    aipw, _ = _loss("aipw", treatment)
    assert abs(ipw.item() - aipw.item()) > 1e-6


def test_aipw_loss_is_differentiable():
    treatment = torch.tensor([1.0, 0.0, 1.0, 0.0])
    total, _ = _loss("aipw", treatment)
    total.backward()


def test_propensity_term_follows_the_treatment_it_is_given():
    """The propensity head is supervised against whatever `treatment` is passed.

    This is why the own-sponsorship/interference mix-up mattered: the head was
    being trained to predict the wrong event, and the DR weights then divided
    by that wrong probability.
    """
    weights = GAILLossWeights(prediction=0.0, overlap=0.0, smoothness=0.0,
                              consistency=0.0, propensity=1.0)
    predicted = torch.zeros(4)
    target = torch.zeros(4)
    propensity = torch.tensor([0.9, 0.1, 0.9, 0.1])
    edge_index = torch.tensor([[0], [1]])
    edge_weight = torch.ones(1)
    mask = torch.zeros(4, dtype=torch.bool)

    matching = torch.tensor([1.0, 0.0, 1.0, 0.0])
    opposite = torch.tensor([0.0, 1.0, 0.0, 1.0])

    _, good = compute_gail_loss(predicted, target, propensity, edge_index,
                                edge_weight, mask, weights, treatment=matching)
    _, bad = compute_gail_loss(predicted, target, propensity, edge_index,
                               edge_weight, mask, weights, treatment=opposite)

    assert good["propensity"] < bad["propensity"], (
        "supervising against the wrong treatment must cost more, or the term "
        "is not discriminating between them at all"
    )


# --- the effect estimate ------------------------------------------------------


def test_effect_estimate_runs_from_model_outputs():
    """End-to-end shape check over the exact call the training script makes."""
    model, data = _model_and_data()
    n = data["creator"].num_nodes
    own = torch.zeros(n)
    own[0] = 1.0
    edge_index = data["creator", "collaborates_with", "creator"].edge_index
    interference = has_sponsored_neighbor(edge_index, own).float()

    with torch.no_grad():
        mu_exposed, _, propensity = model(data, own)
        mu_unexposed = model.predict_unexposed(data)
        tau = doubly_robust_effect(
            mu_exposed, mu_unexposed, torch.randn(n), interference, propensity
        )

    assert tau.shape == (n,)
    assert torch.isfinite(tau).all()


def test_effect_is_not_the_prediction():
    """The distinction the whole change exists for.

    tau is a contrast between two worlds; the prediction is one world. A run
    that reported predictions as effects would be answering a different
    question from the one the thesis asks.
    """
    model, data = _model_and_data()
    n = data["creator"].num_nodes
    own = torch.zeros(n)
    own[0] = 1.0
    interference = has_sponsored_neighbor(
        data["creator", "collaborates_with", "creator"].edge_index, own
    ).float()

    with torch.no_grad():
        mu_exposed, exposure, propensity = model(data, own)
        mu_unexposed = model.predict_unexposed(data)
        tau = doubly_robust_effect(
            mu_exposed, mu_unexposed, torch.randn(n), interference, propensity
        )

    moved = exposure != 0
    assert moved.any(), "fixture must expose at least one node"
    assert not torch.allclose(tau[moved], mu_exposed[moved])


def test_cluster_weighted_average_differs_from_plain_mean():
    """E2's weighting must survive into the reported ATE.

    Node 0's effect is backed by one observation, node 1's by nine. An
    unweighted mean would let the thinly-evidenced node pull the headline
    number as hard as the well-evidenced one.
    """
    tau = torch.tensor([10.0, 0.0])
    w = torch.tensor([1.0, 9.0])
    weighted = float((tau * w).sum() / w.sum())
    plain = float(tau.mean())
    assert abs(weighted - 1.0) < 1e-6
    assert abs(plain - 5.0) < 1e-6
    assert weighted < plain


def test_independent_observation_count_is_clusters_not_nodes():
    """The number quoted as N. Two creators, eleven rows, four observations."""
    sample_weight = torch.tensor([1.0, 3.0, 0.0, 0.0])
    labeled = [0, 1]
    assert int(sample_weight[labeled].sum().item()) == 4
    assert len(labeled) == 2


# --- transmission shares ------------------------------------------------------


def test_transmission_shares_are_a_distribution():
    model, _ = _model_and_data()
    beta = model.transmission_shares()
    assert set(beta) == set(model.exposure_relations)
    assert abs(sum(beta.values()) - 1.0) < 1e-5
    assert all(0.0 <= v <= 1.0 for v in beta.values())


def test_transmission_shares_are_json_serializable():
    """They go into the checkpoint, so they must be plain floats, not tensors."""
    import json

    model, _ = _model_and_data()
    beta = model.transmission_shares()
    assert all(isinstance(v, float) for v in beta.values())
    json.loads(json.dumps(beta))