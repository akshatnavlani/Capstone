"""P2 / P2b: treatment matches the window its outcome was measured in, and
rows contaminated by the neighbour's own sponsorship are dropped."""

from __future__ import annotations

from datetime import date, datetime

import torch

from ml.gail_model import GAILModel
from ml.schema import CREATOR_FEATURE_DIM, empty_hetero_data
from ml.time_indexed_treatment import (
    build_observations,
    drop_self_sponsored,
    group_by_span,
    own_sponsorship_in_window,
    sponsorship_dates,
    treatment_in_span,
)

IDX = {"a": 0, "b": 1, "c": 2}


def test_sponsorship_dates_parses_and_skips_undated():
    got = sponsorship_dates([
        ("a", datetime(2026, 6, 4, 12)), ("a", "2026-01-02T00:00:00+00:00"),
        ("b", None), (None, date(2026, 1, 1)),
    ])
    assert got == {"a": [date(2026, 1, 2), date(2026, 6, 4)]}


def test_treatment_counts_only_sponsorships_inside_the_span():
    """The P2 bug: an all-time flag treated a 2024 sponsor as exposure for a 2026 lift."""
    dates = {"a": [date(2024, 3, 1)], "b": [date(2026, 6, 10)]}
    t = treatment_in_span(dates, IDX, 3, date(2026, 6, 1), date(2026, 7, 1))
    assert t.tolist() == [0.0, 1.0, 0.0]


def test_span_bounds_are_inclusive():
    dates = {"a": [date(2026, 6, 1)], "b": [date(2026, 7, 1)]}
    t = treatment_in_span(dates, IDX, 3, date(2026, 6, 1), date(2026, 7, 1))
    assert t.tolist() == [1.0, 1.0, 0.0]


def test_same_day_own_sponsorship_is_contamination():
    """LeBron/Ronaldo: same Nike campaign, same day. Each is the other's 'spillover'."""
    dates = {"lebron": [date(2026, 6, 4)]}
    assert own_sponsorship_in_window(dates, "lebron", "2026-06-04 10:00:00+00:00", 30)


def test_own_sponsorship_outside_window_is_fine():
    dates = {"b": [date(2026, 1, 1)]}
    assert not own_sponsorship_in_window(dates, "b", date(2026, 6, 4), 30)
    assert own_sponsorship_in_window(dates, "b", date(2026, 1, 31), 30)


def test_drop_self_sponsored_splits_rows():
    dates = {"b": [date(2026, 6, 10)]}
    rows = [
        {"neighbour_id": "b", "event_date": "2026-06-04", "robust_lift": 1.0},
        {"neighbour_id": "c", "event_date": "2026-06-04", "robust_lift": 2.0},
    ]
    kept, dropped = drop_self_sponsored(rows, dates, 30)
    assert [r["neighbour_id"] for r in kept] == ["c"]
    assert [r["neighbour_id"] for r in dropped] == ["b"]


def test_observations_cluster_like_e2_and_carry_their_span():
    rows = [
        {"neighbour_id": "b", "event_date": "2026-06-04", "robust_lift": 1.0},
        {"neighbour_id": "b", "event_date": "2026-06-20", "robust_lift": 3.0},  # overlaps -> same
        {"neighbour_id": "b", "event_date": "2026-12-01", "robust_lift": 5.0},  # separate
        {"neighbour_id": "c", "event_date": "2026-06-04", "robust_lift": None},  # no value
    ]
    obs = build_observations(rows, window_days=30)
    assert len(obs) == 2
    first, second = obs
    assert first.value == 2.0 and first.n_rows == 2
    assert first.start == date(2026, 5, 5) and first.end == date(2026, 7, 20)
    assert second.value == 5.0 and second.span == (date(2026, 11, 1), date(2026, 12, 31))


def test_group_by_span_never_puts_one_creator_twice_in_a_pass():
    rows = [
        {"neighbour_id": "b", "event_date": "2026-06-04", "robust_lift": 1.0},
        {"neighbour_id": "c", "event_date": "2026-06-04", "robust_lift": 2.0},
        {"neighbour_id": "b", "event_date": "2026-12-01", "robust_lift": 3.0},
    ]
    groups = group_by_span(build_observations(rows, window_days=30))
    assert len(groups) == 2
    for members in groups.values():
        ids = [o.neighbour_id for o in members]
        assert len(ids) == len(set(ids))


def _small_graph():
    torch.manual_seed(0)
    n = 6
    data = empty_hetero_data()
    data["creator"].x = torch.randn(n, CREATOR_FEATURE_DIM)
    data["brand"].x = torch.zeros(1, data["brand"].x.size(1))
    src = torch.arange(n)
    dst = (src + 1) % n
    ei = torch.cat([torch.stack([src, dst]), torch.stack([dst, src])], dim=1)
    data["creator", "collaborates_with", "creator"].edge_index = ei
    data["creator", "collaborates_with", "creator"].edge_attr = torch.ones(ei.size(1), 1)
    return data


