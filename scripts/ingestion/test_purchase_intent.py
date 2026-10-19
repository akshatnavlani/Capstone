"""Tests for purchase_intent.py (no database)."""
import purchase_intent as pi


def kinds(text):
    return [k for k, _ in pi.purchase_intent(text)]


def test_says_they_ordered_or_bought():
    assert kinds("Just ordered this, can't wait") == ["bought"]
    assert kinds("maine order kiya kal") == ["bought"]
    assert kinds("I bought it from Amazon") == ["bought"]
    assert kinds("your code worked, thanks bro") == ["bought"]
    assert kinds("मैंने ऑर्डर कर दिया") == ["bought"]


def test_asks_where_or_how_much():
    assert kinds("link please") == ["asking"]
    assert kinds("Kahan se milega ye?") == ["asking"]
    assert kinds("price?") == ["asking"]
    assert kinds("Where can I buy this protein") == ["asking"]
    assert kinds("kitne ka hai") == ["asking"]


def test_both_kinds_in_one_comment():
    assert kinds("ordered it yesterday, what is the price of this?") == ["bought", "asking"]


def test_ordinary_comments_do_not_match():
    for t in ["Great workout bro", "Which exercise is this?", "my order of exercises is chest first", "what a price to pay for glory",
              "bought a gym membership years ago and regret nothing", "", None]:
        assert kinds(t) == [], t
    assert kinds("Great workout bro") == []
    assert kinds("Which exercise is this?") == []
    assert kinds("") == [] and kinds(None) == []


def test_everyday_phrases_found_in_the_first_sample_do_not_match():
    assert kinds("1 dosa bol ke 2 dosa le liya aapne") == []
    assert kinds("Purchased rights to it I assume?") == []
    assert kinds("I bought the patek and the rolex") == []
    assert kinds("Chapters:<br><a href=\"https://youtu.be/x?what-is-the-cost\">00:00</a> Intro") == []
    assert kinds("mehnat se kamaye paise se खरीदा सामान") == []


def test_html_markup_is_ignored_but_the_comment_text_still_counts():
    assert kinds("link please<br>thanks <a href=\"https://example.com\">x</a>") == ["asking"]


def test_words_must_be_whole():
    assert kinds("reordered nothing") == []
    assert kinds("blinking link?") == ["asking"]   # 'link?' is a request for a link
