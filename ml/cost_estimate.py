"""Estimated cost of one sponsored post (Track A, task A3).

Published Indian rate-card ranges by follower tier (data/cost_rate_card.csv,
from upGrowth's 2026 pricing guide). The point estimate is the geometric mean
of the range, since prices spread multiplicatively. These are ESTIMATES: label
them so wherever they are shown.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path


def load_rate_card(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [{**r, "min": int(r["min_followers"]),
                 "max": int(r["max_followers"]) if r["max_followers"] else None,
                 "low": float(r["low_inr"]), "high": float(r["high_inr"])} for r in csv.DictReader(f)]


def estimate(card: list[dict], platform: str, fmt: str, followers: float | None) -> dict | None:
    """{tier, low, mid, high} in INR for one post, or None without a follower count.
    YouTube formats other than 'short' are priced as integrations ('long');
    Instagram uses one row set for every media type."""
    if not followers or followers <= 0:
        return None
    f = "any" if platform == "instagram" else ("short" if fmt == "short" else "long")
    for r in card:
        if r["platform"] == platform and r["format"] == f and r["min"] <= followers and (r["max"] is None or followers < r["max"]):
            return {"tier": r["tier"], "low": r["low"], "high": r["high"], "mid": math.sqrt(r["low"] * r["high"])}
    return None


def percentiles(values: list[float]) -> list[float]:
    """Percentile rank in [0, 1] of each value among `values` (lowest 0, highest 1,
    ties share their average rank). A single value gets 0.5."""
    n = len(values)
    if n == 1:
        return [0.5]
    order = sorted(range(n), key=lambda i: values[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = ((i + j) / 2) / (n - 1)
        i = j + 1
    return out
