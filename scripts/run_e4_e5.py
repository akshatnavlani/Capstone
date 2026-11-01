"""E4 and E5 on the semi-synthetic benchmark (truth known) and E5 on the real run-7 inputs. Offline, no database. Writes models/e4_e5_results.json.

    python scripts/run_e4_e5.py INPUTS.pt [--reps 6] [--checkpoint models/gail_checkpoint.pt] [--out models/e4_e5_results.json]

Needs ml/gail_r.py, ml/semi_synthetic.py and ml/placebo.py (Eesha's branch, merge-eesha-ml) next to ml/gail_r_ext.py.

E4 (SIMULATED, real graph and features, planted effect): does supervising attention with the causal (orthogonalised) loss recover the per-creator effect better than supervising it with plain
outcome error? Compared at two shrinkage strengths, against uniform neighbour weights, in a clean world and one with a pre-existing trend. Error = root mean squared error of the per-creator
effect (PEHE) and absolute error of the mean effect.
E5 (SIMULATED): labels are dropped at a known recall; the naive estimate and the MC-SIMEX estimate are compared with the planted truth.
E5 on the REAL data: the real estimate corrected for a range of assumed recalls. The recall is not known; the range is a sensitivity analysis, not a measurement.
"""
import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ml.semi_synthetic as sm  # noqa: E402
from ml.gail_r import Observations, fit_gail_r  # noqa: E402
from ml.gail_r_ext import drop_labels, fit_gail_r_supervised, simex_gail_r  # noqa: E402


def _obs(world):
    n = len(world.y)
    return Observations(torch.arange(n), torch.zeros(n, dtype=torch.long), world.y, world.y_pre)


def pehe(tau, truth):
    return float((tau - truth).pow(2).mean().sqrt())


def mean_sd(v):
    return {"mean": round(statistics.mean(v), 4), "sd": round(statistics.pstdev(v), 4)} if v else None


def e4(graph, reps):
    out = {}
    for scen in ("clean", "pretrend"):
        for shrink in (100.0, 10.0):
            rows = {"causal": [], "plain": [], "uniform": []}
            for r in range(reps):
                world = sm.make_world(graph, scen, seed=r)
                obs = _obs(world)
                for mode in ("causal", "plain"):
                    f = fit_gail_r_supervised(world.data, [world.treatment], obs, supervision=mode, placebo_weight=0.0, shrink=shrink, seed=r)
                    rows[mode].append((pehe(f["tau"], world.true_tau), abs(f["ate"] - world.true_ate)))
                if shrink == 100.0:
                    f = fit_gail_r(world.data, [world.treatment], obs, uniform=True, placebo_weight=0.0, seed=r)
                    rows["uniform"].append((pehe(f["tau"], world.true_tau), abs(f["ate"] - world.true_ate)))
            for mode, vals in rows.items():
                if mode == "uniform" and shrink != 100.0:
                    continue
                key = f"{scen}, {'uniform weights' if mode == 'uniform' else f'{mode} supervision, shrink {int(shrink)}'}"
                out[key] = {"pehe": mean_sd([v[0] for v in vals]), "abs_error_of_mean_effect": mean_sd([v[1] for v in vals]), "reps": len(vals)}
                print(key, out[key], flush=True)
    return out


def e5_sim(graph, reps, recalls=(0.9, 0.7, 0.5)):
    out = {}
    for rec in recalls:
        naive, simex, truth = [], [], []
        for r in range(reps):
            world = sm.make_world(graph, "clean", seed=r)
            seen = drop_labels([world.treatment], rec, torch.Generator().manual_seed(100 + r))
            res = simex_gail_r(world.data, seen, _obs(world), recall=rec, draws=6, placebo_weight=0.0, seed=r)
            naive.append(res["naive"]["ate"]), simex.append(res["corrected"]["ate"]), truth.append(world.true_ate)
        t = statistics.mean(truth)
        out[str(rec)] = {"true_ate": round(t, 4), "naive_ate": mean_sd(naive), "simex_ate": mean_sd(simex),
                         "naive_abs_error": round(statistics.mean(abs(a - b) for a, b in zip(naive, truth)), 4),
                         "simex_abs_error": round(statistics.mean(abs(a - b) for a, b in zip(simex, truth)), 4), "reps": reps}
        print("E5 simulated recall", rec, out[str(rec)], flush=True)
    return out


def e5_real(inputs, recalls=(1.0, 0.9, 0.8, 0.7, 0.6)):
    blob = torch.load(inputs, weights_only=False, map_location="cpu")
    obs = Observations(node=blob["node"], window=blob["window"], y=blob["y"], pre=blob["pre"])
    out = {}
    for rec in recalls:
        res = simex_gail_r(blob["data"], blob["treatments"], obs, recall=rec, draws=8, placebo_weight=30.0)
        out[str(rec)] = {"naive": {k: round(v, 4) for k, v in res["naive"].items()}, "corrected": {k: round(v, 4) for k, v in res["corrected"].items()}}
        print("E5 real, assumed recall", rec, out[str(rec)], flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs")
    ap.add_argument("--reps", type=int, default=6)
    ap.add_argument("--checkpoint", default=str(ROOT / "models" / "gail_checkpoint.pt"))
    ap.add_argument("--out", default=str(ROOT / "models" / "e4_e5_results.json"))
    args = ap.parse_args()
    graph = sm.load_graph(Path(args.checkpoint))
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "planted_effect": sm.EFFECT, "noise": sm.NOISE, "reps": args.reps,
           "e4_simulated": e4(graph, args.reps), "e5_simulated": e5_sim(graph, args.reps), "e5_real": e5_real(args.inputs),
           "limits": "E4 and E5-simulated use real graph and features with SIMULATED treatment and outcomes; E5-real assumes a recall (unknown) and a homogeneous effect; nothing here changes a score"}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
