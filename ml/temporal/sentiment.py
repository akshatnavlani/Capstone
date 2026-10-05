"""Sentiment classifier -> brand-safety score in [0, 1] (PendingWork S1).

Direction matters: backend/app/fusion.py treats a HIGHER sentiment_risk_score
as better (it adds w2 * score and penalizes scores below RISK_THRESHOLD), so
this is a brand-SAFETY score: 1 = safe, 0 = risky, 0.5 = neutral. It is the
expected value of the 3-class output with negative=0, neutral=0.5, positive=1.

Known limitation: the model is English-trained, and much of the comment data
is Hindi or Hinglish. Report the share of comments the model handles poorly
rather than hiding it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"
MAX_TOKENS = 256
NEUTRAL_SAFETY = 0.5


def probs_to_safety(probs: dict[str, float]) -> float:
    """Expected safety from class probabilities, keyed by label name."""
    p = {label.lower(): value for label, value in probs.items()}
    return float(p.get("positive", 0.0) + NEUTRAL_SAFETY * p.get("neutral", 0.0))


def shrunk_mean(
    scores, prior: float = NEUTRAL_SAFETY, prior_strength: float = 20.0
) -> tuple[float, int]:
    """Mean safety pulled toward `prior` when there are few comments, so a
    creator with 3 comments cannot score an extreme 0 or 1. NaNs are ignored.
    Returns (score, number of scored comments).
    """
    s = np.asarray(scores, dtype=float)
    s = s[~np.isnan(s)]
    n = len(s)
    return float((s.sum() + prior * prior_strength) / (n + prior_strength)), n


def score_with_checkpoint(
    score_fn,
    keys: list[str],
    texts: list[str],
    path: Path,
    block_size: int = 1024,
    on_progress=None,
) -> np.ndarray:
    """Score `texts` in blocks, saving each block to `path` so an interrupted
    run resumes instead of starting over. `keys` identify texts across runs
    (the same key must always mean the same text). `score_fn(list[str])`
    returns one score per text. The checkpoint file is left in place; the
    caller deletes it once its final output is safely written.
    """
    cache: dict[str, float | None] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    todo = [i for i, k in enumerate(keys) if k not in cache]
    if on_progress:
        on_progress(len(keys) - len(todo), len(keys))
    for start in range(0, len(todo), block_size):
        block = todo[start : start + block_size]
        for i, s in zip(block, score_fn([texts[i] for i in block])):
            cache[keys[i]] = None if s != s else float(s)  # NaN -> null
        path.write_text(json.dumps(cache), encoding="utf-8")
        if on_progress:
            on_progress(len(keys) - len(todo) + start + len(block), len(keys))
    return np.array([np.nan if cache[k] is None else cache[k] for k in keys])


class SentimentScorer:
    """Lazy wrapper so importing this module never downloads or loads a model."""

    def __init__(self, model_name: str = MODEL_NAME, batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size
        self._pipe = None

    def _pipeline(self):
        if self._pipe is None:
            from ml._scipy_compat import avoid_blocked_scipy_solver

            avoid_blocked_scipy_solver()
            from transformers import pipeline

            self._pipe = pipeline(
                "text-classification",
                model=self.model_name,
                top_k=None,
                truncation=True,
                max_length=MAX_TOKENS,
            )
        return self._pipe

    def score(self, texts: list[str], progress: bool = False) -> np.ndarray:
        """Safety per text; NaN for empty/blank texts. `progress` prints a
        running count (CPU scoring of thousands of comments takes minutes).
        """
        out = np.full(len(texts), np.nan)
        idx = [i for i, t in enumerate(texts) if t and t.strip()]
        pipe = self._pipeline() if idx else None
        step = self.batch_size * 4
        for start in range(0, len(idx), step):
            chunk = idx[start : start + step]
            results = pipe([texts[i] for i in chunk], batch_size=self.batch_size)
            for i, res in zip(chunk, results):
                labels = res if isinstance(res, list) else [res]
                out[i] = probs_to_safety({d["label"]: d["score"] for d in labels})
            if progress:
                print(f"  scored {min(start + step, len(idx))}/{len(idx)}", flush=True)
        return out
