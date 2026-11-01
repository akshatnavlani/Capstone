"""Placebo (pre-trend) penalty and the asymmetric baseline window."""

from __future__ import annotations

from datetime import date, timedelta

import torch

from ml.dummy_data import make_dummy_hetero_data
from ml.engagement_lift import lift_from_posts
from ml.gail_model import GAILModel
from ml.placebo import placebo_anchor, placebo_lift, placebo_penalty
from ml.target_clustering import windowed_engagement

EVENT = date(2026, 6, 1)


# --- asymmetric baseline ------------------------------------------------------

def test_before_days_widens_only_the_baseline():
    posts = [
        (EVENT - timedelta(days=50), 10.0),  # outside 30d, inside 60d
        (EVENT + timedelta(days=10), 20.0),
        (EVENT + timedelta(days=45), 99.0),  # outside the 30d outcome window
    ]
    b30, a30 = windowed_engagement(posts, EVENT, 30)
    b60, a60 = windowed_engagement(posts, EVENT, 30, before_days=60)
    assert b30 == [] and b60 == [10.0]
    # The causal (after) side must not stretch with the baseline.
    assert a30 == a60 == [20.0]


def test_default_is_symmetric_as_before():
    posts = [(EVENT - timedelta(days=20), 1.0), (EVENT + timedelta(days=20), 2.0)]
    assert windowed_engagement(posts, EVENT, 30) == windowed_engagement(posts, EVENT, 30, before_days=None)


def test_wider_baseline_recovers_a_lift():
    posts = {"youtube": {"c": [(EVENT - timedelta(days=50), 10.0), (EVENT + timedelta(days=5), 20.0)]}}
    assert lift_from_posts(posts, "c", EVENT, 30) is None
    assert lift_from_posts(posts, "c", EVENT, 30, before_days=60) is not None


# --- placebo lift ---------------------------------------------------------------

def test_placebo_windows_end_before_the_event():
    anchor = placebo_anchor(EVENT, 30)
    # Outcome side is (anchor, anchor + 30]; it must end strictly before the event.
    assert anchor + timedelta(days=30) < EVENT


def test_placebo_lift_ignores_post_event_data():
    posts = {"youtube": {"c": [
        (EVENT - timedelta(days=50), 10.0),  # placebo baseline
        (EVENT - timedelta(days=10), 30.0),  # placebo outcome
        (EVENT, 1e6),                         # event day: must be in neither side
        (EVENT + timedelta(days=5), 1e6),     # after the event: must be ignored
    ]}}
    v = placebo_lift([EVENT], lambda a: lift_from_posts(posts, "c", a, 30, statistic="log"), 30)
    expected = lift_from_posts(
        {"youtube": {"c": [(EVENT - timedelta(days=50), 10.0), (EVENT - timedelta(days=10), 30.0)]}},
        "c", placebo_anchor(EVENT, 30), 30, statistic="log",
    )
    assert v == expected


def test_placebo_lift_none_without_data():
    assert placebo_lift([EVENT], lambda a: None, 30) is None


# --- placebo penalty ------------------------------------------------------------

def test_penalty_zero_when_unrelated_or_degenerate():
    assert float(placebo_penalty(torch.tensor([1.0, 1.0, 1.0]), torch.tensor([0.0, 1.0, 2.0]))) == 0.0
    assert float(placebo_penalty(torch.tensor([0.0, 1.0, 2.0]), torch.tensor([5.0, 5.0, 5.0]))) == 0.0
    assert float(placebo_penalty(torch.tensor([1.0]), torch.tensor([2.0]))) == 0.0


def test_penalty_positive_when_gap_tracks_pretrend():
    pre = torch.tensor([-1.0, 0.0, 1.0, 2.0])
    assert float(placebo_penalty(pre * 0.5, pre)) > 0.0


def test_minimising_penalty_removes_the_association():
    torch.manual_seed(0)
    pre = torch.randn(50)
    gap = (0.8 * pre + 0.1 * torch.randn(50)).requires_grad_(True)
    opt = torch.optim.SGD([gap], lr=1.0)
    start = float(placebo_penalty(gap, pre))
    for _ in range(200):
        opt.zero_grad()
        placebo_penalty(gap, pre).backward()
        opt.step()
    assert float(placebo_penalty(gap, pre)) < 0.01 * start


def test_penalty_gradient_reaches_attention_and_beta():
    """The point of the penalty: it must be able to change the learned links."""
    data = make_dummy_hetero_data()
    n = data["creator"].x.size(0)
    torch.manual_seed(0)
    model = GAILModel(creator_feature_dim=data["creator"].x.size(1))
    t = torch.zeros(n)
    t[: n // 2] = 1
    pred, _, _ = model(data, t)
    gap = pred - model.predict_unexposed(data)
    placebo_penalty(gap, torch.randn(n)).backward()
    mix = model.exposure_module.mixing_logits.grad
    attn = [p.grad for p in model.exposure_module.attn_convs.parameters() if p.grad is not None]
    assert mix is not None and mix.abs().sum() > 0
    assert attn and any(g.abs().sum() > 0 for g in attn)
