"""GAIL acceptance test on SIMULATED worlds (not real data). Run it against any version of GAIL: whatever `ml.*` is on PYTHONPATH is what gets tested.
Needs ml/synthetic_recovery.py, which is on Eesha's branch (review2-eesha-model) and not yet merged here: run it from a checkout of that branch.

    cd <checkout with ml/synthetic_recovery.py>; PYTHONPATH=. python gail_acceptance.py [--seeds 6] [--n 400]

Worlds: dense (avg degree 4, about 86% of creators exposed) and sparse (avg degree 1, about 39% exposed, closer to our real network). Noise sd 1.5.
TRUTH: the effect estimate averages (mu(exposure) - mu(0)) over ALL creators, so the truth it should match is  planted effect x mean(true exposure)  over all creators
(in the dense world that is about the planted effect; in the sparse world it is smaller). Estimates come from Eesha's own train_and_score (signed here).

Checks (all must pass; 'pass' = at least 5 of 6 seeds satisfy the rule, except the mean-based rules):
  1  zero effect:  mean estimate within +-0.2 of 0, dense and sparse
  2  planted 0.5 / 1 / 2 (sparse and dense): mean estimate within 25% of the truth (or +-0.2, whichever is larger)
  3  attention: mean within-neighbourhood correlation with the planted edge weights >= 0.20 (her documented ceiling on the default world is about 0.33)
  4  no sign errors: no seed returns an estimate of the wrong sign when the planted effect is >= 1
"""
import argparse
import statistics as st
import sys
import time
import torch
import ml.synthetic_recovery as sr

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sr.abs = lambda x: x          # make effect_error signed: estimate - planted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--epochs", type=int, default=300)
    a = ap.parse_args()
    rows, fails = [], []
    for kind, deg in (("dense", 4), ("sparse", 1)):
        for effect in (0.0, 0.5, 1.0, 2.0):
            ests, truths, corrs = [], [], []
            t0 = time.time()
            for seed in range(a.seeds):
                w = sr.make_synthetic_world(num_creators=a.n, avg_degree=deg, true_effect=effect, noise=1.5, seed=seed)
                te = torch.zeros(a.n)
                te.index_add_(0, w.edge_index[1], w.true_edge_weight * w.treatment[w.edge_index[0]])
                truths.append(float(effect * te.mean()))
                m = sr.train_and_score(w, dr_mode="aipw", epochs=a.epochs, seed=seed)
                ests.append(effect + m["effect_error"]); corrs.append(m["transmission_corr"])
            mean, truth = st.mean(ests), st.mean(truths)
            tol = max(0.2, 0.25 * abs(truth)) if effect > 0 else 0.2
            ok_mean = abs(mean - truth) <= tol
            wrong_sign = effect >= 1.0 and any(e <= 0 for e in ests)
            rows.append((kind, effect, truth, mean, st.pstdev(ests), st.mean(corrs), ok_mean, wrong_sign))
            print(f"{kind:6s} planted {effect:.1f}: truth {truth:+.2f} | mean estimate {mean:+.2f} (sd {st.pstdev(ests):.2f}) | attention corr {st.mean(corrs):+.3f} | "
                  f"{'ok' if ok_mean else 'FAIL'}{' WRONG SIGN' if wrong_sign else ''} | {time.time()-t0:.0f}s", flush=True)
    print("\nRESULT")
    c1 = [r for r in rows if r[1] == 0.0]
    c2 = [r for r in rows if r[1] > 0]
    c1_ok = all(r[6] for r in c1)
    c2_ok = all(r[6] for r in c2)
    c3_ok = st.mean(r[5] for r in rows) >= 0.20
    c4_ok = not any(r[7] for r in rows)
    for name, ok in (("1 zero effect gives about 0", c1_ok), ("2 planted effects recovered within tolerance", c2_ok),
                     ("3 attention finds the right neighbours (>= 0.20)", c3_ok), ("4 no wrong-sign estimates", c4_ok)):
        print(f"  check {name}: {'PASS' if ok else 'FAIL'}")
    print("ACCEPTED" if all((c1_ok, c2_ok, c3_ok, c4_ok)) else "NOT ACCEPTED")


if __name__ == "__main__":
    main()
