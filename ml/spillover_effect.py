"""Spillover effect estimators that are honest at the sample size we have (about 100 creators with a measured lift, 16 of them exposed).

Why this exists (2026-10-24): the GAIL neural head, cross-fitted, did not recover a planted effect of +1.47 (it returned +0.04), because its outcome
head reads a 1289-dim embedding that identifies each creator, so the exposure term never carries weight. Everything here is low-capacity numpy:

  * `difference_in_means` / `adjusted_effect`: exposed vs unexposed lift, optionally with a ridge adjustment on a few creator covariates.
  * `bootstrap_effects`: percentile interval from resampling CREATORS (the unit that is independent), for both estimators.
  * `aipw_cross_fit`: the doubly robust estimate with both nuisance models fit out-of-fold on the analysed sample. Kept for completeness; on this data
    its propensity weights add more noise than they remove (it failed the planted-effect check), so it is not the headline estimate.

`y` is the per-creator lift, `t` the exposure indicator (1 = has a sponsored neighbour), `cov` standardised covariates, `lab` the indices analysed.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

EXPOSURE_PENALTY = 0.01      # the exposure coefficient is (almost) unpenalised so it can carry weight
COVARIATE_PENALTY = 10.0


def ridge_fit(X: np.ndarray, y: np.ndarray, penalty: np.ndarray) -> np.ndarray:
    return np.linalg.solve(X.T @ X + np.diag(penalty), X.T @ y)


def logistic_fit(X: np.ndarray, t: np.ndarray, l2: float = 2.0, iters: int = 50) -> np.ndarray:
    """Ridge logistic regression by Newton's method; column 0 is the (unpenalised) intercept."""
    w = np.zeros(X.shape[1])
    ridge = np.r_[0.0, np.ones(len(w) - 1)]
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w)))
        grad = X.T @ (p - t) + l2 * ridge * w
        hess = (X.T * (p * (1 - p))) @ X + l2 * np.diag(ridge) + 1e-6 * np.eye(len(w))
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def _outcome_design(cov: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    X = np.column_stack([np.ones(len(t)), cov, t])
    penalty = np.r_[0.0, np.full(cov.shape[1], COVARIATE_PENALTY), EXPOSURE_PENALTY]
    return X, penalty


def difference_in_means(y: np.ndarray, t: np.ndarray, idx: np.ndarray) -> float:
    ex, un = idx[t[idx] == 1], idx[t[idx] == 0]
    if len(ex) == 0 or len(un) == 0:
        return float("nan")
    return float(y[ex].mean() - y[un].mean())


def adjusted_effect(cov: np.ndarray, t: np.ndarray, y: np.ndarray, idx: np.ndarray) -> float:
    """Exposure coefficient of a ridge regression of the lift on creator covariates plus exposure."""
    if len(idx[t[idx] == 1]) == 0 or len(idx[t[idx] == 0]) == 0:
        return float("nan")
    X, penalty = _outcome_design(cov, t)
    return float(ridge_fit(X[idx], y[idx], penalty)[-1])


def bootstrap_effects(cov, t, y, lab, draws: int = 2000, seed: int = 0, min_per_arm: int = 3) -> dict:
    """Resample creators with replacement; return both estimates with 95% percentile intervals. Draws with too few exposed/unexposed are skipped."""
    rng = np.random.default_rng(seed)
    lab = np.asarray(lab)
    rows = []
    for _ in range(draws):
        idx = rng.choice(lab, len(lab))
        if (t[idx] == 1).sum() < min_per_arm or (t[idx] == 0).sum() < min_per_arm:
            continue
        rows.append((difference_in_means(y, t, idx), adjusted_effect(cov, t, y, idx)))
    arr = np.array(rows)
    out = {"draws_used": len(rows), "difference_in_means": difference_in_means(y, t, lab), "adjusted": adjusted_effect(cov, t, y, lab)}
    for j, name in enumerate(("difference_in_means", "adjusted")):
        lo, hi = np.percentile(arr[:, j], [2.5, 97.5])
        out[f"{name}_ci"] = (float(lo), float(hi))
        out[f"{name}_excludes_zero"] = bool(lo > 0 or hi < 0)
    return out


def aipw_cross_fit(cov, t, y, lab, folds: int = 5, repeats: int = 20, clip_eps: float = 0.05, seed: int = 0) -> tuple[float, float]:
    """Cross-fitted AIPW effect: outcome ridge and propensity logistic are fit WITHOUT the held-out fold, on the analysed sample only."""
    lab = np.asarray(lab)
    X, penalty = _outcome_design(cov, t)
    Xp = np.column_stack([np.ones(len(t)), cov])
    taus = defaultdict(list)
    for r in range(repeats):
        order = np.random.default_rng(seed + r).permutation(lab)
        for k in range(folds):
            held = order[k::folds]
            tr = np.setdiff1d(lab, held)
            w = ridge_fit(X[tr], y[tr], penalty)
            pi = np.clip(1 / (1 + np.exp(-(Xp[held] @ logistic_fit(Xp[tr], t[tr])))), clip_eps, 1 - clip_eps)
            mu_e = X[held] @ w
            mu_0 = np.column_stack([np.ones(len(held)), cov[held], np.zeros(len(held))]) @ w
            tau = (mu_e - mu_0) + (t[held] / pi) * (y[held] - mu_e) - ((1 - t[held]) / (1 - pi)) * (y[held] - mu_0)
            for i, v in zip(held, tau):
                taus[i].append(v)
    per = np.array([np.mean(v) for v in taus.values()])
    return float(per.mean()), float(per.std() / math.sqrt(len(per)))
