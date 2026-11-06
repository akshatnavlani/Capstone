import math
from datetime import date, timedelta

from ml.direct_effect import Post
from ml.prediction_check import History, predict, score, spearman

D0 = date(2026, 6, 1)


def post(i, day, eng, fmt="long", sponsored=False, creator="c1"):
    return Post(creator, "youtube", f"p{i}", D0 + timedelta(days=day), eng, sponsored, fmt)


def test_predict_uses_only_earlier_posts_and_format():
    ps = [post(0, 0, 99), post(1, 10, 999), post(2, 20, 9999, fmt="short"), post(3, 30, 99),
          post(4, 40, 10**6, sponsored=True), post(5, 50, 10**7)]
    h = History.of(ps)
    out = predict(h, D0 + timedelta(days=45), "long", recent_days=90, min_posts=3)
    assert math.isclose(out["ours"], (math.log(100) + math.log(1000) + math.log(100)) / 3)
    assert math.isclose(out["last_post"], math.log(100))          # day-30 post; later and sponsored ones unseen
    assert "ours" not in predict(h, D0 + timedelta(days=15), "long")  # only 2 earlier long posts


def test_spearman_and_score():
    assert math.isclose(spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
    assert math.isclose(spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
    rows = [{"creator": c, "actual": a, "m": a + 0.5} for c, a in
            [("a", 1), ("a", 1.2), ("a", 0.8), ("b", 3), ("b", 3.1), ("b", 2.9), ("c", 5), ("c", 5), ("c", 5)]]
    s = score(rows, "m")
    assert math.isclose(s["mae_log"], 0.5) and math.isclose(s["spearman_creators"], 1.0)
    assert score(rows, "missing")["n_posts"] == 0
