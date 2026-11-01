"""SIMULATION: does the fusion design recover a planted creator ordering, and what does a spillover branch that carries no information cost? Offline, numpy only; writes models/fusion_simulation.json.

    python scripts/simulate_fusion.py [--reps 300] [--creators 400]

WHAT THIS IS. A controlled test of the fusion LOGIC under stated assumptions. A latent true value v is planted for every creator (what a brand would really get); the three branches observe it with noise:
sentiment and creator-feature with assumed informativeness, spillover with the informativeness of each scenario. Four scoring rules are compared on the same creators: the weights before 30 Oct (0.4/0.3/0.3 with a neutral
0.5 where a branch knows nothing), the 30 Oct priors with the same neutral fill (0.2/0.4/0.4), the current rule (0.2/0.4/0.4 with the branch that knows nothing left out and the rest rescaled), and the proposed rule
(spillover taken out of the score: 0/0.5/0.5, uninformed branches left out). Scored by Spearman correlation with the planted truth and by how many of the true top 20 appear in the top 20.

WHAT IT IS NOT. It does not say how well the score predicts real brand outcomes (no such data exists). The informativeness of sentiment and feature is ASSUMED and swept, not measured. The spillover scenarios cover the real
finding (no detectable effect) and two cases where spillover would carry information, so the result shows when keeping the branch would help and when it would not.
Coverage in the base case follows the app: about 5% of creators have a real spillover score, and 70% have scored comments and real content evidence.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RULES = {"before 30 Oct: 0.4/0.3/0.3, neutral fill": ((0.4, 0.3, 0.3), False), "30 Oct priors: 0.2/0.4/0.4, neutral fill": ((0.2, 0.4, 0.4), False),
         "current: 0.2/0.4/0.4, uninformed branch left out": ((0.2, 0.4, 0.4), True), "proposed: spillover out of the score, 0/0.5/0.5, uninformed left out": ((0.0, 0.5, 0.5), True)}


def observe(v, rho, rng, scale=0.15):
    """A branch score in [0, 1] whose correlation with the planted value is about rho."""
    z = rho * v + np.sqrt(max(1 - rho ** 2, 0)) * rng.standard_normal(len(v))
    return np.clip(0.5 + scale * z, 0, 1)


def score(branches, known, weights, leave_out):
    s, k = np.stack(branches), np.stack(known)
    w = np.array(weights)[:, None] * np.ones_like(s)
    filled = np.where(k, s, 0.5)                       # neutral fill where a branch knows nothing
    if not leave_out:
        return (w * filled).sum(0)
    w = w * k                                          # leave the branch out and rescale to the same total
    tot = w.sum(0)
    base = np.array(weights).sum()
    scaled = np.where(tot > 0, w * (base / np.where(tot > 0, tot, 1)), np.array(weights)[:, None] * np.ones_like(s))
    return (scaled * np.where(tot > 0, s, 0.5)).sum(0)


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)).astype(float), np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def run(n, reps, rho_s, rho_f, rho_p, p_link, p_sent, p_feat, seed):
    rng = np.random.default_rng(seed)
    out = {k: {"spearman": [], "top20": []} for k in RULES}
    for _ in range(reps):
        v = rng.standard_normal(n)
        sp, se, fe = observe(v, rho_p, rng), observe(v, rho_s, rng), observe(v, rho_f, rng)
        known = [rng.random(n) < p_link, rng.random(n) < p_sent, rng.random(n) < p_feat]
        true_top = set(np.argsort(-v)[:20])
        for name, (w, leave) in RULES.items():
            sc = score([sp, se, fe], known, w, leave)
            out[name]["spearman"].append(spearman(sc, v))
            out[name]["top20"].append(len(true_top & set(np.argsort(-sc)[:20])))
    return {k: {"spearman": round(float(np.mean(v["spearman"])), 3), "top20_of_20": round(float(np.mean(v["top20"])), 2)} for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=300)
    ap.add_argument("--creators", type=int, default=400)
    ap.add_argument("--out", default=str(ROOT / "models" / "fusion_simulation.json"))
    a = ap.parse_args()
    base = dict(rho_s=0.25, rho_f=0.42, p_sent=0.7, p_feat=0.7)       # 0.42 is the measured rank correlation of the feature score with relevance (S2); sentiment's value is assumed
    scenarios = {
        "spillover carries no information (what the real data shows), 5% of creators linked": dict(rho_p=0.0, p_link=0.05),
        "spillover carries no information, 30% of creators linked": dict(rho_p=0.0, p_link=0.30),
        "spillover weakly informative (0.2), 30% linked": dict(rho_p=0.2, p_link=0.30),
        "spillover informative (0.5), 30% linked": dict(rho_p=0.5, p_link=0.30),
    }
    res = {}
    for i, (name, kw) in enumerate(scenarios.items()):
        res[name] = run(a.creators, a.reps, seed=100 + i, **base, **kw)
        print(f"\n{name}")
        for rule, m in res[name].items():
            print(f"   {rule:70s} Spearman {m['spearman']:.3f} | true top 20 recovered {m['top20_of_20']:.1f}/20")
    # sensitivity: how informative sentiment would have to be before the conclusion changes
    sens = {}
    for rs in (0.0, 0.25, 0.5):
        sens[str(rs)] = run(a.creators, a.reps, seed=500, rho_s=rs, rho_f=0.42, rho_p=0.0, p_link=0.05, p_sent=0.7, p_feat=0.7)
    Path(a.out).write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "simulated": True, "creators": a.creators, "reps": a.reps,
                                       "assumptions": {"sentiment_informativeness": base["rho_s"], "feature_informativeness": base["rho_f"], "scored_sentiment_share": base["p_sent"], "real_feature_share": base["p_feat"]},
                                       "scenarios": res, "sensitivity_to_sentiment_informativeness_no_spillover_signal": sens,
                                       "limits": "tests the fusion logic under assumed informativeness; says nothing about real brand outcomes, which no data covers"}, indent=1), encoding="utf-8")
    print("\nsaved", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
