"""SIMULATION (not real data): how often does our estimator detect a spillover effect, by number of exposed creators and effect size?
Lifts are heavy-tailed like the real ones (Student-t, 3 df, scaled to sd 1.47, clipped at +-5); unexposed comparison group = 5 x exposed (as if collected).
Detection = 95% bootstrap interval of (mean exposed - mean unexposed) excludes 0. effect 0 row = false-alarm rate (should be near 5%)."""
import numpy as np
rng = np.random.default_rng(2026)
SD, REPS, BOOT = 1.47, 300, 200
def draw(n, shift):
    t = rng.standard_t(3, n) ; t = t / np.sqrt(3.0) * SD          # t3 has variance 3
    return np.clip(t + shift, -5, 5)
print("share of 300 simulated studies that detect the effect (95% interval excludes 0)")
print("exposed creators |  effect:  0.00 (false alarms)   0.25    0.50    0.75    1.00")
for n1 in (16, 19, 40, 81, 160, 320):
    n0 = 5 * n1; row = []
    for eff in (0.0, 0.25, 0.5, 0.75, 1.0):
        hits = 0
        for _ in range(REPS):
            a, b = draw(n1, eff), draw(n0, 0.0)
            ba = a[rng.integers(0, n1, (BOOT, n1))].mean(1); bb = b[rng.integers(0, n0, (BOOT, n0))].mean(1)
            lo, hi = np.percentile(ba - bb, [2.5, 97.5])
            hits += (lo > 0) or (hi < 0)
        row.append(hits / REPS)
    print(f"{n1:16d} |  " + "   ".join(f"{100*r:5.0f}%" for r in row), flush=True)
