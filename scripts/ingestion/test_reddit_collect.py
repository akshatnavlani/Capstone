"""Tests for the pure parts of reddit_collect.py (no Reddit, no database)."""
import shutil

_real_which = shutil.which
shutil.which = lambda name, *a, **k: "stub" if name == "opencli" else _real_which(name, *a, **k)
import reddit_collect as rc  # noqa: E402
shutil.which = _real_which


def test_aliases_use_full_names_and_nicknames_but_not_a_lone_first_name():
    a = rc.aliases("Shivam Dubey (YourFitnessTories)", "yourfitnesstories", "yourfitnesstories")
    assert "shivam dubey" in a and "yourfitnesstories" in a
    assert rc.aliases("Roshan", "roshanehru", None) == {"roshanehru"}      # 'roshan' alone is ambiguous
    assert rc.aliases("Nirbhay", "fitandnirbhayyt", "fitandnirbhay") == {"fitandnirbhayyt", "fitandnirbhay"}


def test_short_or_generic_handles_do_not_count():
    assert rc.aliases("Fit", "fit", "fit") == set()                  # too short and generic
    assert rc.aliases("Gym India", "gymindia", None) == {"gymindia"}  # all-generic words are not a name


def test_match_is_whole_word_and_case_insensitive():
    a = rc.aliases("Ankit Baiyanpuria", "ankitbaiyanpuria", "ankit_baiyanpuria")
    assert rc.matches("Anyone follow Ankit Baiyanpuria's routine?", a)
    assert rc.matches("ankit_baiyanpuria workout", a)
    assert not rc.matches("my friend Ankit does the same", a)
    assert not rc.matches("xankitbaiyanpuriax", {"ankitbaiyanpuria"})


def test_subreddit_names_and_user_profiles():
    assert rc.clean_sub("r/Fitness_India") == "Fitness_India"
    assert rc.clean_sub("u/Feeling_Pea5770") is None
    assert rc.clean_sub("indianfitness") == "indianfitness"


def test_thread_json_becomes_comments_with_utc_times():
    raw = ('{"post": {"id": "1oo3lzv", "t": 1762250829, "sub": "indianfitness", "a": "x", "title": "T", "body": "B", "s": 91, "n": 39},'
           ' "comments": [{"id": "nn1hyj6", "t": 1762255365, "a": "[deleted]", "s": 43, "b": "[removed]", "p": "t3_1oo3lzv"},'
           ' {"id": "nn1idp6", "t": 1762255581, "a": "Cyber-blaster", "s": 40, "b": "science", "p": "t3_1oo3lzv"}]}')
    t = rc.parse_thread(raw)
    assert t["post"]["at"].isoformat() == "2025-11-04T10:07:09" and len(t["comments"]) == 2
    assert t["comments"][0]["at"].isoformat() == "2025-11-04T11:22:45"


def test_bad_thread_output_is_none():
    assert rc.parse_thread('{"status": 429}') is None
    assert rc.parse_thread("not json") is None
    assert rc.parse_thread(None) is None


def test_block_signals():
    assert rc.looks_blocked("HTTP 429 Too Many Requests")
    assert not rc.looks_blocked("ok")


def test_thread_takes_the_brand_named_in_its_title():
    assert rc.pick_brand("Why Naturaltein Yeast Protein feels spicy?", "I also tried Avvatar once, code ABC10") == "NaturalTein"
    assert rc.pick_brand("Best protein?", "Is Nutrabay good? Use code ABC10 on Nutrabay") == "Nutrabay"
    assert rc.pick_brand("Cardio or weights?", "no brands here") is None


def test_a_common_word_is_not_a_brand():
    assert rc.pick_brand("Intermittent fasting and red meat", "fast food is bad") is None
    assert rc.pick_brand("Is Red Skull Nutrition any good?", "") == "Red Skull Nutrition"
    assert "Fast&Up" in rc.brands_named("anyone tried Fast and Up reload?")


def test_search_words_never_carry_command_line_special_characters():
    assert rc.safe_query("Fast&Up") == "Fast Up"
    assert rc.safe_query('He said "hi" | ok > x') == "He said hi ok x"
    assert all(rc.safe_query(b) == b for b in rc.BRAND_QUERIES)      # the brand list itself is already clean


def test_every_brand_search_word_maps_to_a_brand_in_the_database_list():
    from known_brands import KNOWN_BRANDS
    names = {b[0].lower() for b in KNOWN_BRANDS} | {"optimumnutri"}
    for q in rc.BRAND_QUERIES:
        assert rc.BRAND_DB_NAME.get(q, q).lower() in names, q
