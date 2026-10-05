"""Tests for ml/feature_score.py (PendingWork S2). Pure numpy: no model, no DB."""

import numpy as np
import pytest

from ml.feature_score import (
    NEUTRAL,
    cosine,
    creator_feature_scores,
    metadata,
    rank_unit,
    relevance,
)


def test_cosine_values_and_zero_row_is_nan():
    m = np.array([[1.0, 0.0], [0.0, 2.0], [0.0, 0.0]])
    c = cosine(m, np.array([1.0, 0.0]))
    assert c[0] == pytest.approx(1.0)
    assert c[1] == pytest.approx(0.0)
    assert np.isnan(c[2])  # no embedding is not the same as "unrelated"


def test_cosine_zero_query_is_all_nan():
    assert np.isnan(cosine(np.eye(2), np.zeros(2))).all()


def test_rank_unit_spans_zero_to_one_and_ties_share_a_rank():
    r = rank_unit([10.0, 30.0, 20.0, 20.0])
    assert r[0] == 0.0 and r[1] == 1.0
    assert r[2] == r[3] == 0.5  # ranks 1, 2.5, 2.5, 4 -> (r - 1) / 3


def test_rank_unit_invalid_and_too_few_are_neutral():
    r = rank_unit([1.0, np.nan, 3.0, 2.0], valid=[True, True, True, False])
    assert r[1] == NEUTRAL and r[3] == NEUTRAL
    assert (r[0], r[2]) == (0.0, 1.0)
    assert (rank_unit([5.0]) == NEUTRAL).all()
    assert (rank_unit([np.nan, np.nan]) == NEUTRAL).all()


def test_relevance_uses_whichever_signals_exist():
    clip = np.array([0.9, 0.1, np.nan, np.nan])
    has_img = np.array([True, True, False, False])
    bert = np.array([np.nan, 0.2, 0.8, np.nan])
    has_text = np.array([False, True, True, False])
    r = relevance(clip, has_img, [bert], has_text)
    assert r[3] == NEUTRAL  # no image and no text
    assert r[0] == 1.0      # best image match, no text
    assert r[2] == 1.0      # best text match, no image
    assert r[1] == 0.0      # worst on both


def test_text_part_averages_both_text_methods():
    n = 3
    a = np.array([0.0, 0.5, 1.0])   # ranks 0, .5, 1
    b = np.array([1.0, 0.5, 0.0])   # ranks 1, .5, 0 (disagrees with a)
    r = relevance(np.full(n, np.nan), np.zeros(n, bool), [a, b], np.ones(n, bool))
    assert np.allclose(r, 0.5)      # two opposite opinions cancel out
    r2 = relevance(np.full(n, np.nan), np.zeros(n, bool), [a, a], np.ones(n, bool))
    assert np.allclose(r2, [0.0, 0.5, 1.0])


def test_metadata_neutral_when_missing():
    m = metadata([0.01, 0.05, np.nan], [10.0, 12.0, np.nan])
    assert m[2] == NEUTRAL
    assert m[1] > m[0]


def test_scores_bounded_and_missing_creator_is_exactly_neutral():
    n = 6
    rng = np.random.default_rng(0)
    clip = rng.normal(size=n)
    bert = rng.normal(size=n)
    has_img = np.array([True, True, True, False, False, False])
    has_text = np.array([True, True, False, True, False, False])
    eng = np.array([0.01, 0.02, np.nan, 0.03, np.nan, np.nan])
    reach = np.array([10.0, 11.0, 12.0, np.nan, np.nan, np.nan])
    s = creator_feature_scores(clip, has_img, [bert, bert[::-1]], has_text, eng, reach)
    assert ((s >= 0) & (s <= 1)).all()
    assert s[5] == NEUTRAL  # nothing known about this creator


def test_planted_relevance_effect_raises_the_score():
    n = 8
    bert = np.linspace(0.0, 1.0, n)  # creator 7 is most relevant
    s = creator_feature_scores(np.full(n, np.nan), np.zeros(n, bool), [bert], np.ones(n, bool),
                               np.full(n, np.nan), np.full(n, np.nan))
    assert np.all(np.diff(s) > 0)
    assert s.argmax() == n - 1


def test_weights_are_validated():
    z = np.zeros(2)
    with pytest.raises(ValueError):
        creator_feature_scores(z, z.astype(bool), [z], z.astype(bool), z, z, w_relevance=0.0, w_metadata=0.0)
    with pytest.raises(ValueError):
        creator_feature_scores(z, z.astype(bool), [z], z.astype(bool), z, z, w_relevance=-1.0)
