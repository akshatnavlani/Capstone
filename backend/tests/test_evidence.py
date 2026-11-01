"""Evidence grade (app/evidence.py): thin data must never grade high, rich data must."""
from app.evidence import grade_evidence


def test_rich_data_grades_a():
    grade, notes = grade_evidence("inferred", {"basis": "scored", "n_comments": 1200}, {"basis": "scored"}, "youtube+instagram")
    assert grade == "A"
    assert any("1,200" in n for n in notes)


def test_no_data_grades_d():
    grade, notes = grade_evidence("isolated", {"basis": "placeholder", "n_comments": 0}, {"basis": "neutral"}, "none")
    assert grade == "D"
    assert len(notes) == 4


def test_spillover_alone_cannot_lift_the_grade():
    # a trained creator with nothing else still grades D: the spillover point is capped at 1
    assert grade_evidence("trained", None, None, "none")[0] == "D"


def test_one_platform_and_some_comments_is_c_or_b():
    grade, _ = grade_evidence("isolated", {"basis": "scored", "n_comments": 50}, {"basis": "scored"}, "youtube")
    assert grade == "B"  # 1 + 2 + 1 = 4
    grade, _ = grade_evidence("isolated", {"basis": "scored", "n_comments": 50}, {"basis": "neutral"}, "youtube")
    assert grade == "C"  # 1 + 0 + 1 = 2


def test_missing_infos_do_not_crash():
    assert grade_evidence("placeholder", None, None, "youtube")[0] == "D"  # 0 + 0 + 1 + 0
