"""Tests for spoken_sponsor.py with wording taken from real auto-captions (no network)."""
from spoken_sponsor import spoken_evidence

HINDI = ("तो ये वेलकोर का लेमन लाइम फ्लेवर मेरे पास कल ही आया है। और हां डिस्क्रिप्शन में लिंक है और कोड SHIVAM10 यूज़ करना मत भूलना")


def test_devanagari_brand_with_a_code_phrase_is_found():
    assert "spoken:brand:Wellcore(code)" in spoken_evidence(HINDI)


def test_english_brand_with_a_code_phrase_is_found():
    assert "spoken:brand:Nutrabay(code)" in spoken_evidence("this is Nutrabay yeast protein, use my code SHIVA for a discount")


def test_explicit_sponsor_phrase_is_a_disclosure():
    ev = spoken_evidence("this video is sponsored by a brand you will see shortly")
    assert ev and ev[0].startswith("spoken:disclosure:")


def test_brand_without_a_nearby_code_or_sponsor_phrase_is_not_enough():
    assert spoken_evidence("I trained chest today and finished with a MuscleBlaze shake at home " + "blah " * 80 + "see you tomorrow") == []


def test_plain_talk_and_empty_input():
    assert spoken_evidence("Today we do chest and triceps, five sets of ten") == []
    assert spoken_evidence(None) == [] and spoken_evidence("") == []
