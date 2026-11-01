"""Pull the headline numbers of a GAIL training log into models/gail_training_summary_31oct.json (so the paper pack reads a file, not a scratch log). Offline.

    python scripts/extract_training_summary.py LOG [--out models/gail_training_summary_31oct.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--out", default=str(ROOT / "models" / "gail_training_summary_31oct.json"))
    ap.add_argument("--note", default="run of 31 Oct 2026 (run 7), BEFORE the standing-affiliate-code label fix of 1 Nov; the fix leaves all 60 exposed observations exposed")
    a = ap.parse_args()
    t = Path(a.log).read_text(encoding="utf-8", errors="replace")
    g = lambda pat, cast=float, grp=1: cast(re.search(pat, t).group(grp)) if re.search(pat, t) else None  # noqa: E731
    epochs = [(int(m.group(1)), float(m.group(3)), float(m.group(4))) for m in re.finditer(r"epoch (\d+)/(\d+): total=([\d.]+) pred=([\d.]+)", t)]
    out = {
        "source_log": Path(a.log).name,
        "windows": re.search(r"Windows: baseline (\d+)d, outcome (\d+)d", t).groups() if re.search(r"Windows: baseline (\d+)d", t) else None,
        "target": "log_lift: log((after+1)/(before+1)) of a neighbour's engagement around each sponsorship window, median-based, clipped to +/-5",
        "training": {"epochs": epochs[-1][0] if epochs else None, "loss_by_epoch": [{"epoch": e, "total": tot, "prediction": pr} for e, tot, pr in epochs],
                     "observations": g(r"Prod training result \(N=(\d+) observations", int), "mse_trained": g(r"MSE trained: ([\d.]+)"), "mse_baseline_always_zero": g(r"baseline \(always 0\): ([\d.]+)"),
                     "improvement_percent": g(r"improvement: ([\d.]+)%"), "mse_controls": g(r"Control observations: \d+, MSE ([\d.]+)"),
                     "learned_relation_shares": {m.group(1): float(m.group(2)) for m in re.finditer(r"^\s+(co_occurs_with|collaborates_with)\s+([\d.]+)\s*$", t, re.M)},
                     "placebo_penalty_on_trained_model": g(r"Placebo penalty on trained model[^:]*: ([\d.]+)")},
        "exposed_observations": g(r"P3: (\d+) exposed", int), "control_observations": g(r"P3: \d+ exposed \+ (\d+) control", int),
        "matched_did": {"estimate": g(r"Matched DiD \(no model\): ([+-]?[\d.]+)"), "se": g(r"Matched DiD \(no model\): [+-]?[\d.]+\s+SE ([\d.]+)"), "exposed": g(r"over (\d+) exposed vs", int), "controls": g(r"exposed vs (\d+) controls in", int)},
        "category_matched_did": {"estimate": g(r"Category-matched DiD:\s+([+-]?[\d.]+)"), "se": g(r"Category-matched DiD:\s+[+-]?[\d.]+\s+SE ([\d.]+)")},
        "placebo_pre_trend_did": {"estimate": g(r"Placebo \(pre-trend\) DiD: ([+-]?[\d.]+)"), "se": g(r"Placebo \(pre-trend\) DiD: [+-]?[\d.]+\s+SE ([\d.]+)"), "note": "should be about 0; a clear non-zero value means a plain DiD is confounded by pre-existing trends"},
        "gail_r": {"effect_on_exposed": g(r"effect on the \d+ observations with a sponsored collaborator:\s+([+-]?[\d.]+)"),
                   "ci95": [g(r"collaborator:\s+[+-]?[\d.]+\s+95% CI \[([+-]?[\d.]+),"), g(r"collaborator:\s+[+-]?[\d.]+\s+95% CI \[[+-]?[\d.]+, ([+-]?[\d.]+)\]")],
                   "bootstrap": "creator-level, B=200", "creators": g(r"(\d+) observations from (\d+) creators", int, 2)},
        "note": a.note,
    }
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("training", "matched_did", "category_matched_did", "placebo_pre_trend_did", "gail_r")}, indent=1)[:1800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
