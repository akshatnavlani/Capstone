"""Tests for the completed doubly robust estimator (E3).

The tests that carry the claim are the three `test_unbiased_when_*` cases. They
construct data with a KNOWN true effect, deliberately break one nuisance model at
a time, and check the estimate survives. That is the whole point of doubly robust
estimation, and `doubly_robust_weights` alone never had it: inverse-propensity
weighting is unbiased only when the propensity model is right.
"""

from __future__ import annotations

import pytest
import torch

from ml.causal_regularization import (
    doubly_robust_effect,
    doubly_robust_pseudo_outcome,
    doubly_robust_weights,
)
from ml.gail_loss import GAILLossWeights, compute_gail_loss

TRUE_EFFECT = 5.0
N = 4000


def _synthetic(seed: int = 0):
    """Nodes whose neighbourhood treatment depends on a confounder.

    `confounder` drives BOTH the chance of having a sponsored neighbour and the
    outcome -- exactly the selection problem brands create by favouring already
    popular creators. Ignoring it inflates the apparent effect.
    """
    g = torch.Generator().manual_seed(seed)
    confounder = torch.rand(N, generator=g)
    true_propensity = 0.2 + 0.6 * confounder
    treatment = (torch.rand(N, generator=g) < true_propensity).float()
    noise = torch.randn(N, generator=g) * 0.1
    outcome = 2.0 * confounder + TRUE_EFFECT * treatment + noise
    return confounder, true_propensity, treatment, outcome


def _arms(confounder: torch.Tensor):
    """mu(exposed, X) and mu(unexposed, X) for a CORRECT outcome model.

    Both arms are evaluated at fixed exposure levels, not at observed treatment.
    That distinction is the whole reason `doubly_robust_effect` exists -- see
    `test_single_arm_form_does_not_estimate_an_effect` below.
    """
    return 2.0 * confounder + TRUE_EFFECT, 2.0 * confounder


def test_unbiased_when_outcome_model_correct_propensity_wrong():
    confounder, true_p, treatment, outcome = _synthetic()
    mu_1, mu_0 = _arms(confounder)
    wrong_p = torch.full_like(true_p, 0.5)  # ignores the confounder entirely

    est = doubly_robust_effect(mu_1, mu_0, outcome, treatment, wrong_p).mean()
    assert abs(float(est) - TRUE_EFFECT) < 0.1


def test_unbiased_when_propensity_correct_outcome_model_wrong():
    _, true_p, treatment, outcome = _synthetic()
    zero = torch.zeros_like(outcome)  # outcome model predicts nothing at all

    est = doubly_robust_effect(zero, zero, outcome, treatment, true_p).mean()
    assert abs(float(est) - TRUE_EFFECT) < 0.2


def test_unbiased_when_both_models_correct():
    confounder, true_p, treatment, outcome = _synthetic()
    mu_1, mu_0 = _arms(confounder)

    est = doubly_robust_effect(mu_1, mu_0, outcome, treatment, true_p).mean()
    assert abs(float(est) - TRUE_EFFECT) < 0.1


def test_biased_when_both_models_wrong():
    """The one failing case -- stated so the guarantee is not oversold."""
    _, _, treatment, outcome = _synthetic()
    zero = torch.zeros_like(outcome)
    wrong_p = torch.full_like(outcome, 0.5)

    est = doubly_robust_effect(zero, zero, outcome, treatment, wrong_p).mean()
    assert abs(float(est) - TRUE_EFFECT) > 0.2


def test_single_arm_form_does_not_estimate_an_effect():
    """Pins the finding that motivated `doubly_robust_effect`.

    The specification's formula evaluates mu at the OBSERVED exposure, which makes
    it a selection-corrected target for Y -- correct for the L_DR loss term, but
    not an effect estimator. Here it returns E[Y] (~3.5), not the true effect (5.0).
    """
    confounder, true_p, treatment, outcome = _synthetic()
    mu_observed = 2.0 * confounder + TRUE_EFFECT * treatment

    single = doubly_robust_pseudo_outcome(mu_observed, outcome, treatment, true_p).mean()
    assert abs(float(single) - TRUE_EFFECT) > 1.0
    assert abs(float(single) - float(outcome.mean())) < 0.2


