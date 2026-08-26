import pytest

from ml.bot_detection import (
    BotSignals,
    account_age_score,
    compute_bot_score,
    engagement_mismatch_score,
    follower_following_ratio_score,
    is_bot_flagged,
    posting_frequency_score,
)


def test_follower_following_ratio_score_low_for_balanced_account():
    assert follower_following_ratio_score(follower_count=5000, following_count=800) < 0.3


def test_follower_following_ratio_score_high_for_mass_follower():
    assert follower_following_ratio_score(follower_count=100, following_count=5000) == 1.0


def test_follower_following_ratio_score_rejects_negative_counts():
    with pytest.raises(ValueError):
        follower_following_ratio_score(follower_count=-1, following_count=10)


def test_account_age_score_zero_for_old_account():
    assert account_age_score(1000) == 0.0


def test_account_age_score_high_for_brand_new_account():
    assert account_age_score(1) > 0.9


def test_account_age_score_zero_when_unavailable_not_treated_as_suspicious():
    # Instagram doesn't expose account_created_at per Track A's SCHEMA.md —
    # missing data must not be silently treated as a bot signal.
    assert account_age_score(None) == 0.0


def test_posting_frequency_score_low_for_normal_cadence():
    assert posting_frequency_score(1.5) < 0.2


def test_posting_frequency_score_high_for_spam_cadence():
    assert posting_frequency_score(50) == 1.0


def test_engagement_mismatch_score_ignored_for_small_accounts():
    # Small accounts have noisy engagement rates — not a bot signal on its own.
    assert engagement_mismatch_score(engagement_rate=0.0001, follower_count=500) == 0.0


def test_engagement_mismatch_score_high_for_large_account_low_engagement():
    assert engagement_mismatch_score(engagement_rate=0.0001, follower_count=500_000) > 0.9


def test_engagement_mismatch_score_zero_for_healthy_engagement():
    assert engagement_mismatch_score(engagement_rate=0.05, follower_count=500_000) == 0.0


def test_compute_bot_score_low_for_normal_account():
    normal = BotSignals(
        follower_count=5000,
        following_count=800,
        account_age_days=1000,
        posts_per_day=1.5,
        engagement_rate=0.03,
    )
    score = compute_bot_score(normal)
    assert score < 0.3
    assert not is_bot_flagged(score)


def test_compute_bot_score_high_for_obvious_bot():
    # follower_count kept >= 1000 so the engagement-mismatch heuristic is
    # actually in play too (it's intentionally a no-op below that floor).
    bot = BotSignals(
        follower_count=2000,
        following_count=10000,
        account_age_days=2,
        posts_per_day=60,
        engagement_rate=0.0001,
    )
    score = compute_bot_score(bot)
    assert score > 0.8
    assert is_bot_flagged(score)


def test_compute_bot_score_instagram_missing_age_still_flags_on_other_signals():
    # No account_age signal available, but the other three are all extreme.
    bot_no_age_data = BotSignals(
        follower_count=2000,
        following_count=10000,
        account_age_days=None,
        posts_per_day=60,
        engagement_rate=0.0001,
    )
    score = compute_bot_score(bot_no_age_data)
    assert is_bot_flagged(score)
