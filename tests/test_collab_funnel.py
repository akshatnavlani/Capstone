from datetime import datetime, timedelta

from ml.collab_funnel import mentions, straddles


def test_mentions_skip_emails_and_trailing_dots():
    text = "Collab with @FitWithPriya and @gym.bro_99. Mail me: hello@gmail.com"
    assert mentions(text) == {"fitwithpriya", "gym.bro_99"}


def test_straddles():
    e = datetime(2026, 9, 15)
    posts = sorted(e + timedelta(days=d) for d in (-40, -5, 10))
    assert straddles(e, posts, 30)
    assert not straddles(e, posts, 7)          # +10 is outside a 7-day window
    assert not straddles(e, [e - timedelta(days=3)], 30)
