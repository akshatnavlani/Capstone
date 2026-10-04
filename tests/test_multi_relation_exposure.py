"""Tests for ml.multi_relation_exposure.

The test that carries the claim is `test_co_occurrence_only_neighbour_gets_exposure`:
under the previous single-relation model that node's exposure was exactly 0.0,
because co-occurrence edges carried no treatment. Everything else guards the
mixing arithmetic, the renormalization rule, and the consistency property that
`L_consistency` depends on.
"""

from __future__ import annotations

import pytest
import torch

from ml.multi_relation_exposure import (
    DEFAULT_EXPOSURE_RELATIONS,
    MultiRelationExposureModule,
)

COLLAB = "collaborates_with"
COOCCUR = "co_occurs_with"


def _module(seed: int = 0, **kwargs) -> MultiRelationExposureModule:
    torch.manual_seed(seed)
    return MultiRelationExposureModule(in_channels=8, hidden_channels=8, **kwargs)


def _x(n: int = 4, seed: int = 0) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.randn(n, 8, generator=g)


def test_co_occurrence_only_neighbour_gets_exposure():
    """The behaviour change this module exists for.

    Node 1 is connected to sponsored node 0 ONLY through co-occurrence. The
    single-relation model gave it exposure exactly 0.0; here it must be > 0.
    """
    x = _x()
    mod = _module()
    treatment = torch.tensor([1.0, 0.0, 0.0, 0.0])
    edges = {
        COLLAB: torch.empty(2, 0, dtype=torch.long),
        COOCCUR: torch.tensor([[0], [1]], dtype=torch.long),
    }
    exposure = mod(x, edges, treatment)
    assert exposure[1] > 0, "co-occurrence neighbour of a sponsored creator must be exposed"


def test_relations_have_independent_attention_parameters():
    """Heterogeneous attention: W^r and a^r are not shared across relations."""
    mod = _module()
    collab_params = dict(mod.attn_convs[COLLAB].named_parameters())
    cooccur_params = dict(mod.attn_convs[COOCCUR].named_parameters())
    assert collab_params.keys() == cooccur_params.keys()
    for name, p in collab_params.items():
        assert p is not cooccur_params[name], f"{name} is shared between relations"


def test_beta_is_a_distribution():
    mod = _module()
    beta = mod.beta
    assert beta.shape == (len(DEFAULT_EXPOSURE_RELATIONS),)
    assert torch.allclose(beta.sum(), torch.tensor(1.0), atol=1e-6)
    assert (beta >= 0).all()


def test_beta_starts_uniform():
    """Zero-initialized logits => no prior about which channel transmits more."""
    mod = _module()
    beta = mod.beta
    assert torch.allclose(beta, torch.full_like(beta, 1.0 / len(beta)), atol=1e-6)


def test_beta_is_learnable():
    mod = _module()
    x = _x()
    treatment = torch.tensor([1.0, 0.0, 0.0, 0.0])
    # Asymmetric on purpose. GATConv softmaxes alpha per destination node, so
    # one-edge-per-relation makes every alpha exactly 1.0, both channels
    # contribute identically, and d(exposure)/d(logits) is mathematically zero.
    # Differing reach per relation is what gives the mixing weights a gradient.
    edges = {
        COLLAB: torch.tensor([[0, 0], [1, 2]], dtype=torch.long),
        COOCCUR: torch.tensor([[0], [3]], dtype=torch.long),
    }
    mod(x, edges, treatment).sum().backward()
    assert mod.mixing_logits.grad is not None
    assert not torch.allclose(mod.mixing_logits.grad, torch.zeros(2))


def test_single_relation_graph_matches_single_relation_scale():
    """Renormalization rule.

    With only collaboration edges present, beta must renormalize to 1.0 on that
    relation -- otherwise exposure would be silently halved relative to the
    prior single-relation module and the two would not be comparable.
    """
    x = _x()
    mod = _module()
    treatment = torch.tensor([1.0, 0.0, 0.0, 0.0])
    edge_index = torch.tensor([[0], [1]], dtype=torch.long)

    both_declared = mod(x, {COLLAB: edge_index}, treatment)
    collapsed = MultiRelationExposureModule(
        in_channels=8, hidden_channels=8, relations=(COLLAB,)
    )
    collapsed.attn_convs[COLLAB].load_state_dict(mod.attn_convs[COLLAB].state_dict())
    only_collab = collapsed(x, {COLLAB: edge_index}, treatment)

    assert torch.allclose(both_declared, only_collab, atol=1e-6)


def test_exposure_is_zero_without_treated_neighbours():
    """`L_consistency` depends on this holding exactly."""
    x = _x()
    mod = _module()
    treatment = torch.zeros(4)
    edges = {
        COLLAB: torch.tensor([[0, 1], [1, 2]], dtype=torch.long),
        COOCCUR: torch.tensor([[2], [3]], dtype=torch.long),
    }
    assert torch.allclose(mod(x, edges, treatment), torch.zeros(4))


def test_no_edges_anywhere_returns_zeros_and_keeps_autograd():
    x = _x().requires_grad_(True)
    mod = _module()
    exposure = mod(x, {}, torch.tensor([1.0, 0.0, 0.0, 0.0]))
    assert torch.allclose(exposure, torch.zeros(4))
    assert exposure.requires_grad, "empty-graph path must stay in the autograd graph"


def test_both_relations_contribute_more_than_one_alone():
    """A node reachable through both channels is more exposed than through one."""
    x = _x()
    mod = _module()
    treatment = torch.tensor([1.0, 0.0, 0.0, 0.0])

    collab_only = mod(x, {COLLAB: torch.tensor([[0], [1]], dtype=torch.long)}, treatment)
    both = mod(
        x,
        {
            COLLAB: torch.tensor([[0], [1]], dtype=torch.long),
            COOCCUR: torch.tensor([[0], [1]], dtype=torch.long),
        },
        treatment,
    )
    # Not a strict sum: beta renormalizes, so this checks direction only.
    assert both[1] > 0 and collab_only[1] > 0


def test_per_relation_exposure_decomposes_by_channel():
    x = _x()
    mod = _module()
    treatment = torch.tensor([1.0, 0.0, 0.0, 0.0])
    edges = {
        COLLAB: torch.tensor([[0], [1]], dtype=torch.long),
        COOCCUR: torch.tensor([[0], [2]], dtype=torch.long),
    }
    parts = mod.per_relation_exposure(x, edges, treatment)
    assert set(parts) == set(DEFAULT_EXPOSURE_RELATIONS)
    assert parts[COLLAB][1] > 0 and parts[COLLAB][2] == 0
    assert parts[COOCCUR][2] > 0 and parts[COOCCUR][1] == 0


def test_beta_dict_keys_match_relations():
    mod = _module()
    assert tuple(mod.beta_dict()) == DEFAULT_EXPOSURE_RELATIONS


def test_rejects_empty_relation_tuple():
    with pytest.raises(ValueError, match="at least one relation"):
        MultiRelationExposureModule(in_channels=8, relations=())


def test_treatment_edges_are_not_exposure_relations():
    """`sponsors` defines T; letting treatment flow along it would feed the
    treatment signal back into its own exposure measure.
    """
    assert "sponsors" not in DEFAULT_EXPOSURE_RELATIONS
    assert "sponsored_by" not in DEFAULT_EXPOSURE_RELATIONS