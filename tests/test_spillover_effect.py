"""The spillover estimators must find nothing when nothing is planted and find a large planted effect (the check GAIL's neural head failed)."""
import numpy as np

from ml import spillover_effect as se


def _world(effect: float, n: int = 100, n_exposed: int = 16, seed: int = 0):
    rng = np.random.default_rng(seed)
    cov = rng.normal(size=(n, 4))
    t = np.zeros(n)
    t[rng.choice(n, n_exposed, replace=False)] = 1.0
    y = 0.3 * cov[:, 0] + rng.normal(scale=1.5, size=n) + effect * t
    return cov, t, y, np.arange(n)


def test_no_planted_effect_gives_an_interval_that_includes_zero():
    cov, t, y, lab = _world(0.0, seed=3)
    out = se.bootstrap_effects(cov, t, y, lab, draws=500)
    assert out["difference_in_means_excludes_zero"] is False and out["adjusted_excludes_zero"] is False


def test_a_large_planted_effect_is_found_and_close_to_the_truth():
    cov, t, y, lab = _world(2.0, n=120, n_exposed=20, seed=1)
    out = se.bootstrap_effects(cov, t, y, lab, draws=500)
    assert out["difference_in_means_excludes_zero"] and out["adjusted_excludes_zero"]
    assert abs(out["difference_in_means"] - 2.0) < 1.0 and abs(out["adjusted"] - 2.0) < 1.0


def test_estimators_return_nan_when_one_arm_is_empty():
    cov, t, y, lab = _world(0.0)
    all_unexposed = np.zeros_like(t)
    assert np.isnan(se.difference_in_means(y, all_unexposed, lab))
    assert np.isnan(se.adjusted_effect(cov, all_unexposed, y, lab))


def test_logistic_fit_separates_a_signal_covariate():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(400, 2))
    t = (x[:, 0] + rng.normal(scale=0.5, size=400) > 0).astype(float)
    w = se.logistic_fit(np.column_stack([np.ones(400), x]), t)
    assert w[1] > 1.0 and abs(w[2]) < 0.5


def test_cross_fitted_aipw_is_near_zero_without_an_effect():
    cov, t, y, lab = _world(0.0, n=300, n_exposed=100, seed=2)
    ate, err = se.aipw_cross_fit(cov, t, y, lab, repeats=3)
    assert abs(ate) < 3 * max(err, 0.1)
