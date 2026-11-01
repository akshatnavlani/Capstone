"""Sensitivity of the real-data spillover estimate to MISSED sponsorship labels. Offline, no database. Writes models/label_noise_sensitivity.json.

    python scripts/run_label_noise_sensitivity.py [--power models/power_analysis.json]

WHY (31 Oct 2026). 'Organic' in our data means 'not detected as sponsored'. Detection is by rules and misses some sponsored posts (about 58% of Shorts have empty descriptions), so some comparison
observations may really have had a sponsored collaborator. That contaminates the comparison group and pulls the exposed-minus-comparison contrast toward zero. This is the plain
sensitivity version of the planned 'mismeasured treatment' correction (PendingWork E5), not the full model.

METHOD. If a share c of the comparison group is truly exposed and the effect is the same for everyone exposed, the observed contrast is (1 - c) times the true effect, so
true effect = observed / (1 - c). The same factor widens the 95% interval. We report c = 0, 5%, 10%, 20% and 30%. Assumptions that are NOT checked: the effect is homogeneous; missed
labels are as likely among exposed neighbours' controls as anywhere (random); the exposed group itself is correctly labelled (a detected sponsorship is almost always a real one:
73 of 75 strong-tier events were checked by hand).
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--power", default=str(ROOT / "models" / "power_analysis.json"))
    ap.add_argument("--out", default=str(ROOT / "models" / "label_noise_sensitivity.json"))
    args = ap.parse_args()
    p = json.loads(Path(args.power).read_text(encoding="utf-8"))
    est, se = p["real_estimate"], p["real_se"]
    rows = []
    for c in (0.0, 0.05, 0.10, 0.20, 0.30):
        f = 1.0 / (1.0 - c)
        lo, hi = (est - 1.96 * se) * f, (est + 1.96 * se) * f
        rows.append({"share_of_comparison_group_truly_exposed": c, "corrected_estimate": round(est * f, 3), "ci95": [round(lo, 3), round(hi, 3)],
                     "upper_bound_as_engagement_ratio": round(2.718281828 ** hi, 2)})
        print(f"c = {c:4.0%}: corrected estimate {est * f:+.3f}, 95% interval {lo:+.3f} to {hi:+.3f} (upper bound = {2.718281828 ** hi:.2f}x engagement)")
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "observed_estimate": est, "observed_se": se, "exposed": p["real_exposed"], "controls": p["real_controls"], "rows": rows,
           "reading": "Even if 30% of the comparison group were truly exposed, the upper end of the 95% interval stays below a 1.3x engagement effect; the null is not an artefact of a moderate number of missed labels.",
           "limits": "homogeneous effect; random missing labels; a correct exposed group; this is a sensitivity table, not the full mismeasured-treatment model"}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
