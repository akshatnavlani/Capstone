import numpy as np

from passport_stats import MIN_GAP, loo_ridge, matched_differences, mood_gap, placebo_pooled, pooled, prediction_report, spearman


def test_mood_gap_needs_size_and_certainty():
    assert mood_gap(0.50, 100, 0.52, 100)["significant"] is False
    clear = mood_gap(0.40, 400, 0.65, 400)
    assert clear["significant"] and clear["label"] == "warmer on Instagram than on YouTube"
    assert mood_gap(0.40, 400, 0.65, 400)["gap"] == 0.25
    # a big gap on a handful of comments is not flagged
    assert mood_gap(0.40, 100, 0.62, 5)["significant"] is False
    assert abs(mood_gap(0.6, 400, 0.3, 400)["gap"]) >= MIN_GAP


def test_matched_differences_use_same_format_and_window():
    organic = [(d, "long", 5.0) for d in range(0, 100, 5)] + [(d, "short", 9.0) for d in range(0, 100, 5)]
    spons = [(50.0, "long", 4.0), (50.0, "short", 9.5)]
    assert matched_differences(spons, organic, 30) == [-1.0, 0.5]
    assert matched_differences([(50.0, "long", 4.0)], organic[:2], 30) == []  # too few organic neighbours


def test_pooled_and_placebo_centre_on_zero_when_nothing_happens():
    rng = np.random.default_rng(0)
    organic = {f"c{i}": [(float(d), "long", float(rng.normal(5, 0.5))) for d in range(0, 200, 4)] for i in range(12)}
    p = placebo_pooled(organic, {c: 6 for c in organic}, 40, runs=40)
    assert p["runs"] > 0 and p["ci95"][0] < 0 < p["ci95"][1]
    assert pooled([0.1, -0.1, 0.0, 0.05, -0.05])["ci95"][0] < 0 < pooled([0.1, -0.1, 0.0, 0.05, -0.05])["ci95"][1]
    assert pooled([0.1])["mean"] is None


def test_prediction_beats_size_only_when_a_second_feature_matters():
    rng = np.random.default_rng(1)
    n = 120
    size, other = rng.normal(size=n), rng.normal(size=n)
    y = 0.5 * size + 1.0 * other + rng.normal(scale=0.3, size=n)
    rep = prediction_report(np.c_[size, other], y, size_col=0)
    assert rep["beats_size_only"] and rep["spearman_full"] > rep["spearman_size_only"]
    noise = prediction_report(np.c_[size, rng.normal(size=n)], 0.5 * size + rng.normal(scale=0.5, size=n), size_col=0)
    assert not noise["beats_size_only"]
    assert abs(spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-9
    assert loo_ridge(np.c_[size], size * 2, 1e-6).shape == (n,)
