import standing_code_unflag_20261101 as S


def vid(i, day, brands, evidence="brand_and_code", sponsored=True, title="Back day", kind="name+code"):
    return {"id": f"v{i}", "t": float(day), "sponsored": sponsored, "evidence": evidence, "title": title,
            "matches": [f"brand:{b}({kind})" for b in brands]}


def test_same_brand_in_most_videos_is_standing():
    vs = [vid(i, i, ["Gymshark"]) for i in range(12)]
    assert S.find_standing(vs) == {f"v{i}" for i in range(12)}


def test_one_off_sponsored_video_stays():
    vs = [vid(i, i * 2, ["Gymshark"], sponsored=False, evidence=None) for i in range(12)]
    vs[5] = vid(5, 10, ["Gymshark"])
    assert S.find_standing(vs) == set()


def test_real_labels_and_title_brands_stay():
    vs = [vid(i, i, ["Gymshark"]) for i in range(12)]
    vs[3] = vid(3, 3, ["Gymshark"], evidence="official_label")
    vs[4] = vid(4, 4, ["Gymshark"], title="Gymshark haul and review")
    vs[5] = vid(5, 5, ["Gymshark"], kind="title+code")
    got = S.find_standing(vs)
    assert {"v3", "v4", "v5"}.isdisjoint(got) and len(got) == 9


def test_code_list_of_three_brands_is_standing_even_if_rare():
    vs = [vid(0, 0, ["A", "B", "C"])] + [vid(i, i * 40, [], sponsored=False, evidence=None) for i in range(1, 8)]
    assert S.find_standing(vs) == {"v0"}
    assert S.find_standing([vid(0, 0, ["A", "B"])] + vs[1:]) == set()
