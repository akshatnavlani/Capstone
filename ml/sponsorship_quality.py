"""Probability that a detected sponsorship event is a REAL ad, learned from the events a human has checked (26 Oct 2026).

Why: only about 10% of the 1,871 sponsorship events were ever checked by a person, and 81% of them come from the weaker rule tiers (brand name, brand + promo code).
This model learns from those checks, gives every event a probability, and is scored the honest way: on creators it never trained on (grouped cross-validation).

Features, all plain numpy (scikit-learn is not installed here):
  * the detector's evidence tier (one-hot) and how many evidence strings it left;
  * words that signal an ad or a plain code footer, and WHERE in the text they sit (a promo code in the last lines of a long description is the typical "footer only" non-ad);
  * a small hashed bag of words from the head (title + first 300 characters) and the tail (last 300 characters) of the text.
Model: ridge logistic regression (`ml.spillover_effect.logistic_fit`).
"""
from __future__ import annotations

import re
import zlib

import numpy as np

from ml.spillover_effect import logistic_fit

TIERS = ("official_label", "disclosure_tag", "spoken", "creator_comment", "brand_and_code", "brand_mention", "none")
HASH_DIM = 256
_TOKEN = re.compile(r"[a-z0-9#@]{2,}")
_CODE = re.compile(r"\b(code|coupon|promo|discount|off)\b", re.I)
_DISCLOSURE = re.compile(r"(#ad\b|#sponsored|sponsored|paid partnership|paid promotion|partnered|in collaboration|collab with|brought to you by|affiliate)", re.I)
_LINK = re.compile(r"https?://\S+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def hashed_bag(words: list[str], prefix: str, dim: int = HASH_DIM) -> np.ndarray:
    """Signed hashed unigram + bigram counts (deterministic: crc32), scaled so a long text does not dominate."""
    v = np.zeros(dim)
    grams = words + [a + "_" + b for a, b in zip(words, words[1:])]
    for g in grams:
        h = zlib.crc32((prefix + g).encode("utf-8"))
        v[h % dim] += 1.0 if (h >> 16) & 1 else -1.0
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def event_features(row: dict) -> np.ndarray:
    """One row = {tier, n_evidence, platform, title, body}. Returns a fixed-length feature vector."""
    tier = row.get("tier") or "none"
    title, body = row.get("title") or "", row.get("body") or ""
    text = f"{title}\n{body}"
    head, tail = f"{title} {body[:300]}", body[-300:] if len(body) > 300 else ""
    code_hits = [m.start() for m in _CODE.finditer(text)]
    first_code = (code_hits[0] / max(len(text), 1)) if code_hits else 1.0
    disc_hits = [m.start() for m in _DISCLOSURE.finditer(text)]
    first_disc = (disc_hits[0] / max(len(text), 1)) if disc_hits else 1.0
    in_footer = float(bool(code_hits) and len(body) > 600 and first_code > 0.7)        # a code that only appears near the end of a long description
    numeric = np.array([
        float(len(code_hits) > 0), float(len(disc_hits) > 0), first_code, first_disc, in_footer,
        np.log1p(len(code_hits)), np.log1p(len(disc_hits)), np.log1p(len(body)), np.log1p(len(_LINK.findall(body))),
        float(row.get("n_evidence", 0)), float(row.get("platform") == "instagram"), float(row.get("platform") == "youtube"),
    ])
    onehot = np.array([float(tier == t) for t in TIERS])
    return np.concatenate([onehot, numeric, hashed_bag(tokens(head), "h:"), hashed_bag(tokens(tail), "t:")])


def standardise(X: np.ndarray, mean: np.ndarray | None = None, std: np.ndarray | None = None):
    mean = X.mean(0) if mean is None else mean
    std = X.std(0) if std is None else std
    std = np.where(std > 1e-9, std, 1.0)
    return (X - mean) / std, mean, std


def fit_model(X: np.ndarray, y: np.ndarray, l2: float = 20.0):
    Z, mean, std = standardise(X)
    w = logistic_fit(np.column_stack([np.ones(len(Z)), Z]), y.astype(float), l2=l2)
    return {"w": w, "mean": mean, "std": std}


def predict(model: dict, X: np.ndarray) -> np.ndarray:
    Z, _, _ = standardise(X, model["mean"], model["std"])
    return 1.0 / (1.0 + np.exp(-(np.column_stack([np.ones(len(Z)), Z]) @ model["w"])))


def auc(y: np.ndarray, score: np.ndarray) -> float:
    """Probability that a random positive outranks a random negative (ties count half)."""
    pos, neg = score[y == 1], score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(gt / (len(pos) * len(neg)))


def group_folds(groups: list, k: int, seed: int) -> list[np.ndarray]:
    """k folds of row indices in which every group (creator) lands in exactly one fold, so a creator's own footer habits never leak into its test fold."""
    rng = np.random.default_rng(seed)
    uniq = list(dict.fromkeys(groups))
    rng.shuffle(uniq)
    bucket = {g: i % k for i, g in enumerate(uniq)}
    folds = [[] for _ in range(k)]
    for i, g in enumerate(groups):
        folds[bucket[g]].append(i)
    return [np.array(f) for f in folds if f]


def binary_metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    pred = p >= threshold
    tp, fp, fn, tn = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum()), int((~pred & (y == 1)).sum()), int((~pred & (y == 0)).sum())
    return {"precision": tp / (tp + fp) if tp + fp else float("nan"), "recall": tp / (tp + fn) if tp + fn else float("nan"),
            "accuracy": (tp + tn) / max(len(y), 1), "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def cross_validate(rows: list[dict], y: np.ndarray, groups: list, k: int = 5, repeats: int = 5, l2: float = 20.0, tier_only: bool = False) -> dict:
    """Grouped k-fold, repeated. Returns the out-of-fold AUC and the metrics at 0.5, averaged over repeats. `tier_only` keeps just the tier one-hot (the baseline)."""
    X = np.array([event_features(r) for r in rows])
    if tier_only:
        X = X[:, : len(TIERS)]
    aucs, mets = [], []
    for rep in range(repeats):
        oof = np.full(len(y), np.nan)
        for test in group_folds(groups, k, seed=rep):
            train = np.setdiff1d(np.arange(len(y)), test)
            if len(set(y[train])) < 2:
                continue
            oof[test] = predict(fit_model(X[train], y[train], l2), X[test])
        ok = ~np.isnan(oof)
        aucs.append(auc(y[ok], oof[ok]))
        mets.append(binary_metrics(y[ok], oof[ok]))
    avg = lambda key: float(np.nanmean([m[key] for m in mets]))  # noqa: E731
    return {"auc": float(np.nanmean(aucs)), "auc_sd": float(np.nanstd(aucs)), "precision": avg("precision"), "recall": avg("recall"), "accuracy": avg("accuracy"), "n": int(len(y))}
