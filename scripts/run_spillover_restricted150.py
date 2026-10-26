"""Spillover estimates restricted to the verified 150 creators (exposed AND unexposed both inside the 150), with the planted-effect checks, saved to
models/spillover_effect_restricted150.json for the Analysis tab.

    python scripts/run_spillover_restricted150.py <shared_brand_dir> <collab_dir>

Each dir holds the data built by scripts/make_unexposed_controls.py: sub-folders real, beta_0.0, beta_0.5, beta_1.0 (the beta_* folders are SIMULATED
effects planted on the real network, the pass/fail check for the estimator). Same estimators and creator bootstrap as scripts/run_spillover_check.py.
Reads the database only for the list of verified creators and sponsored creators.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np
import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.spillover_effect import bootstrap_effects  # noqa: E402

spec = importlib.util.spec_from_file_location("rsc", ROOT / "scripts" / "run_spillover_check.py")
rsc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rsc)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]
    cur = psycopg2.connect(url).cursor()
    cur.execute("select creator_id::text from creator_verification where creator_id is not null and link_level in ('confirmed','probable')")
    ver = {r[0] for r in cur.fetchall()}
    out = {}
    for name, base in (("shared_brand", sys.argv[1]), ("collaboration", sys.argv[2])):
        out[name] = {}
        for world in ("real", "beta_0.0", "beta_0.5", "beta_1.0"):
            d = Path(base) / world
            cov, t, y, lab = rsc.load(str(d))
            ids = [c["creator_id"] for c in json.load(open(d / "creators.json", encoding="utf-8"))]
            lab = np.array([i for i in lab if ids[i] in ver])
            r = bootstrap_effects(cov, t, y, lab, draws=1000)
            r.update(n_exposed=int(t[lab].sum()), n_unexposed=int(len(lab) - t[lab].sum()))
            out[name][world] = r
            lo, hi = r["difference_in_means_ci"]
            print(f"{name:13s} {world:9s} exposed {r['n_exposed']:3d} unexposed {r['n_unexposed']:3d} | difference in means {r['difference_in_means']:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    (ROOT / "models" / "spillover_effect_restricted150.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved models/spillover_effect_restricted150.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
