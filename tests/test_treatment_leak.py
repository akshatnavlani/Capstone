"""P1: treatment must reach the prediction ONLY through the exposure input.

THE BUG. The backbone passed messages over `sponsors` / `sponsored_by`. With two
layers that is brand -> sponsored creator -> collaborator, so an UNSPONSORED
creator's embedding changed depending on whether a neighbour was sponsored.
`predict_unexposed` zeroes exposure but keeps the embedding, so the
"counterfactual" still carried the treatment. Measured before the fix: 47 of 53
unsponsored creators' embeddings moved when sponsorship edges were removed.

THE TEST. Build a graph, add sponsorship edges for the treated creators, and
check that no creator's embedding (and so no unexposed prediction) depends on
them. Under the old backbone this fails; with P1 it must pass.
"""

from __future__ import annotations

import torch

from ml.gail_model import GAILModel
from ml.schema import CREATOR_FEATURE_DIM, TREATMENT_EDGE_TYPES, empty_hetero_data


def _graph_with_and_without_sponsorship():
    torch.manual_seed(0)
    n = 12
    data = empty_hetero_data()
    data["creator"].x = torch.randn(n, CREATOR_FEATURE_DIM)
    data["brand"].x = torch.randn(1, data["brand"].x.size(1))

    # A ring plus chords, so every creator is within two hops of a treated one.
    src = torch.arange(n)
    dst = (src + 1) % n
    edge_index = torch.cat([torch.stack([src, dst]), torch.stack([dst, src])], dim=1)
    data["creator", "collaborates_with", "creator"].edge_index = edge_index
    data["creator", "collaborates_with", "creator"].edge_attr = torch.ones(edge_index.size(1), 1)

    treated = torch.tensor([0, 5])
    with_sp = data.clone()
    with_sp["brand", "sponsors", "creator"].edge_index = torch.stack(
        [torch.zeros_like(treated), treated]
    )
    with_sp["creator", "sponsored_by", "brand"].edge_index = torch.stack(
        [treated, torch.zeros_like(treated)]
    )
    return data, with_sp


def test_backbone_excludes_treatment_edges_by_default():
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM)
    for edge_type in TREATMENT_EDGE_TYPES:
        assert edge_type not in model.backbone.edge_types


def test_embeddings_do_not_depend_on_sponsorship_edges():
    without_sp, with_sp = _graph_with_and_without_sponsorship()
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM)
    model.eval()
    with torch.no_grad():
        h_without = model.backbone(without_sp)["creator"]
        h_with = model.backbone(with_sp)["creator"]
        mu0_without = model.predict_unexposed(without_sp)
        mu0_with = model.predict_unexposed(with_sp)
    assert torch.allclose(h_with, h_without)
    assert torch.allclose(mu0_with, mu0_without)


def test_leaky_mode_still_leaks():
    """Guards the test itself: if the leaky configuration stopped leaking, the
    test above would pass for the wrong reason (e.g. a graph too small to
    carry the signal)."""
    without_sp, with_sp = _graph_with_and_without_sponsorship()
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, backbone_sees_treatment=True)
    model.eval()
    with torch.no_grad():
        h_without = model.backbone(without_sp)["creator"]
        h_with = model.backbone(with_sp)["creator"]
    assert not torch.allclose(h_with, h_without)


def test_exposure_still_carries_treatment():
    """Removing the leak must not remove the intended channel: a creator next
    to a sponsored one still gets nonzero exposure, and its prediction can
    still differ from the unexposed one."""
    _, with_sp = _graph_with_and_without_sponsorship()
    treatment = torch.zeros(12)
    treatment[[0, 5]] = 1.0
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM)
    model.eval()
    with torch.no_grad():
        _, exposure, _ = model(with_sp, treatment)
    neighbours_of_treated = torch.tensor([1, 4, 6, 11])
    assert (exposure[neighbours_of_treated] > 0).all()
