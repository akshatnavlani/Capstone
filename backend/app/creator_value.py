"""Engagement per rupee for the ranking (Track A, task A4), read from models/creator_value.csv.

The file is written by scripts/direct_effect.py (Eesha, 6 Nov 2026). Per creator and platform it holds:
  - ranking_expected_engagement: the creator's normal recent engagement x one population sponsored-post
    adjustment (exp(-0.23), about 0.79), because per-creator direct-effect scores did not predict better;
  - cost_low/mid/high_inr: an ESTIMATED price of one post from the published rate card (data/cost_rate_card.csv);
  - engagement_per_1000_inr (+ _lo, _hi): expected engagement per Rs 1,000 at the mid cost (range: high to low cost).

Engagement units differ by platform (YouTube views+likes, Instagram likes+comments), so a raw per-rupee number
is only comparable within one platform. The ranking therefore uses the creator's PERCENTILE among creators on the
same platform, and picks the creator's best allowed platform.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

VALUE_PATH = Path(__file__).resolve().parents[2] / "models" / "creator_value.csv"
UNITS = {"youtube": "views + likes", "instagram": "likes + comments"}
SPONSORED_FACTOR_NOTE = "normal recent engagement x 0.79 (the average change on a sponsored post)"
_FLOATS = ("ranking_expected_engagement", "cost_low_inr", "cost_mid_inr", "cost_high_inr", "engagement_per_1000_inr",
           "engagement_per_1000_inr_lo", "engagement_per_1000_inr_hi", "direct_score", "direct_lo", "direct_hi")


def _num(v: str):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=4)
def load_values(path: Path = VALUE_PATH) -> dict[str, list[dict]]:
    """creator_id -> rows with a cost estimate, each with 'percentile' (0-100) within its platform."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if _num(r.get("engagement_per_1000_inr")) is not None]
    for r in rows:
        for k in _FLOATS:
            r[k] = _num(r.get(k))
        r["n_sponsored_posts"] = int(_num(r.get("n_sponsored_posts")) or 0)
    by_platform: dict[str, list[dict]] = {}
    for r in rows:
        by_platform.setdefault(r["platform"], []).append(r)
    for group in by_platform.values():
        group.sort(key=lambda r: r["engagement_per_1000_inr"])
        n = len(group)
        for i, r in enumerate(group):
            r["percentile"] = 100.0 * (i + 1) / n
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["creator_id"], []).append(r)
    return out


def best_value(rows: list[dict] | None, platforms: list[str] | None) -> dict | None:
    """The creator's row with the highest within-platform percentile, among the allowed platforms."""
    allowed = [r for r in rows or [] if not platforms or r["platform"] in platforms]
    return max(allowed, key=lambda r: r["percentile"]) if allowed else None


def _inr(x: float) -> str:
    if x >= 1e7:
        return f"Rs {x / 1e7:.1f} crore"
    if x >= 1e5:
        return f"Rs {x / 1e5:.1f} lakh"
    return f"Rs {x:,.0f}"


def explain(r: dict) -> list[str]:
    """The 'why' lines shown with a ranked creator, in plain words."""
    unit, platform = UNITS.get(r["platform"], "engagement"), r["platform"].capitalize()
    lines = [
        f"About {r['engagement_per_1000_inr']:,.0f} {unit} per Rs 1,000 on {platform} "
        f"(range {r['engagement_per_1000_inr_lo']:,.0f} to {r['engagement_per_1000_inr_hi']:,.0f}); "
        f"better than {r['percentile']:.0f}% of {platform} creators we hold",
        f"Expected about {r['ranking_expected_engagement']:,.0f} {unit} on one sponsored post: {SPONSORED_FACTOR_NOTE}",
        f"Estimated cost {_inr(r['cost_mid_inr'])} ({r.get('cost_tier') or 'unknown'} tier, range "
        f"{_inr(r['cost_low_inr'])} to {_inr(r['cost_high_inr'])}; published rate card, an estimate)",
    ]
    if r.get("direct_basis") == "measured":
        lines.append(f"Effect of sponsorship on this creator's own audience measured on {r['n_sponsored_posts']} sponsored "
                     f"posts ({r['direct_score']:+.2f} on the log scale); shown for context, the ranking uses the average")
    else:
        lines.append("No sponsored posts of this creator measured yet: the ranking uses the average sponsored-post change")
    if r.get("overseas") == "yes":
        lines.append(f"Not an Indian creator; kept because they collaborate with {r.get('india_link') or 'an Indian creator'}")
    return lines
