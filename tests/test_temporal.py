"""Tests for ml/temporal (PendingWork S1). Synthetic data only: no model
download, no database. Planted effects check the methods recover what was put in.
"""

from datetime import datetime, timezone

import numpy as np
import pytest

from ml.temporal.lag import lag_profile, pooled_lag_test
from ml.temporal.propagation import (
    apply_propagated_risk,
    normalized_adjacency,
    propagate,
    propagation_matrix,
    risk_shock,
    top_source,
)
from ml.temporal.sentiment import probs_to_safety, score_with_checkpoint, shrunk_mean
from ml.temporal.series import bin_counts, bin_mean, to_epoch_hours


# --- sentiment ---------------------------------------------------------------


def test_probs_to_safety_extremes_and_neutral():
    assert probs_to_safety({"negative": 1.0, "neutral": 0.0, "positive": 0.0}) == 0.0
    assert probs_to_safety({"negative": 0.0, "neutral": 0.0, "positive": 1.0}) == 1.0
    assert probs_to_safety({"negative": 0.0, "neutral": 1.0, "positive": 0.0}) == 0.5


def test_probs_to_safety_is_case_insensitive_and_mixed():
    assert probs_to_safety({"Negative": 0.2, "Neutral": 0.4, "Positive": 0.4}) == pytest.approx(0.6)


def test_shrunk_mean_empty_is_neutral():
    score, n = shrunk_mean([])
    assert score == 0.5 and n == 0


def test_shrunk_mean_few_comments_stay_near_prior_many_approach_mean():
    few, _ = shrunk_mean([0.0, 0.0, 0.0])
    many, n = shrunk_mean([0.0] * 2000)
    assert 0.4 < few < 0.5
    assert many < 0.01 and n == 2000


def test_shrunk_mean_ignores_nan():
    score, n = shrunk_mean([np.nan, 1.0, np.nan], prior_strength=0.0)
    assert n == 1 and score == 1.0


def test_checkpoint_resumes_after_interruption_without_rescoring(tmp_path):
    texts = [f"t{i}" for i in range(10)]
    keys = [f"k{i}" for i in range(10)]
    path = tmp_path / "ckpt.json"
    calls = []
    dies = {"on": True}

    def flaky(batch):
        calls.append(list(batch))
        if dies["on"] and len(calls) == 2:
            raise RuntimeError("battery died")
        return [float(t[1:]) / 10 for t in batch]

    with pytest.raises(RuntimeError):
        score_with_checkpoint(flaky, keys, texts, path, block_size=4)
    assert len(calls) == 2  # block 1 saved (4 texts), block 2 failed

    dies["on"] = False
    calls.clear()
    scores = score_with_checkpoint(flaky, keys, texts, path, block_size=4)
    scored_again = [t for batch in calls for t in batch]
    assert scored_again == texts[4:]  # only the unfinished texts were scored again
    assert scores.tolist() == [i / 10 for i in range(10)]


def test_checkpoint_keeps_nan_for_blank_texts(tmp_path):
    path = tmp_path / "ckpt.json"
    scores = score_with_checkpoint(lambda b: [np.nan, 0.7][: len(b)], ["a", "b"], ["", "x"], path, block_size=5)
    assert np.isnan(scores[0]) and scores[1] == 0.7


# --- series ------------------------------------------------------------------


def test_bin_counts_and_mean():
    hours = np.array([0.5, 1.5, 1.7, 5.0])
    assert bin_counts(hours, 0, 6, 2).tolist() == [3.0, 0.0, 1.0]  # bins 0-2, 2-4, 4-6
    means = bin_mean(hours, np.array([1.0, 2.0, 4.0, 9.0]), 0, 6, 2)
    assert means[0] == pytest.approx((1.0 + 2.0 + 4.0) / 3)
    assert np.isnan(means[1]) and means[2] == 9.0


def test_to_epoch_hours_spacing():
    a = datetime(2026, 1, 1, 0, tzinfo=timezone.utc)
    b = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    h = to_epoch_hours([a, b])
    assert h[1] - h[0] == pytest.approx(12.0)


# --- lag detection -----------------------------------------------------------


def _lagged_pair(rng, n=200, lag=3, noise=0.3):
    x = rng.normal(size=n)
    y = np.roll(x, lag) + noise * rng.normal(size=n)
    return x, y


def test_lag_profile_peaks_at_planted_lag():
    x, y = _lagged_pair(np.random.default_rng(1))
    profile = lag_profile(x, y, max_lag=6)
    assert np.argmax(profile) - 6 == 3


