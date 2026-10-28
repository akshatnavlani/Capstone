from ml.creator_links import india_links


def test_only_collaborations_with_indian_people_count():
    people = {"i_creator"}          # an Indian creator; "i_team" is a team account, not a person
    collab = {("i_creator", "o1"), ("i_team", "o2")}
    out = india_links({"o1", "o2", "o3"}, people, collab, {"i_creator": "Some Creator"})
    assert set(out) == {"o1"} and "Some Creator" in out["o1"]
