from ml.creator_links import india_links


def test_india_links_by_brand_or_collaboration():
    indian = {"i1", "i2"}
    deals = {"i1": {"B1"}, "o_brand": {"B1", "B7"}, "o_collab": {"B9"}, "o_none": {"B9"}}
    collab = {("i2", "o_collab")}
    out = india_links({"o_brand", "o_collab", "o_none"}, indian, deals, collab)
    assert set(out) == {"o_brand", "o_collab"}
    assert "brand" in out["o_brand"] and "collaborates" in out["o_collab"]
    named = india_links({"o_collab"}, indian, deals, collab, {"i2": "Mumbai Indians"})
    assert "Mumbai Indians" in named["o_collab"]


def test_brand_shared_only_with_other_overseas_does_not_count():
    out = india_links({"o1", "o2"}, {"i1"}, {"o1": {"B5"}, "o2": {"B5"}, "i1": {"B1"}}, set())
    assert out == {}
