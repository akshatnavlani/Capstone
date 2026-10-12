"""Tests for cluster-derived targets and sample weights (E2, second half).

`per_creator_targets` turns clustered rows into one target per creator plus the
number of independent observations behind it; `sample_weight` in the loss makes
that count matter during training.

The case that carries the change is
`test_repeated_measurement_does_not_outweigh_independent_events`: before this,
a creator whose single engagement change was recorded sixteen times trained with
the same influence as one backed by three separate events.
"""

from __future__ import annotations

import torch

from ml.gail_loss import GAILLossWeights, compute_gail_loss
from ml.target_clustering import per_creator_targets

KOHLI = "kohli"
SHARMA = "sharma"
_EDGE_INDEX = torch.tensor([[0, 1], [1, 0]])
_EDGE_WEIGHT = torch.tensor([1.0, 1.0])
_NO_NBR = torch.tensor([False, False, False])


def _row(neighbour: str, day: int, lift: float) -> dict:
    return {
        "neighbour_id": neighbour,
        "event_date": f"2026-08-{day:02d}",
        "mean_lift": lift,
    }


# --- per_creator_targets ------------------------------------------------------


def test_repeated_measurement_counts_as_one_observation():
    """16 rows two days apart are one engagement change, so weight 1."""
    rows = [_row(KOHLI, 1 + 2 * i, 0.5) for i in range(8)]  # within one window
    out = per_creator_targets(rows)
    target, n_clusters = out[KOHLI]
    assert n_clusters == 1
    assert abs(target - 0.5) < 1e-9


def test_separate_events_count_separately():
    rows = [
        {"neighbour_id": SHARMA, "event_date": "2026-01-01", "mean_lift": 0.2},
        {"neighbour_id": SHARMA, "event_date": "2026-06-01", "mean_lift": 0.4},
        {"neighbour_id": SHARMA, "event_date": "2026-11-01", "mean_lift": 0.6},
    ]
    target, n_clusters = per_creator_targets(rows)[SHARMA]
    assert n_clusters == 3
    assert abs(target - 0.4) < 1e-9  # mean of the three


def test_within_cluster_averaging_then_across():
    """Two readings of one change, plus a separate change months later.

    The target must be the mean of the two CLUSTER values (0.3 and 0.9), not
    the mean of the three raw rows (0.5) -- otherwise the repeated cluster
    pulls the target toward itself simply for having been measured twice.
    """
    rows = [
        _row(KOHLI, 1, 0.2),
        _row(KOHLI, 3, 0.4),   # same cluster as above -> 0.3
        {"neighbour_id": KOHLI, "event_date": "2026-12-01", "mean_lift": 0.9},
    ]
    target, n_clusters = per_creator_targets(rows)[KOHLI]
    assert n_clusters == 2
    assert abs(target - 0.6) < 1e-9
    assert abs(target - 0.5) > 1e-3  # NOT the raw-row mean


def test_rows_without_a_lift_are_skipped_not_zeroed():
    """Cross-platform-only straddles have no same-platform lift. Counting them
    as zero would drag every target toward zero."""
    rows = [_row(KOHLI, 1, 0.5), {"neighbour_id": KOHLI, "event_date": "2026-12-01", "mean_lift": None}]
    target, n_clusters = per_creator_targets(rows)[KOHLI]
    assert n_clusters == 1
    assert abs(target - 0.5) < 1e-9


def test_separate_creators_are_independent():
    rows = [_row(KOHLI, 1, 0.5), _row(SHARMA, 1, 0.1)]
    out = per_creator_targets(rows)
    assert set(out) == {KOHLI, SHARMA}
    assert out[KOHLI][1] == 1 and out[SHARMA][1] == 1


def test_empty_input():
    assert per_creator_targets([]) == {}


# --- sample_weight in the loss ------------------------------------------------


