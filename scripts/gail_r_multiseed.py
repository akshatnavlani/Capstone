"""GAIL-R over many seeds, offline, CPU or GPU: how stable is the spillover estimate? Writes models/gail_r_multiseed.json.

    python scripts/gail_r_multiseed.py INPUTS.pt [--seeds 10] [--boot 200] [--device cpu|cuda] [--out models/gail_r_multiseed.json]

INPUTS.pt: the real graph, treatment windows and observations of a training run (saved by a one-line hook in a scratch copy of Eesha's train_prod_model.py, GAIL_DUMP_R). No database
and no secrets are needed, so this file can go to a notebook or a GPU machine as it is, together with the repo's ml/ folder.

For each placebo-penalty weight (0 and 30) and each seed, fit GAIL-R with LEARNED attention (ml/gail_r.py fit_gail_r) and record the effect on observations whose collaborator was sponsored
(ATT) and the two relation slopes. Then a creator-level bootstrap (uniform attention, the same fit the training script reports). One seed is an anecdote; the spread over seeds shows how much of
the estimate is the model's own randomness. The model is small (about 20,000 weights on 390 creators), so a GPU mainly speeds up the bootstrap; the CPU path is the one tested here.
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

from ml.gail_r import RELATIONS, Observations, cluster_bootstrap, fit_gail_r  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default=str(ROOT / "models" / "gail_r_multiseed.json"))
    args = ap.parse_args()
    if args.device != "cpu":
        torch.set_default_device(args.device)
    blob = torch.load(args.inputs, weights_only=False, map_location="cpu")
    dev = torch.device(args.device)
    data = blob["data"].to(dev)
    treatments = [t.to(dev) for t in blob["treatments"]]
    obs = Observations(node=blob["node"].to(dev), window=blob["window"].to(dev), y=blob["y"].to(dev), pre=blob["pre"].to(dev))
    print(f"device {dev}; {len(obs.y)} observations from {len(obs.node.unique())} creators, {len(treatments)} windows")

    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "device": str(dev), "observations": len(obs.y), "creators": len(obs.node.unique()), "windows": len(treatments), "seeds": args.seeds, "runs": {}}
    for label, w_pl in (("without placebo penalty", 0.0), ("with placebo penalty (30)", 30.0)):
        fits = [fit_gail_r(data, treatments, obs, placebo_weight=w_pl, seed=s) for s in range(args.seeds)]
        att = [f["att"] for f in fits]
        ci = cluster_bootstrap(data, treatments, obs, B=args.boot, seed=0, placebo_weight=w_pl)
        row = {"n_exposed": fits[0]["n_exposed"], "att_by_seed": [round(a, 4) for a in att], "att_mean": round(statistics.mean(att), 4), "att_sd_over_seeds": round(statistics.pstdev(att), 4),
               "bootstrap_ci95": [round(ci["att"]["lo"], 4), round(ci["att"]["hi"], 4)], "bootstrap_B": args.boot,
               "slopes_mean": {r: round(statistics.mean(f["slopes"][r] for f in fits), 4) for r in RELATIONS}, "slopes_sd_over_seeds": {r: round(statistics.pstdev(f["slopes"][r] for f in fits), 4) for r in RELATIONS}}
        out["runs"][label] = row
        print(f"{label}: ATT {row['att_mean']:+.3f} (sd over {args.seeds} seeds {row['att_sd_over_seeds']:.3f}), bootstrap 95% [{row['bootstrap_ci95'][0]:+.3f}, {row['bootstrap_ci95'][1]:+.3f}], {row['n_exposed']} exposed", flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
