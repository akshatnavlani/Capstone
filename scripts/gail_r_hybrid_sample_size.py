"""SIMULATED part 2: GAIL-R detection vs number of small creators (GAIL_R_HYBRID_SAMPLE_SIZE_PLAN_22NOV.md).

    python scripts/gail_r_hybrid_sample_size.py --inputs models/gail_r_inputs_final_22nov.pt

Real inputs of the final run; only the effect is planted and the number of creators per study is scaled (K x, drawn with
replacement, each draw a separate creator in the bootstrap). Writes models/gail_r_hybrid_sample_size_22nov.json.
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
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import gail_r_hybrid_sim as part1  # noqa: E402,F401  (installs the same pure-function caches)
from ml.gail_r import Observations, _gather, fit_gail_r, uniform_share  # noqa: E402

RUNS = [(2, 0.13), (2, 0.30), (4, 0.13), (4, 0.30), (8, 0.13), (8, 0.30), (8, 0.0)]


def rows_for(draws, rows_of):
    return torch.cat([rows_of[int(c)] for c in draws]), torch.cat([torch.full((len(rows_of[int(c)]),), i) for i, c in enumerate(draws)])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", required=True)
    ap.add_argument("--studies", type=int, default=10)
    ap.add_argument("--boot", type=int, default=50)
    ap.add_argument("--out", default=str(ROOT / "models" / "gail_r_hybrid_sample_size_22nov.json"))
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
    y0 = sub.y - exposed.float() * real["att"]
    creators = sub.node.unique()
    rows_of = {int(c): (sub.node == c).nonzero().squeeze(1) for c in creators}
    g = torch.Generator().manual_seed(2212)
    out = {"plan": "GAIL_R_HYBRID_SAMPLE_SIZE_PLAN_22NOV.md", "SIMULATED": True, "small_creators": len(creators),
           "small_exposed_rows": int(exposed.sum()), "studies": a.studies, "bootstrap_B": a.boot, "results": {}}
    t0 = time.time()
    for K, p in RUNS:
        d = math.log1p(p)
        y = y0 + exposed.float() * d
        hits, ests = 0, []
        for s in range(a.studies):
            draws = creators[torch.randint(0, len(creators), (K * len(creators),), generator=g)]
            idx, unit = rows_for(draws, rows_of)
            st = Observations(node=sub.node[idx], window=sub.window[idx], y=y[idx], pre=sub.pre[idx], own=None)
            fit = fit_gail_r(data, treatments, st, uniform=True, seed=s, **kw)
            # creator-level bootstrap over the drawn creators (each draw is one unit), as ml.gail_r.cluster_bootstrap
            gb = torch.Generator().manual_seed(1000 + s)
            unit_rows = [(unit == u).nonzero().squeeze(1) for u in range(len(draws))]
            atts = []
            for b in range(a.boot):
                pick = torch.randint(0, len(draws), (len(draws),), generator=gb)
                bi = torch.cat([unit_rows[int(u)] for u in pick])
                sb = Observations(node=st.node[bi], window=st.window[bi], y=st.y[bi], pre=st.pre[bi], own=None)
                atts.append(fit_gail_r(data, treatments, sb, uniform=True, seed=s + b + 1, **kw)["att"])
            t = torch.tensor([v for v in atts if not math.isnan(v)])
            lo = float(t.quantile(0.025))
            hits += int(lo > 0)
            ests.append(fit["att"])
        key = f"K={K}, +{int(round(p * 100))}%"
        out["results"][key] = {"creators_per_study": K * len(creators), "planted_log": d, "detected_share": hits / a.studies,
                               "detected": hits, "studies": a.studies, "mean_estimate": sum(ests) / len(ests)}
        out["as_of"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"{key}: {K * len(creators)} creators/study; detected in {hits}/{a.studies}; mean estimate "
              f"{sum(ests) / len(ests):+.3f} (truth {d:+.3f}); {time.time() - t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
