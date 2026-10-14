"""Tests for known_brands.py, using wording taken from real creator bios and descriptions."""

from known_brands import best_brand_for_text, match_known_brands


def _names(text):
    return {m.name for m in match_known_brands(text) if m.strong}


def test_handle_mention_with_a_code_is_strong():
    assert _names("⛽:- @fuelone.in @muscleblaze ABHI30") == {"FuelOne", "MuscleBlaze"}


def test_brand_with_a_quoted_code_is_strong():
    assert best_brand_for_text("Supps @naturaltein_india: Code ‘HYPER’").name == "NaturalTein"


def test_name_with_a_discount_code_is_strong_without_a_handle():
    assert best_brand_for_text("Use code SIDD10 on Wellcore for 15% off").name == "Wellcore"


def test_trailing_dot_in_a_mention_still_matches():
    assert best_brand_for_text("Partner @wellcore.in. code BHAARAT10").name == "Wellcore"


def test_a_bare_brand_name_is_not_enough():
    assert best_brand_for_text("I trained in my new Puma shoes today") is None
    assert [m.strong for m in match_known_brands("my Puma shoes")] == [False]


def test_a_disclosure_tag_beside_the_name_is_strong():
    assert best_brand_for_text("Paid partnership with Nike. Loving the new drop #ad").name == "Nike"


def test_an_ordinary_word_brand_needs_a_mention_or_code():
    assert best_brand_for_text("Campus life vlog, day in the dorm") is None
    assert best_brand_for_text("Dynamite workout today, full body") is None
    assert best_brand_for_text("@dynamite.preworkout code UN10").name == "Dynamite"


def test_alias_and_spacing_variants():
    assert best_brand_for_text("Muscle Blaze whey, use code ANKUSH").name == "MuscleBlaze"
    assert best_brand_for_text("Black Beast pre workout, coupon BEAST5").name == "Black Beast Nutrition"


def test_an_at_mention_is_not_double_counted_as_a_name():
    m = [x for x in match_known_brands("@muscleblaze") if x.name == "MuscleBlaze"][0]
    assert m.signals == ["mention"]


def test_prefers_the_mentioned_brand_when_several_are_named():
    assert best_brand_for_text("Compare Nike and Puma. Code SAVE10 at @pumaindia").name == "Puma"


def test_empty_and_unrelated_text():
    assert best_brand_for_text("") is None
    assert best_brand_for_text(None) is None
    assert best_brand_for_text("Chest and triceps day, 5 sets of 10") is None


def test_one_description_can_promote_several_brands():
    from known_brands import all_strong_brands
    text = 'Avvatar Discount code : "Desigym" Nakpro code : "Raha10" Blackbeast code : "Desigym" Nutrabay Code : "Desigym"'
    assert {m.name for m in all_strong_brands(text)} == {"Avvatar", "Nakpro", "Black Beast Nutrition", "Nutrabay"}


def test_cult_store_mention_is_strong():
    assert best_brand_for_text("Shop now @cultstoreindia  get 10% off").name == "Cult.fit"


def test_common_word_brand_needs_a_mention_or_code():
    assert best_brand_for_text("my lifelong goal is to lift, thanks to my team") is None
    assert best_brand_for_text("Lifelong code RAHA10 for 10% off").name == "Lifelong"


def test_soniya_bio_names_three_brands():
    bio = ("🔸 Managed by @imddxb 🇮🇳 🇦🇪 \n🔸 @rippedupnutrition @redskullnutrition1 : fitgirl\n"
           "🔸 @trueforma.nutrition : FitGirl10\n✉️ : team@example.com")
    assert _names(bio) == {"Ripped Up Nutrition", "Red Skull Nutrition", "TrueForma"}


def test_brand_written_as_one_word_url_or_product_is_found():
    assert best_brand_for_text("Buy it now https://asitisnutrition.com/products/pure-creatine use code ABC10").name == "AsItIs Nutrition"
    assert best_brand_for_text("use code :- ANKITRS  for  CARNIVOX").name == "Red Skull Nutrition"
    assert best_brand_for_text("get 50% off all Lifespan memberships with code RAJ2026").name == "Lifespan"
    assert best_brand_for_text("I want a longer lifespan") is None
