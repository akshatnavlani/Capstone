"""Cross-promotion mechanism test for the detected cross-platform spillover. Plan: CROSS_PROMOTION_MECHANISM_PLAN_10NOV.md
(fixed before any number). READ ONLY on the database; writes models/cross_promotion_mechanism_10nov.json.

    python scripts/cross_promotion_mechanism_test.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from run_platform_pairs import build_series, granger, granger_f, load  # noqa: E402

IG_RE = re.compile(r"youtube|you tube|\byt\b", re.I)
YT_RE = re.compile(r"instagram|\binsta\b", re.I)
PERMS, MIN_GROUP = 2000, 15


def share(items, pat):
    return sum(bool(pat.search(i["text"] or "")) for i in items) / len(items) if items else 0.0


def split(S, shares):
    vals = np.array([shares[c] for c in S])
    med = float(np.median(vals))
    hi = {c: S[c] for c in S if shares[c] > med}
    lo = {c: S[c] for c in S if shares[c] <= med}
    return hi, lo, med


def compare(S, shares, cause, label):
    hi, lo, med = split(S, shares)
    out = {"label": label, "median_share": round(med, 4), "promoters": len(hi), "others": len(lo)}
    if len(hi) < MIN_GROUP or len(lo) < MIN_GROUP:
        out["verdict"] = f"fewer than {MIN_GROUP} creators in a group: printed, not a result"
        return out
    real = granger_f(hi, cause=cause) - granger_f(lo, cause=cause)
    rng = np.random.default_rng(0)
    keys = list(S)
    null = []
    for _ in range(PERMS):
        perm = rng.permutation(keys)
        h = {c: S[c] for c in perm[:len(hi)]}
        l = {c: S[c] for c in perm[len(hi):]}
        null.append(granger_f(h, cause=cause) - granger_f(l, cause=cause))
    p_diff = (1 + sum(d >= real for d in null)) / (1 + PERMS)
    name = "Instagram posts -> YouTube comments" if cause == 1 else "YouTube comments -> Instagram posts"
    own = {"promoters": granger(hi, 500, 5)[name], "others": granger(lo, 500, 5)[name]}
    out.update({"direction": name, "F_difference": round(real, 3), "p_difference": round(p_diff, 4), "own_granger": own,
                "verdict": "MECHANISM SUPPORTED" if p_diff < 0.05 and own["promoters"]["p_value"] < 0.05 else "NOT supported"})
    return out


def main() -> int:
    names, yt, ig, com, igd = load()
    S = build_series(com, igd, list(igd), True)   # comments on videos older than 72 h, as in the detected test
    ig_share = {c: share(ig.get(c, []), IG_RE) for c in S}
    yt_share = {c: share(yt.get(c, []), YT_RE) for c in S}
    res = {"plan": "CROSS_PROMOTION_MECHANISM_PLAN_10NOV.md", "creators": len(S),
           "update_detected_test_today": granger(S, 500, 5),
           "primary": compare(S, ig_share, 1, "Instagram captions mentioning YouTube (median split)"),
           "secondary": compare(S, yt_share, 0, "YouTube texts mentioning Instagram (median split)")}
    out = ROOT / "models" / "cross_promotion_mechanism_10nov.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
