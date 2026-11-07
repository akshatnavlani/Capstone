"""The Cai et al. (2015) adapter, on a tiny hand-made copy of the file layout
(the real data is not in the repo)."""

import pandas as pd
import pytest
import torch

from ml.cai_benchmark import load, permute_treatment, random_treatment


def _write(tmp_path):
    # Households 1-4 first round (1, 2 intensive), 5-8 second round, 9 second-round
    # household with an unknown friend. Village 1 = 1..4 + 5, 6; village 2 = the rest.
    ids = list(range(1, 10))
    survey = pd.DataFrame({
        "id": ids, "region": 1, "village": [1, 1, 1, 1, 1, 1, 2, 2, 2], "address": [1, 1, 1, 1, 1, 1, 2, 2, 2],
        "delay": [0, 0, 0, 0, 1, 1, 1, 1, 1], "intensive": [1, 1, 0, 0, 0, 1, 0, 1, 0],
        "info_none": 1, "takeup_survey": [1, 0, 1, 0, 1, 1, 0, 0, 1],
        "male": 1, "age": [30, 40, 50, 60, 35, 45, 55, 65, 33], "agpop": 4, "ricearea_2010": 10,
        "literacy": [1, 0, 1, 0, 1, 0, 1, 0, 1], "risk_averse": 0, "disaster_prob": 20,
    })
    # 5 names 1 (intensive), 3 (simple); 6 names 2 (intensive) and 777 (outside the
    # survey, but the network file says first-round intensive); 7 names 4; 8 names
    # 3 and 5; 9 names an unidentified person (99).
    rows = [(5, 1), (5, 3), (6, 2), (6, 777), (7, 4), (8, 3), (8, 5), (9, 99)]
    status = {i: (d, it) for i, d, it in zip(ids, survey.delay, survey.intensive)} | {777: (0, 1)}
    net = pd.DataFrame({
        "id": [r[0] for r in rows], "network_id": [float(r[1]) for r in rows],
        "delay": [status.get(r[1], (None, None))[0] for r in rows],
        "intensive": [status.get(r[1], (None, None))[1] for r in rows], "network_missname": 0.0,
    })
    d = tmp_path / "Data"
    d.mkdir()
    survey.to_stata(d / "0422survey.dta", write_index=False)
    net.astype({"delay": float, "intensive": float}).to_stata(d / "0422allinforawnet.dta", write_index=False)
    return tmp_path


def test_exposure_uses_all_named_friends_as_denominator(tmp_path):
    cd = load(_write(tmp_path))
    exp = dict(zip(cd.frame.id, cd.frame.exposure.round(4)))
    assert exp[5] == 0.5           # 1 of {1 intensive, 3 simple}
    assert exp[6] == 1.0           # 2 and the outside-survey friend 777 are both treated
    assert exp[7] == 0.0
    assert exp[8] == 0.0           # 3 simple, 5 second round
    assert exp[9] == 0.0           # an unknown friend counts in the denominator, untreated
    assert sorted(cd.frame.id) == [5, 6, 7, 8, 9]


def test_fake_assignments(tmp_path):
    cd = load(_write(tmp_path))
    for s in range(5):
        p = permute_treatment(cd, s)
        for v in cd.node_village.unique():
            m = (cd.node_village == v) & cd.first_round
            assert p[m].sum() == cd.treatment[m].sum()       # village counts kept
        assert (p[~cd.first_round] == 0).all()
        r = random_treatment(cd, s)
        assert (r[~cd.first_round] == 0).all()


def test_missing_data_is_a_clear_error(tmp_path):
    with pytest.raises(SystemExit):
        load(tmp_path)