def test_ipw_alone_is_biased_where_aipw_is_not():
    """Why the outcome arm was needed.

    With the propensity model wrong, IPW weighting cannot recover the effect,
    while AIPW can because the correct outcome model carries it.
    """
    confounder, true_p, treatment, outcome = _synthetic()
    mu_1, mu_0 = _arms(confounder)
    wrong_p = torch.full_like(true_p, 0.5)

    w = doubly_robust_weights(treatment, wrong_p)
    ipw_est = float(
        (w * treatment * outcome).sum() / (w * treatment).sum()
        - (w * (1 - treatment) * outcome).sum() / (w * (1 - treatment)).sum()
    )
    aipw_est = float(doubly_robust_effect(mu_1, mu_0, outcome, treatment, wrong_p).mean())

    assert abs(aipw_est - TRUE_EFFECT) < abs(ipw_est - TRUE_EFFECT)


def test_effect_estimator_detaches_nuisances():
    mu_1 = torch.randn(10, requires_grad=True)
    mu_0 = torch.randn(10, requires_grad=True)
    p = torch.rand(10).clamp(0.2, 0.8).requires_grad_(True)
    out = doubly_robust_effect(mu_1, mu_0, torch.randn(10), torch.ones(10), p)
    assert not out.requires_grad


def test_predict_unexposed_zeroes_exposure():
    """The counterfactual arm comes from the model itself, not a second model."""
    from ml.dummy_data import make_dummy_hetero_data
    from ml.gail_model import GAILModel
    from ml.schema import CREATOR_FEATURE_DIM

    torch.manual_seed(0)
    data = make_dummy_hetero_data(num_creators=10, num_brands=2)
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM)
    treatment = torch.zeros(data["creator"].num_nodes)
    treatment[0] = 1.0

    exposed, exposure, _ = model(data, treatment)
    unexposed = model.predict_unexposed(data)

    assert unexposed.shape == exposed.shape
    # Where exposure is genuinely zero the two arms must agree; where it is not,
    # they must differ -- otherwise the head is ignoring its exposure input.
    zero = exposure == 0
    assert torch.allclose(exposed[zero], unexposed[zero], atol=1e-5)
    assert not torch.allclose(exposed[~zero], unexposed[~zero], atol=1e-5)


def test_pseudo_outcome_detaches_nuisances():
    """Target must not carry gradient, or the model can shift both together."""
    mu = torch.randn(10, requires_grad=True)
    p = torch.rand(10).clamp(0.2, 0.8).requires_grad_(True)
    pseudo = doubly_robust_pseudo_outcome(mu, torch.randn(10), torch.ones(10), p)
    assert not pseudo.requires_grad


def test_aipw_mode_changes_the_loss():
    predicted = torch.tensor([1.0, 2.0, 3.0])
    target = torch.tensor([0.0, 0.0, 0.0])
    propensity = torch.tensor([0.5, 0.25, 0.75])
    treatment = torch.tensor([1.0, 0.0, 1.0])
    edge_index = torch.tensor([[0, 1], [1, 0]])
    edge_weight = torch.tensor([1.0, 1.0])
    mask = torch.tensor([False, False, False])
    w = GAILLossWeights(prediction=1.0, overlap=0.0, smoothness=0.0, consistency=0.0)

    ipw, _ = compute_gail_loss(
        predicted, target, propensity, edge_index, edge_weight, mask, w,
        treatment=treatment, dr_mode="ipw",
    )
    aipw, _ = compute_gail_loss(
        predicted, target, propensity, edge_index, edge_weight, mask, w,
        treatment=treatment, dr_mode="aipw",
    )
    assert abs(ipw.item() - aipw.item()) > 1e-6


def test_aipw_loss_stays_differentiable():
    predicted = torch.tensor([1.0, 2.0, 3.0], requires_grad=True)
    total, _ = compute_gail_loss(
        predicted,
        torch.tensor([0.0, 0.0, 0.0]),
        torch.tensor([0.5, 0.25, 0.75]),
        torch.tensor([[0, 1], [1, 0]]),
        torch.tensor([1.0, 1.0]),
        torch.tensor([False, False, False]),
        GAILLossWeights(prediction=1.0, overlap=0.0, smoothness=0.0, consistency=0.0),
        treatment=torch.tensor([1.0, 0.0, 1.0]),
        dr_mode="aipw",
    )
    total.backward()
    assert predicted.grad is not None
    assert torch.isfinite(predicted.grad).all()


def test_rejects_unknown_dr_mode():
    with pytest.raises(ValueError, match="dr_mode"):
        compute_gail_loss(
            torch.zeros(3), torch.zeros(3), torch.full((3,), 0.5),
            torch.tensor([[0, 1], [1, 0]]), torch.tensor([1.0, 1.0]),
            torch.tensor([False, False, False]),
            treatment=torch.ones(3), dr_mode="magic",
        )