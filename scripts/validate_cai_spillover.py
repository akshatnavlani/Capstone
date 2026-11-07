"""Does GAIL-R recover a spillover that is known to exist?

Runs GAIL-R on the Cai, de Janvry & Sadoulet (2015) insurance experiment, where
friends' randomised invitations to an intensive information session are
published to raise take-up by 0.291 per 0-to-100% of friends (SE 0.082).

Data is NOT in the repo. Download "Replication Data for: Social Networks and
the Decision to Insure" from Harvard Dataverse (doi:10.7910/DVN/CXDJM0), unzip
it anywhere, and point --data at that folder (or set GAIL_CAI_DIR).

    python scripts/validate_cai_spillover.py --data data/external/cai2015

Checks, in order:
  1. Our graph rebuilds the paper's regression (should print ~0.29).
  2. GAIL-R, learned attention and uniform, with village window effects.
  3. Interval: bootstrap over the paper's clusters (natural villages).
  4. Pure-noise fake assignments: GAIL-R should average ~0.
  5. Randomisation inference: the experiment's within-village draw rerun on
     fake assignments; the real estimate should sit in their upper tail.
Writes models/cai_validation.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.cai_benchmark import PUBLISHED, load, permute_treatment, random_treatment, replicate_paper  # noqa: E402
from ml.gail_r import Observations, fit_gail_r  # noqa: E402


def cluster_bootstrap_by(cd, treatments, clusters, B, seed, **kw):
    g = torch.Generator().manual_seed(seed)
    uniq = clusters.unique()
    rows_of = {int(c): (clusters == c).nonzero().squeeze(1) for c in uniq}
    vals = []
    for b in range(B):
        pick = uniq[torch.randint(0, len(uniq), (len(uniq),), generator=g)]
        idx = torch.cat([rows_of[int(c)] for c in pick])
        vals.append(fit_gail_r(cd.data, treatments, cd.obs.subset(idx), seed=seed + b + 1,
                               uniform=True, **kw)["slopes"]["collaborates_with"])
    t = torch.tensor(vals)
    return {"lo": float(t.quantile(0.025)), "hi": float(t.quantile(0.975)), "se": float(t.std()), "B": B}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.environ.get("GAIL_CAI_DIR", "data/external/cai2015"))
    ap.add_argument("--boot", type=int, default=200)
    ap.add_argument("--perms", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    cd = load(args.data)
    W = int(cd.obs.window.max()) + 1
    same = lambda t: [t] * W  # noqa: E731  one assignment, every village window sees it
    out = {"published": PUBLISHED, "n_obs": len(cd.obs.y),
           "n_nodes": int(cd.data["creator"].x.size(0)),
           "n_edges": int(cd.data["creator", "collaborates_with", "creator"].edge_index.size(1))}
    print(f"Cai et al. (2015): {out['n_obs']} second-round households, {out['n_nodes']} nodes, "
          f"{out['n_edges']} friendship links, {W} villages")
    print(f"Published effect (0->100% of friends treated): {PUBLISHED['slope']:+.3f} "
          f"(SE {PUBLISHED['se']:.3f}, 95% CI [{PUBLISHED['lo']:+.3f}, {PUBLISHED['hi']:+.3f}])\n")

    rep = replicate_paper(cd)
    out["replication_ols"] = rep
    print(f"1. Paper's regression rebuilt from our graph: {rep['slope']:+.3f} (SE {rep['se']:.3f}, n={rep['n']})")

    print("2. GAIL-R (placebo penalty inactive: this design has no pre-period outcome)")
    fits = {}
    for name, kw in (("learned attention, village effects", {}),
                     ("uniform attention, village effects", {"uniform": True}),
                     ("uniform attention, no village effects", {"uniform": True, "window_fe": False})):
        t0 = time.time()
        f = fit_gail_r(cd.data, same(cd.treatment), cd.obs, placebo_weight=0.0, seed=args.seed, **kw)
        s = f["slopes"]["collaborates_with"]
        fits[name] = {"slope": s, "att": f["att"], "n_exposed": f["n_exposed"]}
        print(f"   {name:40s} slope {s:+.3f}   ({time.time() - t0:.0f}s)")
    out["gail_r"] = fits

    ci = cluster_bootstrap_by(cd, same(cd.treatment), cd.address, args.boot, args.seed, placebo_weight=0.0)
    out["gail_r_ci"] = ci
    main_s = fits["learned attention, village effects"]["slope"]
    print(f"3. 95% CI, bootstrap over {len(cd.address.unique())} natural villages (B={args.boot}): "
          f"[{ci['lo']:+.3f}, {ci['hi']:+.3f}]  SE {ci['se']:.3f}")
    inside = ci["lo"] <= PUBLISHED["slope"] <= ci["hi"]
    print(f"   published effect inside GAIL-R's interval: {'YES' if inside else 'NO'}; "
          f"gap {main_s - PUBLISHED['slope']:+.3f} = {(main_s - PUBLISHED['slope']) / PUBLISHED['se']:+.2f} published SEs")

    def slopes_on(make, offset, obs):
        return torch.tensor([fit_gail_r(cd.data, same(make(cd, args.seed + offset + r)), obs,
                                        placebo_weight=0.0, uniform=True)["slopes"]["collaborates_with"]
                             for r in range(args.perms)])

    # A fake intensive session can only go to a first-round household, so fake
    # exposure tracks the household's (real) share of first-round friends. That
    # share is randomised by the design and is held fixed here, as an extra input
    # to the nuisance models, so the fake exposure carries nothing real.
    fr_obs = Observations(cd.obs.node, cd.obs.window, cd.obs.y, cd.obs.pre, cd.first_round_share)
    noise = slopes_on(random_treatment, 1000, fr_obs)
    out["noise_assignments"] = {"mean": float(noise.mean()), "sd": float(noise.std()), "R": args.perms}
    print(f"4. Pure-noise fake assignments ({args.perms}x, first-round-friend share held fixed): "
          f"mean {noise.mean():+.3f}, sd {noise.std():.3f} (should be ~0: GAIL-R does not invent spillover)")

    uni = fits["uniform attention, village effects"]["slope"]
    perm = slopes_on(permute_treatment, 5000, cd.obs)
    p = float(((perm >= uni).sum() + 1) / (len(perm) + 1))
    out["randomisation_inference"] = {"mean": float(perm.mean()), "sd": float(perm.std()), "p_value": p,
                                      "R": args.perms}
    print(f"5. Randomisation inference (experiment's within-village draw rerun {args.perms}x): "
          f"fake mean {perm.mean():+.3f}, sd {perm.std():.3f}; one-sided p-value of the real {uni:+.3f}: {p:.3f}")
    print("   (fake draws keep each village's share of intensive sessions, so they carry part of the real\n"
          "    signal and average above 0; only the p-value is the test)")

    path = Path(__file__).resolve().parents[1] / "models" / "cai_validation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
