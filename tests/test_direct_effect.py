import random
from datetime import date, timedelta

from ml.direct_effect import Post, effects_by_creator, overall, placebo_targets, post_effect, settled, shrink

D0 = date(2025, 6, 1)


def _creator(cid, n=40, base=1000.0, sponsored_mult=1.0, every=8, seed=0):
    rng = random.Random(seed)
    posts = []
    for i in range(n):
        sp = i % every == every - 1
        e = base * rng.uniform(0.7, 1.3) * (sponsored_mult if sp else 1.0)
        posts.append(Post(cid, "youtube", f"{cid}-{i}", D0 + timedelta(days=3 * i), e, sp))
    return posts


def test_post_effect_is_log_ratio_to_nearby_ordinary_median():
    posts = [Post("a", "youtube", str(i), D0 + timedelta(days=i), 99.0, False) for i in range(5)]
    sp = Post("a", "youtube", "s", D0 + timedelta(days=2), 199.0, True)
    import math
    assert abs(post_effect(sp, posts + [sp]) - math.log(200 / 100)) < 1e-12


def test_post_effect_needs_enough_baseline():
    posts = [Post("a", "youtube", "1", D0, 10.0, False)]
    sp = Post("a", "youtube", "s", D0, 20.0, True)
    assert post_effect(sp, posts + [sp]) is None


def test_recovers_planted_effects_and_placebo_is_zero():
    posts = _creator("up", sponsored_mult=2.0, seed=1) + _creator("flat", sponsored_mult=1.0, seed=2) \
        + _creator("down", sponsored_mult=0.5, seed=3)
    targets = [p for p in posts if p.sponsored]
    eff = effects_by_creator(targets, posts)
    sc = shrink(eff)
    assert sc["up"]["score"] > 0.4 and sc["down"]["score"] < -0.4 and abs(sc["flat"]["score"]) < 0.25
    counts = {c: len(v) for c, v in eff.items()}
    pl = overall(effects_by_creator(placebo_targets(posts, counts), posts), B=200)
    assert abs(pl["mean"]) < 0.15


def test_shrinkage_pulls_single_post_creators_toward_mean():
    eff = {"many": [0.1] * 20, "one": [2.0], **{f"c{i}": [0.0, 0.2, -0.1] for i in range(10)}}
    sc = shrink(eff)
    assert sc["one"]["score"] < 2.0 and sc["one"]["lo"] < sc["one"]["score"] < sc["one"]["hi"]


def test_settled_drops_recent_posts():
    p_old = Post("a", "youtube", "1", date(2026, 10, 1), 1.0, False)
    p_new = Post("a", "youtube", "2", date(2026, 10, 25), 1.0, False)
    assert settled([p_old, p_new], date(2026, 10, 27)) == [p_old]