def _loss(sample_weight, predicted, target):
    weights = GAILLossWeights(prediction=1.0, overlap=0.0, smoothness=0.0,
                              consistency=0.0, propensity=0.0)
    total, _ = compute_gail_loss(
        predicted, target, torch.full((3,), 0.5),
        _EDGE_INDEX, _EDGE_WEIGHT, _NO_NBR, weights,
        sample_weight=sample_weight,
    )
    return total


def test_repeated_measurement_does_not_outweigh_independent_events():
    """The behaviour change.

    Node 0 is backed by ONE observation, node 1 by THREE. Node 1's error should
    dominate. Without weights both count equally.
    """
    predicted = torch.tensor([1.0, 1.0, 0.0])
    target = torch.zeros(3)

    unweighted = _loss(None, predicted, target)
    weighted = _loss(torch.tensor([1.0, 3.0, 0.0]), predicted, target)
    assert weighted > unweighted, "the better-evidenced node must carry more weight"


def test_uniform_weights_match_the_unweighted_loss():
    """Normalisation guard: all-equal weights must not change the scale, or
    the prediction term would silently retune against the other loss terms."""
    predicted = torch.tensor([1.0, 2.0, 3.0])
    target = torch.zeros(3)
    assert abs(_loss(None, predicted, target).item()
               - _loss(torch.full((3,), 5.0), predicted, target).item()) < 1e-5


def test_zero_weight_node_is_excluded():
    predicted = torch.tensor([0.0, 0.0, 99.0])
    target = torch.zeros(3)
    # Node 2 has a huge error but zero evidence behind it.
    assert _loss(torch.tensor([1.0, 1.0, 0.0]), predicted, target).item() < 1e-6


def test_weights_work_in_aipw_mode():
    predicted = torch.tensor([1.0, 1.0, 0.0], requires_grad=True)
    weights = GAILLossWeights(prediction=1.0, overlap=0.0, smoothness=0.0,
                              consistency=0.0, propensity=0.0)
    total, _ = compute_gail_loss(
        predicted, torch.zeros(3), torch.full((3,), 0.5),
        _EDGE_INDEX, _EDGE_WEIGHT, _NO_NBR, weights,
        treatment=torch.tensor([1.0, 0.0, 1.0]), dr_mode="aipw",
        sample_weight=torch.tensor([1.0, 3.0, 0.0]),
    )
    total.backward()
    assert predicted.grad is not None
    assert torch.isfinite(predicted.grad).all()


def test_weights_work_in_ipw_mode():
    weights = GAILLossWeights(prediction=1.0, overlap=0.0, smoothness=0.0,
                              consistency=0.0, propensity=0.0)
    args = (torch.tensor([1.0, 1.0, 0.0]), torch.zeros(3), torch.tensor([0.5, 0.25, 0.75]),
            _EDGE_INDEX, _EDGE_WEIGHT, _NO_NBR, weights)
    plain, _ = compute_gail_loss(*args, treatment=torch.tensor([1.0, 0.0, 1.0]), dr_mode="ipw")
    weighted, _ = compute_gail_loss(*args, treatment=torch.tensor([1.0, 0.0, 1.0]),
                                    dr_mode="ipw", sample_weight=torch.tensor([1.0, 3.0, 0.0]))
    assert abs(plain.item() - weighted.item()) > 1e-6


def test_no_sample_weight_keeps_previous_behaviour():
    """Callers that pass nothing must be unaffected."""
    weights = GAILLossWeights(prediction=1.0, overlap=0.0, smoothness=0.0,
                              consistency=0.0, propensity=0.0)
    total, comps = compute_gail_loss(
        torch.tensor([1.0, 2.0, 3.0]), torch.zeros(3), torch.full((3,), 0.5),
        _EDGE_INDEX, _EDGE_WEIGHT, _NO_NBR, weights,
    )
    expected = torch.tensor([1.0, 2.0, 3.0]).pow(2).mean()
    assert abs(total.item() - expected.item()) < 1e-6
    assert abs(comps["prediction"] - expected.item()) < 1e-6