def test_forward_multi_matches_separate_forwards():
    data = _small_graph()
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM)
    model.eval()
    t1 = torch.tensor([1.0, 0, 0, 0, 0, 0])
    t2 = torch.tensor([0, 0, 0, 1.0, 0, 0])
    with torch.no_grad():
        preds, exps, prop = model.forward_multi(data, [t1, t2])
        for t, p, e in zip((t1, t2), preds, exps):
            p_ref, e_ref, prop_ref = model(data, t)
            assert torch.allclose(p, p_ref) and torch.allclose(e, e_ref)
            assert torch.allclose(prop, prop_ref)
    assert not torch.allclose(exps[0], exps[1])


def test_forward_multi_refuses_leaky_backbone():
    model = GAILModel(creator_feature_dim=CREATOR_FEATURE_DIM, backbone_sees_treatment=True)
    try:
        model.forward_multi(_small_graph(), [torch.zeros(6)])
    except RuntimeError:
        return
    raise AssertionError("forward_multi must refuse a backbone that sees treatment")


# --- P3: control observations --------------------------------------------------

from ml.engagement_lift import lift_from_posts, platform_engagement, platform_lift, row_target  # noqa: E402
from ml.time_indexed_treatment import Observation, build_control_observations, matched_did  # noqa: E402


class _OneCreatorCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *a, **k):
        pass

    def fetchall(self):
        return self.rows


def test_control_lift_is_measured_exactly_like_treated_lift():
    """Treated rows go through platform_engagement (one query each); controls go
    through lift_from_posts (bulk). Any difference would show up as 'spillover'."""
    rows = [(date(2026, 5, d), 10 * d, d) for d in (1, 10, 20)] + \
           [(date(2026, 6, d), 30 * d, 2 * d) for d in (5, 15, 25)]
    event = date(2026, 6, 1)
    before, after = platform_engagement(_OneCreatorCursor(rows), "x", "instagram", event, 30)
    treated = row_target({"instagram": platform_lift(before, after)})
    posts = {"instagram": {"x": [(d, a + b) for d, a, b in rows]}}
    assert lift_from_posts(posts, "x", event, 30) == treated


def test_lift_from_posts_returns_none_without_both_sides():
    posts = {"instagram": {"x": [(date(2026, 5, 20), 5)]}}
    assert lift_from_posts(posts, "x", date(2026, 6, 1), 30) is None
    assert lift_from_posts(posts, "missing", date(2026, 6, 1), 30) is None


SPAN_A = (date(2026, 5, 2), date(2026, 7, 1))
SPAN_B = (date(2026, 6, 1), date(2026, 7, 31))  # overlaps A
SPAN_C = (date(2026, 9, 1), date(2026, 10, 31))


def test_controls_are_measured_at_the_treated_dates():
    seen = []

    def lift(cid, d):
        seen.append((cid, d))
        return 1.0

    out = build_control_observations([(SPAN_A, [date(2026, 6, 1)], ["c1"])], lift)
    assert seen == [("c1", date(2026, 6, 1))]
    assert len(out) == 1 and not out[0].exposed and out[0].span == SPAN_A


def test_a_control_creator_never_reuses_overlapping_windows():
    """Same independence rule as E2: overlapping windows are one observation."""
    out = build_control_observations(
        [(SPAN_B, [date(2026, 7, 1)], ["c1"]), (SPAN_A, [date(2026, 6, 1)], ["c1"]),
         (SPAN_C, [date(2026, 10, 1)], ["c1"])],
        lambda cid, d: 1.0,
    )
    assert [o.span for o in out] == [SPAN_A, SPAN_C]  # earliest wins, B skipped


def test_controls_avoid_the_creators_own_treated_windows():
    out = build_control_observations(
        [(SPAN_B, [date(2026, 7, 1)], ["c1", "c2"])], lambda cid, d: 1.0,
        reserved_spans={"c1": [SPAN_A]},
    )
    assert [o.neighbour_id for o in out] == ["c2"]


def test_controls_without_a_measurable_lift_are_skipped_not_zeroed():
    out = build_control_observations([(SPAN_A, [date(2026, 6, 1)], ["c1"])], lambda c, d: None)
    assert out == []


def _obs(cid, span, value, exposed):
    return Observation(cid, value, span[0], span[1], 1, f"{cid}#x", (), exposed)


def test_matched_did_compares_within_window():
    """Window A: everyone rose by ~1 (season), exposed by 1.5 -> effect 0.5.
    Window C: flat season, exposed +0.5 -> effect 0.5. An UNMATCHED comparison
    would mix the seasons; the matched one recovers 0.5."""
    obs = [
        _obs("t1", SPAN_A, 1.5, True), _obs("c1", SPAN_A, 0.9, False), _obs("c2", SPAN_A, 1.1, False),
        _obs("t2", SPAN_C, 0.5, True), _obs("c3", SPAN_C, -0.1, False), _obs("c4", SPAN_C, 0.1, False),
    ]
    did = matched_did(obs)
    assert abs(did["estimate"] - 0.5) < 1e-9
    assert did["n_treated"] == 2 and did["n_control"] == 4 and did["windows"] == 2
    assert did["se"] > 0


def test_matched_did_reports_windows_without_controls():
    obs = [_obs("t1", SPAN_A, 1.0, True), _obs("t2", SPAN_C, 2.0, True), _obs("c1", SPAN_C, 1.0, False)]
    did = matched_did(obs)
    assert did["treated_without_control"] == 1 and did["n_treated"] == 1
    assert abs(did["estimate"] - 1.0) < 1e-9
