"""Helpers of the direct-effect and out-of-time ranking scripts: own-post comparison, rank correlation, NDCG."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_direct_effect as de  # noqa: E402
import run_ranking_test as rk  # noqa: E402


def _posts(n_plain, sponsored_value):
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    posts = [{"date": base + timedelta(days=i), "sponsored": False, "views": 5.0} for i in range(n_plain)]
    posts.append({"date": base + timedelta(days=3), "sponsored": True, "views": sponsored_value})
    return posts


def test_sponsored_post_is_compared_with_the_creators_own_typical_post():
    out = de.effects(_posts(12, 6.0), "sponsored", "views")
    assert len(out) == 1 and abs(out[0][1] - 1.0) < 1e-9


def test_too_few_comparison_posts_gives_no_effect():
    assert de.effects(_posts(3, 6.0), "sponsored", "views") == []


def test_plain_posts_are_compared_without_sponsored_ones():
    out = de.effects(_posts(12, 99.0), "plain", "views")
    assert out and all(abs(e) < 1e-9 for _, e in out)


def test_spearman_and_ties():
    assert abs(rk.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-9
    assert abs(rk.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert rk.ranks([5, 5, 1]) == [2.5, 2.5, 1.0]


def test_ndcg_is_one_for_the_ideal_order():
    gain = {"a": 3.0, "b": 2.0, "c": 0.0}
    assert abs(rk.ndcg_at(["a", "b", "c"], gain) - 1.0) < 1e-9 and rk.ndcg_at(["c", "b", "a"], gain) < 1.0




def test_semisynthetic_placebo_removes_an_injected_trend_and_detects_a_planted_effect():
    import numpy as np

    import sim_semisynthetic_benchmark as sim

    rng = np.random.default_rng(0)
    rows = [(f"n{i}", float(rng.normal(0, 0.3)), float(rng.normal(0, 0.3))) for i in range(40) for _ in range(5)]
    table = sim.simulate(rows, reps=60, inner=100, seed=1)
    assert table["0.0"]["naive"]["error_vs_truth"] > 0.1          # the injected trend biases the naive analysis
    assert abs(table["0.0"]["placebo"]["error_vs_truth"]) < 0.1    # the placebo comparison cancels it
    assert table["1.0"]["placebo"]["detects_effect_share"] > 0.9 and table["0.0"]["placebo"]["detects_effect_share"] < 0.2
