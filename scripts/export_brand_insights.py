"""Brand Analysis page data (23 Nov 2026): the few results a brand can act on, copied from their result files.

    python scripts/export_brand_insights.py      # writes frontend/public/brand_insights.json

Reads result files only (no database, no new analysis). Each block keeps its source file and date so the page can say
how current it is.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "models" / name).read_text(encoding="utf-8"))


def main() -> int:
    cp = load("cross_promotion_mechanism_10nov.json")  # 10 Nov update of the detected cross-platform test (105 creators)
    pp = load("platform_pairs.json")                   # same creator, both platforms within 24 h
    pr = load("promotion_behaviour.json")              # disclosure and buying-looking comments
    fa = load("ad_fatigue.json")                       # views after heavier sponsored load

    fwd = cp["update_detected_test_today"]["Instagram posts -> YouTube comments"]
    rev = cp["update_detected_test_today"]["YouTube comments -> Instagram posts"]
    counts = Counter(c.get("stronger_platform") for c in pp["creators"])
    views = next(r for r in fa["results"] if r["outcome"].startswith("views"))
    rate = next(r for r in fa["results"] if r["outcome"].startswith("like+comment"))

    out = {
        "cross_platform": {
            "source": "models/cross_promotion_mechanism_10nov.json (AUDIENCE_FLOW_RESULTS_8NOV.md, 10 Nov 2026 update)",
            "creators": cp["creators"],
            "lag_days": [1, 3],  # scripts/run_platform_pairs.py: daily series, Instagram posts lagged 1-3 days
            "instagram_to_youtube": {"F": fwd["F"], "placebo_F": fwd["placebo_F_median"], "p": fwd["p_value"]},
            "youtube_to_instagram": {"F": rev["F"], "placebo_F": rev["placebo_F_median"], "p": rev["p_value"]},
        },
        "stronger_platform": {
            "source": "models/platform_pairs.json",
            "as_of": pp["as_of"],
            "matched_posts": pp["pairs"],
            "counts": {"Instagram": counts["Instagram"], "YouTube": counts["YouTube"], "balanced": counts["balanced"],
                       "not_enough": counts["not enough pairs"]},
            "creators": [{"creator_id": c["creator_id"], "name": c["name"], "stronger": c["stronger_platform"], "pairs": c["pairs"]}
                         for c in pp["creators"] if c.get("stronger_platform") in ("Instagram", "YouTube", "balanced")],
        },
        "promotion": {
            "source": "models/promotion_behaviour.json",
            "as_of": pr["as_of"],
            "sponsored_videos": pr["disclosure"]["sponsored_videos"],
            "share_disclosed": pr["disclosure"]["share_disclosed_overall"],
            "disclosure_creators": pr["disclosure"]["creators"],
            "buying_ratio": pr["response"]["median_ratio"],
            "buying_ratio_ci95": pr["response"]["ci95_ratio"],
            "placebo_ratio": pr["response"]["placebo_median_ratio"],
            "p": pr["response"]["p_one_sided_more_on_sponsored"],
            "response_creators": pr["response"]["creators"],
            "creators_more": pr["response"]["creators_more"],
            "creators_same": pr["response"]["creators_same"],
            "creators_fewer": pr["response"]["creators_fewer"],
        },
        "ad_load": {
            "source": "models/ad_fatigue.json",
            "as_of": fa["as_of"],
            "creators": views["creators"],
            "videos": fa["organic_videos"],
            "window_days": fa["window_days"],
            "views_slope": views["median_slope"],      # log views per extra sponsored video in the previous 30 days
            "views_ci95": views["ci95"],
            "views_p": views["p_one_sided_fatigue"],
            "rate_slope": rate["median_slope"],
            "rate_ci95": rate["ci95"],
        },
    }
    dest = ROOT / "frontend" / "public" / "brand_insights.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {dest}: cross-platform {out['cross_platform']['creators']} creators p {fwd['p_value']}; platforms {dict(out['stronger_platform']['counts'])}; "
          f"buying x{out['promotion']['buying_ratio']}; disclosed {out['promotion']['share_disclosed']:.1%}; views slope {views['median_slope']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
