"""Power analysis for the spillover test: how large an effect could our real data detect? Offline, no database. Writes models/power_analysis.json.

    python scripts/run_power_analysis.py [--obs models/gail_observations_29oct.json] [--out models/power_analysis.json]

INPUT: the real observations of the 29 Oct training run (fitness rule): 11 exposed (a direct collaborator was sponsored) and 295 control observations, each a measured
engagement lift (log((median after + 1) / (median before + 1)), 30-day windows) with its window and creator category. Saved by a one-line hook in a scratch copy of
Eesha's train_prod_model.py (stops after the observations are built).
METHOD. Only the effect is made up: a known extra lift DELTA is added to some observations, and the pipeline's own category-matched DiD (the estimator printed in the training
log) is run many times; "detected" = estimate / SE > 1.96. Two versions:
  (a) stand-ins: n random real CONTROL observations play "exposed" (real noise, real windows of the controls, but real exposed windows are sparser, so this is optimistic);
  (b) real structure: the 11 real exposed rows (their windows and categories) against the real controls, resampled with replacement; exposed rows are first shifted by minus the
      observed estimate so DELTA = 0 is a true null. n > 11 repeats the same 11 rows, so those lines are rough.
DELTA is in log-lift units: exp(DELTA) - 1 is the percent change in median engagement. The DELTA = 0 column is the false-alarm rate (target about 5%).
LIMITS: assumes the estimator's SE (independent observations); one platform at a time; says what could be SEEN, not whether an effect exists.
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
DELTAS = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5)


def matched_did(rows, stratum_of):
    """Same arithmetic as ml.time_indexed_treatment.matched_did (estimate and SE): exposed minus controls inside each (window, category) cell, weighted by exposed count."""
    by = defaultdict(list)
    for o in rows:
        by[(o.span, stratum_of(o))].append(o)

    def var(xs):
        if len(xs) < 2:
            return None
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)

    t_all = [o.value for g in by.values() for o in g if o.exposed]
    c_all = [o.value for g in by.values() for o in g if not o.exposed]
    var_t, var_cp = var(t_all) or 0.0, var(c_all) or 0.0
    parts = []
    for g in by.values():
        t = [o.value for o in g if o.exposed]
        c = [o.value for o in g if not o.exposed]
        if not t or not c:
            continue
        vc = var(c)
        parts.append((len(t), sum(t) / len(t) - sum(c) / len(c), len(c), vc if vc is not None else var_cp))
    n_t = sum(p[0] for p in parts)
    if not n_t:
        return None
    est = sum(p[0] * p[1] for p in parts) / n_t
    return est, (sum((p[0] / n_t) ** 2 * (var_t / p[0] + p[3] / p[2]) for p in parts)) ** 0.5


def mk(o, shift=0.0, exposed=False):
    return SimpleNamespace(span=tuple(o["span"]), value=o["value"] + shift, exposed=exposed, category=o["category"])


def min_detectable(table, n):
    ok = [d for d in DELTAS if d > 0 and table[(n, d)] >= 0.8]
    return ok[0] if ok else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--obs", default=str(ROOT / "models" / "gail_observations_29oct.json"))
    ap.add_argument("--out", default=str(ROOT / "models" / "power_analysis.json"))
    ap.add_argument("--reps", type=int, default=400)
    args = ap.parse_args()
    obs = json.loads(Path(args.obs).read_text(encoding="utf-8"))
    T, C = [o for o in obs if o["exposed"]], [o for o in obs if not o["exposed"]]
    cat = lambda o: o.category
    real = matched_did([mk(o, 0, True) for o in T] + [mk(o) for o in C], cat)
    print(f"real data: {len(T)} exposed, {len(C)} controls; category-matched DiD {real[0]:+.3f}, SE {real[1]:.3f}")
    rng = np.random.default_rng(29)
    rows = [mk(o) for o in C]
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "real_exposed": len(T), "real_controls": len(C), "real_estimate": round(real[0], 4), "real_se": round(real[1], 4),
           "deltas": DELTAS, "reps": args.reps, "limits": "assumes the estimator's SE; one platform; shows what could be seen, not whether an effect exists"}
    for name, sizes in (("stand_ins", (11, 18, 40, 80, 160)), ("real_structure", (11, 18, 40, 80))):
        tab = {}
        for n in sizes:
            for d in DELTAS:
                hit = tot = 0
                for _ in range(args.reps):
                    if name == "stand_ins":
                        pick = set(rng.choice(len(rows), n, replace=False).tolist())
                        sim = [SimpleNamespace(span=r.span, value=r.value + (d if i in pick else 0.0), exposed=i in pick, category=r.category) for i, r in enumerate(rows)]
                    else:
                        sim = [mk(T[i], d - real[0], True) for i in rng.integers(0, len(T), n)] + [mk(C[i]) for i in rng.integers(0, len(C), len(C))]
                    r = matched_did(sim, cat)
                    if r is not None:
                        tot += 1
                        hit += r[0] / r[1] > 1.96
                tab[(n, d)] = hit / max(tot, 1)
            print(f"{name:14s} n={n:4d} | " + "  ".join(f"d={d:.2f}: {100 * tab[(n, d)]:3.0f}%" for d in DELTAS), flush=True)
        out[name] = {"share_detected": {str(n): [round(tab[(n, d)], 3) for d in DELTAS] for n in sizes},
                     "min_detectable_80pct": {str(n): min_detectable(tab, n) for n in sizes}}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
