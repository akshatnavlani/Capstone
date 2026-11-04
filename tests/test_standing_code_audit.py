from datetime import datetime, timedelta

from ml.standing_code_audit import Video, classify, codes, mentions

T0 = datetime(2026, 9, 1)


def v(i, day, desc, title="video"):
    return Video(f"v{i}", "c1", T0 + timedelta(days=day), title, desc)


def test_codes_and_mentions():
    assert codes('Use code "EESHA10" for 10% off, coupon: fit-20') == {"EESHA10", "FIT-20"}
    assert codes("code for the link below") == set()
    assert mentions("Thanks to MuscleBlaze!", "muscleblaze") == 10
    assert mentions("muscleblazer fan", "MuscleBlaze") == -1


def test_onset_new_code_and_standing():
    block = "Gear: MuscleBlaze code EESHA10"
    vids = [v(0, 0, block), v(1, 3, block), v(2, 6, "MuscleBlaze code DIWALI25"), v(3, 9, block)]
    assert classify(vids[0], "MuscleBlaze", vids)["label"] == "new_onset"   # first in the run
    assert classify(vids[1], "MuscleBlaze", vids)["label"] == "standing"    # same code repeated
    assert classify(vids[2], "MuscleBlaze", vids)["label"] == "new_code"    # new campaign code
    assert classify(vids[3], "MuscleBlaze", vids)["label"] == "standing"


def test_gap_longer_than_window_restarts_the_deal():
    block = "MuscleBlaze code EESHA10"
    vids = [v(0, 0, block), v(1, 45, block)]
    assert classify(vids[1], "MuscleBlaze", vids)["label"] == "new_onset"
