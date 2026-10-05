"""Creator feature score (PendingWork S2): the third input of the fusion layer.

Replaces the constant 0.5 in `creator_feature_score` with a score that depends
on the brand's brief. Two parts, both in [0, 1]:

  relevance  how close a creator's content is to the brand's product category.
             Image part: CLIP text-to-image similarity (thumbnails). Text part:
             the average of CLIP text-to-text and BERT (mean pooled) similarity
             on the scrubbed bio, titles and captions. Averaged over whichever
             of the two parts the creator has. (On the real creators the text
             part ranks matching creators above others with AUC about 0.85;
             BERT's pooled output alone managed about 0.70.)
  metadata   engagement rate and reach (log subscribers), averaged over
             whichever the creator has.

Raw cosine similarities are not comparable across models and sit in narrow
bands, so each is turned into a percentile rank among the creators for the
same query. Percentile ranks are uniform on [0, 1] with mean 0.5, so the
neutral value used when a signal is missing is consistent with them.

A creator with no usable signal gets exactly NEUTRAL (0.5): a missing signal
is never invented. The 0.7 / 0.3 blend is an uncalibrated starting value;
PendingWork S3 calibrates it together with the fusion weights.

Pure numpy, no model code, so it is testable without any download.
"""
from __future__ import annotations

import numpy as np

NEUTRAL = 0.5
W_RELEVANCE = 0.7
W_METADATA = 0.3


def cosine(matrix, vector) -> np.ndarray:
    """Cosine similarity of each row of `matrix` with `vector`. A zero row
    (no embedding) gives NaN, not 0, so it is not mistaken for 'unrelated'."""
    m = np.asarray(matrix, dtype=float)
    v = np.asarray(vector, dtype=float)
    vn = np.linalg.norm(v)
    if vn == 0:
        return np.full(len(m), np.nan)
    norms = np.linalg.norm(m, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (m @ v) / (norms * vn)
    out[norms == 0] = np.nan
    return out


def _average_ranks(x: np.ndarray) -> np.ndarray:
    """1-based ranks with ties sharing their average rank (numpy only: scipy
    is partly blocked by the Application Control policy on the team machines)."""
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x))
    ranks[order] = np.arange(1, len(x) + 1)
    sorted_x = x[order]
    start = 0
    for i in range(1, len(x) + 1):
        if i == len(x) or sorted_x[i] != sorted_x[start]:
            ranks[order[start:i]] = (start + 1 + i) / 2
            start = i
    return ranks


def rank_unit(values, valid=None) -> np.ndarray:
    """Percentile rank in [0, 1] among the valid entries (ties share their
    average rank). Invalid entries, and every entry when fewer than two are
    valid, get NEUTRAL."""
    x = np.asarray(values, dtype=float)
    ok = np.isfinite(x)
    if valid is not None:
        ok &= np.asarray(valid, dtype=bool)
    out = np.full(len(x), NEUTRAL)
    if ok.sum() >= 2:
        r = _average_ranks(x[ok])
        out[ok] = (r - 1) / (len(r) - 1)
    return out


def _mean_of_available(parts: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    """Per-creator mean of the rank arrays whose `available` flag is set;
    NEUTRAL where a creator has none of them."""
    n = len(parts[0][0])
    total, count = np.zeros(n), np.zeros(n)
    for ranks, available in parts:
        a = np.asarray(available, dtype=bool)
        total += np.where(a, ranks, 0.0)
        count += a
    return np.where(count > 0, total / np.maximum(count, 1), NEUTRAL)


def relevance(image_sim, has_img, text_sims, has_text) -> np.ndarray:
    """Brief relevance in [0, 1]. `text_sims` is a list of text similarity
    arrays (CLIP text and BERT) whose ranks are averaged into one text part;
    that part and the image part are then averaged over whichever the creator
    has. NEUTRAL for creators with no image and no text."""
    has_img, has_text = np.asarray(has_img, bool), np.asarray(has_text, bool)
    text_rank = np.mean([rank_unit(t, has_text) for t in text_sims], axis=0)
    return _mean_of_available([
        (rank_unit(image_sim, has_img), has_img & np.isfinite(image_sim)),
        (text_rank, has_text & np.all([np.isfinite(t) for t in text_sims], axis=0)),
    ])


def metadata(engagement, log_reach) -> np.ndarray:
    """Popularity-quality part in [0, 1]; NEUTRAL where both values are missing."""
    eng, reach = np.asarray(engagement, float), np.asarray(log_reach, float)
    return _mean_of_available([
        (rank_unit(eng), np.isfinite(eng)),
        (rank_unit(reach), np.isfinite(reach)),
    ])


def creator_feature_scores(
    clip_sim, has_img, text_sims, has_text, engagement, log_reach,
    w_relevance: float = W_RELEVANCE, w_metadata: float = W_METADATA,
) -> np.ndarray:
    """Final creator feature score per creator, in [0, 1]."""
    total = w_relevance + w_metadata
    if w_relevance < 0 or w_metadata < 0 or total <= 0:
        raise ValueError("weights must be non-negative and not both zero")
    rel = relevance(clip_sim, has_img, text_sims, has_text)
    meta = metadata(engagement, log_reach)
    return np.clip((w_relevance * rel + w_metadata * meta) / total, 0.0, 1.0)
