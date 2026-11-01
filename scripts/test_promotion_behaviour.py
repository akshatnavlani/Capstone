"""Pure helpers of scripts/run_promotion_behaviour.py: what counts as a disclosure, the Wilson interval, the neutral label."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_promotion_behaviour import disclosure_label, is_disclosed, wilson  # noqa: E402


def test_plain_tags_and_official_labels_are_disclosures():
    assert is_disclosed(["#ad"])
    assert is_disclosed(["sponsored by"])
    assert is_disclosed(["native:paid_partnership_label"])
    assert is_disclosed(["spoken:disclosure:promotion", "review:yes(Shimona)"])
    assert is_disclosed(["disclosure:#ad", "brand:Acme(name+code)"])


def test_a_brand_and_code_alone_is_not_a_disclosure():
    assert not is_disclosed(["brand:Acme(name+code)"])
    assert not is_disclosed(["spoken:brand:Acme(code)", "review:yes(Shimona)"])
    assert not is_disclosed(["comment:brand:Acme(name+code)"])
    assert not is_disclosed([])
    assert not is_disclosed(None)


def test_wilson_interval_is_sane():
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and 0.2 < hi < 0.35
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi
    assert wilson(0, 0) == (0.0, 1.0)


def test_label_is_neutral_wording():
    assert "most" in disclosure_label(0.8) and "few" in disclosure_label(0.05) and "some" in disclosure_label(0.4)
    assert "rarely" not in disclosure_label(0.0)
