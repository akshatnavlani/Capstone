"""Tests for the pure parts of comment_sponsor_pass.py."""
from comment_sponsor_pass import comment_evidence, is_owner, standing_keys


def test_owner_is_the_channel_handle_or_title_ignoring_case_and_spaces():
    assert is_owner("@DesiGymReviews", "DesiGymReviews", "Desi Gym Reviews")
    assert is_owner("Desi Gym Reviews", "DesiGymReviews", "Desi Gym Reviews")
    assert not is_owner("random_viewer", "DesiGymReviews", "Desi Gym Reviews")
    assert not is_owner("", "DesiGymReviews", None) and not is_owner(None, None, None)


def test_comment_with_brand_and_code_is_evidence():
    ev = comment_evidence("Use code RAHA10 on Nakpro for 10% off")
    assert ev and ev[0].startswith("comment:brand:Nakpro(")


def test_comment_without_a_known_brand_or_code_is_not():
    assert comment_evidence("Thanks for watching, see you tomorrow!") == []
    assert comment_evidence(None) == []


def test_a_comment_repeated_on_four_videos_is_a_standing_comment():
    text = "Use code ANKIT10 on Nakpro for 10% off"
    rows = [("c1", f"v{i}", text) for i in range(4)] + [("c1", "v9", "Use code X on Wellcore only here")]
    keys = standing_keys(rows)
    assert ("c1", "use code ankit10 on nakpro for 10% off") in keys and len(keys) == 1
    assert standing_keys(rows[:3]) == set()
