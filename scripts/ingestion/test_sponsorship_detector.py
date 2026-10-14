"""Tests for sponsorship_detector.py, using wording from real creator descriptions."""

from sponsorship_detector import boilerplate_lines, detect


def test_known_brand_with_a_code_is_sponsored():
    d = detect('Nakpro code : "Raha10"  Wellcore code : "Raha10"')
    assert d.is_sponsored and d.brand_name in {"Nakpro", "Wellcore"}
    assert any(e.startswith("brand:Nakpro") for e in d.evidence)


def test_disclosure_tag_alone_is_sponsored():
    d = detect("Loved this one! #Ad  link in bio")
    assert d.is_sponsored and "disclosure:#ad" in d.evidence


def test_platform_label_alone_is_sponsored():
    d = detect("new reel", has_paid_partnership_label=True)
    assert d.is_sponsored and d.evidence == ["native:paid_partnership_label"]


def test_code_without_a_known_brand_is_only_a_candidate():
    d = detect("Use code *YS30* for extra discount on the shop")
    assert not d.is_sponsored and d.candidate_only


def test_plain_text_is_not_sponsored():
    d = detect("Chest and triceps day, 5 sets of 10. Thanks for watching!")
    assert not d.is_sponsored and not d.candidate_only and d.evidence == []


def test_a_creator_collab_is_not_a_sponsorship():
    assert not detect("Great chat with my friend, in collaboration with the team").is_sponsored


def test_empty_text():
    assert not detect(None).is_sponsored


def test_partner_hashtag_in_an_ordinary_sentence_is_not_a_disclosure():
    assert not detect("Worst Foods for Your Partner #partner #food").is_sponsored


def test_repeated_footer_lines_are_ignored():
    from sponsorship_detector import boilerplate_lines
    footer = "hope you liked it :)\nMuscleBlaze Pre Workout code ABC10 on the site"
    descs = [footer] * 5
    bp = boilerplate_lines(descs)
    assert not detect(footer, title="Life Update", boilerplate=bp).is_sponsored
    assert detect(footer, title="MuscleBlaze Whey Gold review", boilerplate=bp).is_sponsored


def test_a_line_seen_only_once_is_not_boilerplate():
    from sponsorship_detector import boilerplate_lines
    assert boilerplate_lines(["Wellcore code ANKIT10 for creatine", "other text entirely here"]) == set()


def test_title_brand_with_repeated_code_line_counts():
    from sponsorship_detector import boilerplate_lines
    d = "use code ANKIT10 for all products on the site"
    bp = boilerplate_lines([d] * 5)
    out = detect(d, title="Wellcore Creatine Lemon Lime #shorts", boilerplate=bp)
    assert out.is_sponsored and out.brand_name == "Wellcore"


def test_negated_disclosure_is_not_a_disclosure():
    assert not detect("BEST CREATINE IN INDIAN MARKET || NO PAID PROMOTION").is_sponsored
    assert not detect("This video is not sponsored by anyone").is_sponsored
    assert detect("This video is sponsored by Acme").is_sponsored


def test_not_a_paid_promotion_is_a_negation():
    assert not detect("(Not a paid promotion, just something I personally use) healthy tomato ketchup").is_sponsored
    assert not detect("this is not an ad and not a paid promotion").is_sponsored
    assert detect("this is a paid promotion for Acme").is_sponsored


def test_brand_written_as_one_word_handle_is_found():
    assert detect("Why do I trust [@rippedupnutrition](/rippedupnutrition/) ?  Use code : SAGAR10").brand_name == "Ripped Up Nutrition"
    assert detect("Website https://bigmusclesnutrition.com  Use my code for extra discount BMRAHUL").brand_name == "BigMuscles Nutrition"


def test_mille_needs_a_mention_or_a_code():
    assert detect("@millesupergrain Use code MILLE5 on Amazon").brand_name == "Mille Supergrain"
    assert not detect("I walked a mille today").is_sponsored


def test_evidence_type_is_the_strongest_kind_present():
    assert detect("new reel", has_paid_partnership_label=True).evidence_type == "official_label"
    assert detect("Loved this #Ad").evidence_type == "disclosure_tag"
    assert detect('Nakpro code : "Raha10"').evidence_type == "brand_and_code"
    assert detect("Thanks @muscleblaze").evidence_type == "brand_mention"
    assert detect("Chest day").evidence_type is None
    assert detect("#ad with Nakpro code RAHA10", has_paid_partnership_label=True).evidence_type == "official_label"


def test_a_code_in_a_standing_footer_is_not_even_a_candidate():
    footer = "Use code *YS30* for extra discount on the shop"
    bp = boilerplate_lines([footer] * 5)
    assert not detect(footer, title="Leg day", boilerplate=bp).candidate_only
    assert detect(footer, title="Leg day").candidate_only                 # the same text, not a footer: a candidate
