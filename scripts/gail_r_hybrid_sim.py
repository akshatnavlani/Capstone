"""SIMULATED (hybrid) validation of GAIL-R on the final run's REAL inputs (GAIL_R_HYBRID_SIMULATION_PLAN_22NOV.md).

    python scripts/gail_r_hybrid_sim.py --inputs models/gail_r_inputs_final_22nov.pt [--studies 40] [--boot 100]

Real graph, features, treatments and outcome rows; only the spillover effect is planted. Writes
models/gail_r_hybrid_sim_22nov.json (progress after every planted size). Nothing goes to the database or the app model.
"""
import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.gail_r import Observations, _gather, cluster_bootstrap, fit_gail_r, uniform_share  # noqa: E402

PLANTED = [0.0, 0.10, 0.20, 0.30, 0.40, 0.60]   # percent effects; planted on the log scale as log(1 + p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--studies", type=int, default=40)
    ap.add_argument("--boot", type=int, default=100)
    ap.add_argument("--out", default=str(ROOT / "models" / "gail_r_hybrid_sim_22nov.json"))
    a = ap.parse_args()
    z = torch.load(a.inputs, weights_only=False)
    data, treatments, obs = z["data"], z["treatments"], z["obs"]
    kw = {"placebo_weight": z["placebo_weight"], "window_fe": z["window_fe"]}
    small = set(z["small_nodes"])
    mask = torch.tensor([int(n) in small for n in obs.node.tolist()])
    sub = Observations(node=obs.node[mask], window=obs.window[mask], y=obs.y[mask], pre=obs.pre[mask], own=None)
    n = data["creator"].x.size(0)
    U0 = _gather([uniform_share(data["creator", "collaborates_with", "creator"].edge_index, t, n) for t in treatments], sub)
    exposed = U0 > 0
    real = fit_gail_r(data, treatments, sub, uniform=True, seed=z["seed"], **kw)
    print(f"small-creator rows {len(sub.y)}, exposed {int(exposed.sum())}; real estimate (uniform) {real['att']:+.4f}", flush=True)
    y0 = sub.y - exposed.float() * real["att"]           # remove the real estimate: planted 0 = true null
    creators = sub.node.unique()
    rows_of = {int(c): (sub.node == c).nonzero().squeeze(1) for c in creators}
    g = torch.Generator().manual_seed(2211)
    out = {"plan": "GAIL_R_HYBRID_SIMULATION_PLAN_22NOV.md", "SIMULATED": True, "inputs": a.inputs,
           "small_rows": len(sub.y), "small_exposed_rows": int(exposed.sum()), "real_att_uniform": real["att"],
           "studies_per_size_target": a.studies, "bootstrap_B": a.boot, "results": {}}
    t0 = time.time()
    for p in PLANTED:
        d = math.log1p(p)
        y = y0 + exposed.float() * d
        hits, ests, done = 0, [], 0
        for s in range(a.studies):
            pick = creators[torch.randint(0, len(creators), (len(creators),), generator=g)]
            idx = torch.cat([rows_of[int(c)] for c in pick])
            st = Observations(node=sub.node[idx], window=sub.window[idx], y=y[idx], pre=sub.pre[idx], own=None)
            fit = fit_gail_r(data, treatments, st, uniform=True, seed=s, **kw)
            ci = cluster_bootstrap(data, treatments, st, B=a.boot, seed=1000 + s, **kw)["att"]
            hits += int(ci["lo"] > 0)
            ests.append(fit["att"])
            done += 1
        mean_est = sum(ests) / len(ests)
        out["results"][f"+{int(p*100)}%"] = {"planted_log": d, "studies": done, "detected_share": hits / done,
                                            "mean_estimate": mean_est, "bias": mean_est - d}
        out["as_of"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"planted +{int(p*100)}%: detected in {hits}/{done} studies; mean estimate {mean_est:+.3f} "
              f"(truth {d:+.3f}); {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