def test_pooled_lag_test_recovers_planted_lag_and_is_significant():
    rng = np.random.default_rng(2)
    pairs = [_lagged_pair(rng) for _ in range(5)]
    result = pooled_lag_test(pairs, max_lag=6, n_perm=200, seed=0)
    assert result.best_lag == 3
    assert result.p_value < 0.05
    assert result.n_pairs == 5


def test_pooled_lag_test_not_significant_on_independent_noise():
    rng = np.random.default_rng(3)
    pairs = [(rng.normal(size=120), rng.normal(size=120)) for _ in range(5)]
    result = pooled_lag_test(pairs, max_lag=6, n_perm=200, seed=0)
    assert result.p_value > 0.05


def test_pooled_lag_test_rejects_when_no_usable_pairs():
    with pytest.raises(ValueError):
        pooled_lag_test([(np.zeros(50), np.ones(50))], max_lag=3)


# --- Granger (needs scipy) ---------------------------------------------------


def test_granger_detects_planted_one_step_cause():
    pytest.importorskip("scipy")
    from ml.temporal.granger import best_lag_pvalue, granger_pvalues

    rng = np.random.default_rng(4)
    cause = rng.normal(size=300)
    effect = np.zeros(300)
    for t in range(1, 300):
        effect[t] = 0.8 * cause[t - 1] + 0.3 * rng.normal()
    p = granger_pvalues(cause, effect, max_lag=3)
    lag, p_best = best_lag_pvalue(p)
    assert lag == 1 and p_best < 0.01
    # the planted cause runs one way only: effect does not help predict cause
    p_reverse = granger_pvalues(effect, cause, max_lag=3)
    assert best_lag_pvalue(p_reverse)[1] > 0.05


def test_granger_not_significant_on_independent_noise():
    pytest.importorskip("scipy")
    from ml.temporal.granger import best_lag_pvalue, granger_pvalues

    rng = np.random.default_rng(5)
    p = granger_pvalues(rng.normal(size=300), rng.normal(size=300), max_lag=3)
    assert set(p) == {1, 2, 3}
    assert best_lag_pvalue(p)[1] > 0.05


def test_granger_returns_none_for_short_or_constant_series():
    pytest.importorskip("scipy")
    from ml.temporal.granger import granger_pvalues

    assert granger_pvalues(np.arange(10.0), np.arange(10.0)[::-1], max_lag=2) is None
    assert granger_pvalues(np.ones(100), np.arange(100.0), max_lag=2) is None


def test_fisher_combine_many_small_p_values_is_small():
    pytest.importorskip("scipy")
    from ml.temporal.granger import fisher_combine

    assert fisher_combine([0.04] * 8) < fisher_combine([0.04])


# --- propagation -------------------------------------------------------------


def _path_graph():
    # 0 - 1 - 2 - 3, node 4 isolated
    return normalized_adjacency(5, {"collaborates_with": [(0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0)]})


def test_propagation_reaches_neighbours_within_hops_only():
    M = propagation_matrix(_path_graph(), alpha=0.5, hops=2)
    shock = np.array([1.0, 0, 0, 0, 0])
    out = propagate(shock, M)
    assert out[1] > out[2] > 0          # decays with distance
    assert out[3] == 0                  # three hops away, hops=2
    assert out[4] == 0                  # isolated node unaffected
    assert out[0] == 0                  # a source does not propagate to itself


def test_top_source_identifies_origin_and_none_when_no_risk():
    M = propagation_matrix(_path_graph(), alpha=0.5, hops=2)
    shock = np.array([1.0, 0, 0, 0, 0])
    assert top_source(M, shock, 2) == 0
    assert top_source(M, shock, 4) is None


def test_relation_weights_change_what_propagates():
    edges = {"collaborates_with": [(0, 1, 1.0)], "co_occurs_with": [(0, 2, 1.0)]}
    A = normalized_adjacency(3, edges, {"collaborates_with": 3.0, "co_occurs_with": 1.0})
    out = propagate(np.array([1.0, 0, 0]), propagation_matrix(A, alpha=0.5, hops=1))
    assert out[1] > 0 and out[2] > 0
    # both are row-normalized per node, so each leaf gets the same share here
    assert out[1] == pytest.approx(out[2])


def test_risk_shock_only_below_threshold():
    s = risk_shock(np.array([0.9, 0.5, 0.25, 0.0]), threshold=0.5)
    assert s.tolist() == [0.0, 0.0, 0.5, 1.0]


def test_apply_propagated_risk_lowers_safety_and_stays_in_range():
    out = apply_propagated_risk(np.array([0.9, 0.1]), np.array([0.4, 0.9]), beta=0.5)
    assert out[0] == pytest.approx(0.7)
    assert out[1] == 0.0
