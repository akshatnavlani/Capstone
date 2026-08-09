"""Precision validation for app/labeling.py -- this is the sole source of
GAIL's treatment labels (PROJECT_PLAN.md Section 1), so false positives are
tested for explicitly and deliberately, not just "does it find #ad".

Includes real scraped text pulled from the live Supabase DB (ATHLEAN-X
YouTube descriptions, 2026-08-09) as grounded negative/decoy cases, plus
synthetic cases targeting the specific regex risks a naive substring match
would fall into (#adidas, #adventure, "advice", "spontaneous", genuine
institutional-affiliation language that superficially resembles a brand
partnership disclosure).
"""

from app.labeling import detect_sponsorship

# ---- Positive cases: every disclosure convention named in PROJECT_PLAN.md
# Section 1 ("#ad, #sponsored, 'in partnership with', including
# variants/misspellings"), plus the extra conventions this module added. ----

def test_hashtag_ad():
    found, matches = detect_sponsorship("Check out this cool gear! #ad")
    assert found is True
    assert matches == ["#ad"]


def test_hashtag_sponsored():
    found, matches = detect_sponsorship("New drop from my favorite brand #sponsored")
    assert found is True
    assert matches == ["#sponsored"]


def test_sponsored_by_phrase():
    found, matches = detect_sponsorship("This video is sponsored by BrandX")
    assert found is True
    assert matches == ["sponsored by"]


def test_in_partnership_with_brand():
    found, matches = detect_sponsorship("In partnership with Nike, we're excited to launch this")
    assert found is True
    # Matched substring preserves original casing (audit-trail fidelity) --
    # the sentence starts with capital "In", so that's what should come back.
    assert matches == ["In partnership with"]


def test_paid_partnership():
    found, matches = detect_sponsorship("This is a paid partnership with BrandY")
    assert found is True
    assert matches == ["paid partnership"]


def test_brought_to_you_by():
    found, matches = detect_sponsorship("Brought to you by our friends at Acme Corp")
    assert found is True


def test_common_misspelling_sponser():
    found, matches = detect_sponsorship("Thanks to our sponser BrandZ for making this possible")
    assert found is True
    assert matches == ["sponser"]


def test_spon_con_variant():
    found, matches = detect_sponsorship("just a lil spon-con for my favorite skincare brand")
    assert found is True


def test_multiple_matches_all_returned():
    found, matches = detect_sponsorship("#ad #sponsored in partnership with BrandX")
    assert found is True
    assert len(matches) == 3


def test_case_insensitive():
    found, matches = detect_sponsorship("SPONSORED BY BrandX")
    assert found is True


def test_matches_across_multiple_fields():
    # title + description, mirrors how the pipeline calls this with two DB columns
    found, matches = detect_sponsorship("Cool new video", "This one is #ad btw")
    assert found is True


# ---- Negative / decoy cases: the actual precision test. Every one of
# these was chosen because a naive substring match (not word-boundary-aware)
# would false-positive on it. ----

def test_no_sponsorship_language_at_all():
    found, matches = detect_sponsorship("Check out my new workout routine!")
    assert found is False
    assert matches == []


def test_hashtag_adventure_is_not_hashtag_ad():
    found, matches = detect_sponsorship("#adventure time with my dog today")
    assert found is False


def test_hashtag_adidas_is_not_hashtag_ad():
    found, matches = detect_sponsorship("#adidas shoes review, just my honest opinion")
    assert found is False


def test_advice_does_not_contain_standalone_ad():
    found, matches = detect_sponsorship("My advice for beginners: start slow and be consistent")
    assert found is False


def test_spontaneous_does_not_match_spon_con():
    found, matches = detect_sponsorship("Went on a spontaneous adventure today, no plans at all")
    assert found is False


def test_institutional_partnership_is_not_brand_sponsorship():
    # Genuinely ambiguous-sounding phrase -- "partnership" with an
    # institution, not a brand disclosure. The exact wording is deliberately
    # NOT "in partnership with" (which we do want to catch) -- this tests
    # that mentioning a university/institution alone doesn't false-positive.
    found, matches = detect_sponsorship(
        "He earned his degree at the University of Connecticut and has a long-standing "
        "relationship with the athletic department there."
    )
    assert found is False


def test_real_athleanx_description_no_false_positive():
    # Pulled verbatim from the live DB (video_id CTblai7olJo, 2026-08-09) --
    # a real, substantial (4600+ char) description that's entirely
    # self-promotional (own website/program, not a paid brand disclosure).
    # This is exactly the kind of text a precision-critical labeler needs
    # to get right: lots of promotional language, zero actual sponsorship.
    description = (
        "Build Bigger Arms Here - https://athleanx.com\n"
        "Subscribe to this channel here - http://bit.ly/2b0coMW\n\n"
        "Want to know how to get bigger arms in just 22 days? In this ATHLEAN-X arm "
        "workout, Jeff Cavaliere lays out a step-by-step plan to help you build bigger "
        "biceps, bigger triceps, and more noticeable arm size without adding a full arm "
        "day to your weekly split.\n\n"
        "If you are looking for a complete workout plan to build muscle, get stronger, "
        "and develop an athletic body from head to toe, visit ATHLEANX.com and use the "
        "program selector to find the best training program for your goals.\n\n"
        "For more videos on how to get bigger arms, how to build big biceps, how to "
        "build big triceps, the best arm exercises, and complete biceps and triceps "
        "workouts, subscribe to ATHLEAN-X and turn on notifications so you never miss a "
        "new video."
    )
    found, matches = detect_sponsorship(description)
    assert found is False


def test_real_athleanx_bio_credentials_no_false_positive():
    # Pulled verbatim from the live DB (video_id ZVUjuyavXYE, 2026-08-09) --
    # professional credentials/affiliations (former team, university),
    # exactly the kind of institutional-affiliation text that risks
    # false-positiving on a loose "partnership"/"sponsor" keyword search.
    bio = (
        "Jeff Cavaliere MSPT, CSCS served as both the head physical therapist and "
        "assistant strength coach for the New York Mets. Jeff earned his Masters of "
        "Physical Therapy and Bachelor's of Physioneurobiology from the College of "
        "Health Sciences University of Connecticut Storrs. He is a certified Strength "
        "and Conditioning Specialist by the National Strength and Conditioning "
        "Association (NSCA)."
    )
    found, matches = detect_sponsorship(bio)
    assert found is False


def test_none_and_empty_text():
    assert detect_sponsorship(None) == (False, [])
    assert detect_sponsorship("") == (False, [])
    assert detect_sponsorship(None, None) == (False, [])
    assert detect_sponsorship(None, "") == (False, [])


def test_brand_name_mention_alone_is_not_a_disclosure():
    # Mentioning a brand by name isn't the same as disclosing a paid deal --
    # PROJECT_PLAN.md Section 1 is explicit that only the disclosure tag
    # itself is the signal, not brand mentions in general.
    found, matches = detect_sponsorship("Thanks for 10k followers!! Wearing my favorite Nike kicks today")
    assert found is False
