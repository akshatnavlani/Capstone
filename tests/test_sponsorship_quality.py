"""The label-quality model: hashing is deterministic, folds never split a creator, AUC is right, and a clear signal is learned and found on unseen creators."""
import numpy as np

from ml import sponsorship_quality as sq


def test_hashing_is_deterministic_and_bounded():
    a = sq.hashed_bag(sq.tokens("Use my code FIT20 for 20% off"), "h:")
    b = sq.hashed_bag(sq.tokens("Use my code FIT20 for 20% off"), "h:")
    assert np.array_equal(a, b) and a.shape == (sq.HASH_DIM,) and abs(np.linalg.norm(a) - 1.0) < 1e-9
    assert not sq.hashed_bag([], "h:").any()


def test_a_code_only_at_the_end_of_a_long_description_looks_like_a_footer():
    long_body = "workout vlog about my day " * 40 + "\nUse code FIT20"
    footer = sq.event_features({"tier": "brand_and_code", "title": "Leg day", "body": long_body})
    early = sq.event_features({"tier": "brand_and_code", "title": "Use code FIT20", "body": "Use code FIT20 now. " + "more " * 80})
    idx = len(sq.TIERS) + 4          # the in_footer flag
    assert footer[idx] == 1.0 and early[idx] == 0.0


def test_group_folds_never_split_a_creator():
    groups = ["a"] * 5 + ["b"] * 4 + ["c"] * 6 + ["d"] * 3
    folds = sq.group_folds(groups, 3, seed=0)
    seen = {}
    for f, idx in enumerate(folds):
        for i in idx:
            assert seen.setdefault(groups[i], f) == f
    assert sorted(np.concatenate(folds)) == list(range(len(groups)))


def test_auc_known_values():
    y = np.array([1, 1, 0, 0])
    assert sq.auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == 1.0
    assert sq.auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 0.0
    assert sq.auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == 0.5


def test_a_clear_signal_is_learned_and_found_on_creators_it_never_saw():
    rng = np.random.default_rng(0)
    rows, y, groups = [], [], []
    for i in range(160):
        ad = i % 2 == 0
        rows.append({"tier": "brand_and_code" if ad else "none", "title": "Sponsored by BrandX use code SAVE" if ad else "my morning routine",
                     "body": ("paid partnership " if ad else "") + "some words " * int(rng.integers(5, 30)), "n_evidence": 2 if ad else 0, "platform": "youtube"})
        y.append(int(ad))
        groups.append(f"creator{i % 20}")
    out = sq.cross_validate(rows, np.array(y), groups, k=5, repeats=2)
    assert out["auc"] > 0.95 and out["precision"] > 0.9 and out["recall"] > 0.9
