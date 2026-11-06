import math
from pathlib import Path

from ml.cost_estimate import estimate, load_rate_card

CARD = load_rate_card(Path(__file__).resolve().parents[1] / "data" / "cost_rate_card.csv")


def test_tiers_formats_and_mid():
    e = estimate(CARD, "instagram", "video", 50_000)
    assert e["tier"] == "micro" and e["low"] == 8000 and e["high"] == 80000
    assert math.isclose(e["mid"], math.sqrt(8000 * 80000))
    assert estimate(CARD, "youtube", "short", 50_000)["high"] == 80000        # shorts ~ reels
    assert estimate(CARD, "youtube", "long", 50_000)["high"] == 320000        # integration 2x-4x
    assert estimate(CARD, "youtube", "unknown", 50_000)["high"] == 320000
    assert estimate(CARD, "instagram", "image", 5_000_000)["tier"] == "mega"
    assert estimate(CARD, "instagram", "image", 10_000)["tier"] == "micro"    # boundary goes up
    assert estimate(CARD, "instagram", "image", None) is None


def test_card_has_no_gaps():
    for platform, fmt in (("instagram", "any"), ("youtube", "short"), ("youtube", "long")):
        rows = sorted((r for r in CARD if r["platform"] == platform and r["format"] == fmt), key=lambda r: r["min"])
        assert rows[0]["min"] == 0 and rows[-1]["max"] is None
        assert all(a["max"] == b["min"] for a, b in zip(rows, rows[1:]))
