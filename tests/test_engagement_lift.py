"""Tests for ml.engagement_lift.

The test that carries the change is `test_one_viral_post_moves_the_mean_not_the_median`:
it reproduces the real failure -- creator 767cd996 swinging +3.07 to -0.75 across
well-measured events -- and checks the median-based lift is unmoved by the single
post that caused it.

Its counterpart, `test_a_real_shift_still_registers`, matters just as much: a
statistic that flattened everything would hide the effect we are trying to measure.
"""

from __future__ import annotations

import pytest

from ml.engagement_lift import (
    DEFAULT_MIN_POSTS,
    TARGET_STATISTIC,
    platform_lift,
    row_target,
    well_measured,
)


# --- the headline case --------------------------------------------------------


def test_one_viral_post_moves_the_mean_not_the_median():
    """A steady creator plus one video that took off.

    Typical engagement is unchanged, so the honest lift is ~0. The mean reports a
    large rise purely because of the viral post.
    """
    before = [100.0] * 10
    after = [100.0] * 9 + [50_000.0]

    out = platform_lift(before, after)

    assert out["lift"] > 40, "the mean should be dragged up by the viral post"
    assert abs(out["robust_lift"]) < 1e-9, "the median should be unmoved"


def test_a_real_shift_still_registers():
    """The median must not flatten a genuine change into nothing."""
    out = platform_lift([100.0] * 10, [200.0] * 10)
    assert out["robust_lift"] > 0.9


def test_a_real_decline_registers():
    out = platform_lift([200.0] * 10, [100.0] * 10)
    assert out["robust_lift"] < -0.4


# --- the formula --------------------------------------------------------------


def test_zero_baseline_does_not_divide_by_zero():
    """The +1 in the denominator. A creator with no prior engagement is common."""
    out = platform_lift([0.0, 0.0, 0.0], [5.0, 5.0, 5.0])
    assert out["robust_lift"] == pytest.approx(5.0)


def test_identical_windows_give_zero_lift():
    out = platform_lift([3.0, 7.0, 11.0], [3.0, 7.0, 11.0])
    assert out["lift"] == pytest.approx(0.0)
    assert out["robust_lift"] == pytest.approx(0.0)


def test_single_value_each_side_makes_median_equal_mean():
    """Why the median does not fix thin rows: with one value it IS the value."""
    out = platform_lift([10.0], [40.0])
    assert out["lift"] == pytest.approx(out["robust_lift"])


def test_post_counts_are_reported():
    out = platform_lift([1.0, 2.0], [3.0, 4.0, 5.0])
    assert out["n_before"] == 2
    assert out["n_after"] == 3


def test_empty_side_raises_rather_than_returning_zero():
    """An uncomputable row must not reach the model as a real zero."""
    with pytest.raises(ValueError):
        platform_lift([], [1.0])
    with pytest.raises(ValueError):
        platform_lift([1.0], [])


# --- row aggregation ----------------------------------------------------------


def _lifts(**per_platform) -> dict[str, dict]:
    return {
        name: platform_lift(before, after)
        for name, (before, after) in per_platform.items()
    }


def test_row_target_averages_across_platforms():
    lifts = _lifts(
        instagram=([100.0] * 4, [200.0] * 4),
        reddit=([100.0] * 4, [100.0] * 4),
    )
    both = row_target(lifts, statistic="median")
    only_instagram = row_target({"instagram": lifts["instagram"]}, statistic="median")
    assert 0 < both < only_instagram


def test_row_target_default_is_the_median():
    """The default must be the statistic the evidence chose, not the old one."""
    assert TARGET_STATISTIC == "median"
    lifts = _lifts(youtube=([100.0] * 10, [100.0] * 9 + [50_000.0]))
    assert row_target(lifts) == pytest.approx(row_target(lifts, statistic="median"))
    assert row_target(lifts) != pytest.approx(row_target(lifts, statistic="mean"))


def test_mean_statistic_reproduces_the_old_behaviour():
    """Kept so a comparison run against the pre-change target is possible."""
    lifts = _lifts(youtube=([100.0] * 10, [100.0] * 9 + [50_000.0]))
    assert row_target(lifts, statistic="mean") == pytest.approx(
        lifts["youtube"]["lift"]
    )


def test_unknown_statistic_raises():
    lifts = _lifts(youtube=([1.0], [2.0]))
    with pytest.raises(ValueError):
        row_target(lifts, statistic="mode")


def test_row_target_on_no_platforms_raises():
    """Cross-platform-only straddles must be reported, not averaged to zero."""
    with pytest.raises(ValueError):
        row_target({})


# --- the min-post filter ------------------------------------------------------


def test_default_min_posts_filters_nothing():
    """One change at a time: introducing this module must not also drop rows."""
    assert DEFAULT_MIN_POSTS == 1
    assert well_measured(_lifts(instagram=([1.0], [2.0])))


def test_weakest_platform_decides():
    lifts = _lifts(
        instagram=([1.0] * 20, [2.0] * 20),
        reddit=([1.0], [2.0]),
    )
    assert well_measured(lifts, min_posts=3) is False


def test_well_measured_row_passes():
    lifts = _lifts(instagram=([1.0] * 5, [2.0] * 5))
    assert well_measured(lifts, min_posts=5) is True


def test_threshold_applies_to_both_sides():
    lifts = _lifts(instagram=([1.0] * 8, [2.0]))
    assert well_measured(lifts, min_posts=2) is False


def test_no_platforms_is_never_well_measured():
    assert well_measured({}) is False