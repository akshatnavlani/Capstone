"""SIMULATED validation on the REAL growth readings: how large would a delayed cross-platform effect have to be for our lag test to find it? Writes only a local JSON.

    python scripts/sim_lag_power.py [--placebo 300] [--out models/sim_lag_power.json]

Takes the real units of the Instagram -> YouTube lag test (real Instagram post times, real YouTube view-gain series since 11 Oct) and PLANTS extra attention on the creator's
YouTube catalogue 12 to 36 hours after each Instagram post: extra = `s` x the creator's own mean attention rate x 24 hours, spread over six points in that window.
Then runs the same placebo event study as scripts/run_snapshot_lag.py and records whether the smallest after-event p survives the 4-window correction (p < 0.0125). Five
random plantings per size. `s = 0` is the false-alarm check; the control (a YouTube upload and views on the same channel) shows the method on a real effect.
Reads the database only; nothing is written to it, and the result is labelled SIMULATED everywhere it is shown.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_snapshot_lag as lag  # noqa: E402
from ml.temporal.snapshot_lag import WUnit, weighted_event_study  # noqa: E402

SIZES = [0.0, 0.03, 0.06, 0.1, 0.15, 0.25, 0.5, 1.0]


def plant(units: list[WUnit], s: float, rng: np.random.Generator) -> list[WUnit]:
    out = []
    for u in units:
        if s == 0 or not len(u.times):
            out.append(u)
            continue
        rate = float(u.weights.sum()) / max(u.hi - u.lo, 1.0)          # attention per hour on a normal day
        extra_t = u.t0 + rng.uniform(12.0, 36.0, size=6)
        extra_w = np.full(6, s * rate * 24.0 / 6.0)
        t = np.concatenate([u.times, extra_t])
        w = np.concatenate([u.weights, extra_w])
        o = np.argsort(t)
        out.append(WUnit(u.t0, t[o], w[o], u.lo, u.hi, u.creator))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placebo", type=int, default=300)
    ap.add_argument("--plantings", type=int, default=5)
    ap.add_argument("--out", default=str(lag.ROOT / "models" / "sim_lag_power.json"))
    args = ap.parse_args()
    import psycopg2

    conn = psycopg2.connect(lag.database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    readings, owner, published, ig = lag.load(conn.cursor())
    conn.close()
    per, uploads = lag.build(readings, owner, published, ig)
    ig_yt, ig_yt_pure = [], []
    for cid, d in per.items():
        lo, hi = d["lo"], d["hi"]
        if hi - lo < 96:
            continue
        t_cat, w_cat = lag.unit_series(d["cat_t"], d["cat_w"])
        ups, posts = uploads.get(cid, np.array([])), ig.get(cid, np.array([]))
        for e in posts:
            if lo + 48 <= e <= hi - 48 and len(t_cat):
                u = WUnit(float(e), t_cat, w_cat, lo, hi, cid)
                ig_yt.append(u)
                if not len(ups) or np.min(np.abs(ups - e)) > 24:
                    ig_yt_pure.append(u)
    result = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "simulated": True,
              "how": "extra attention of s x the creator's own mean rate x 24 h, spread over 12-36 h after each real Instagram post; detection = smallest after-event p < 0.0125 (4 windows, Bonferroni)",
              "sets": {}}
    for name, units in (("ig_to_yt (all posts)", ig_yt), ("ig_to_yt_pure (no YouTube upload within 24 h)", ig_yt_pure)):
        base = weighted_event_study(units, lag.EDGES, lag.N_PRE, n_placebo=args.placebo, seed=7)
        n_units, n_creators = (base.n_units, base.n_creators) if base else (0, 0)
        rows = {}
        print(f"{name}: units {n_units}, creators {n_creators}", flush=True)
        for s in SIZES:
            hits, ps = 0, []
            for k in range(args.plantings):
                rng = np.random.default_rng(100 * k + int(s * 10))
                study = weighted_event_study(plant(units, s, rng), lag.EDGES, lag.N_PRE, n_placebo=args.placebo, seed=7 + k)
                if study is not None:
                    p = float(study.p_values[lag.AFTER].min())
                    ps.append(p)
                    hits += int(p < 0.0125)
            rows[str(s)] = {"detected_share": hits / max(len(ps), 1), "median_smallest_p": float(np.median(ps)) if ps else None}
            print(f"   extra attention +{s * 100:4.0f}% of a normal day, 12-36 h after the post: detected in {hits}/{len(ps)} plantings (median smallest p {rows[str(s)]['median_smallest_p']:.4f})", flush=True)
        result["sets"][name] = {"units": n_units, "creators": n_creators, "by_size": rows}
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
