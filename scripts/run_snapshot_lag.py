"""Cross-platform lag test on the growth readings collected since 2026-10-11 (S1, version 2). READ ONLY on the database;
writes models/snapshot_lag.json.

    python scripts/run_snapshot_lag.py [--placebo 1000] [--out models/snapshot_lag.json]

Three tests, all with the placebo method in ml/temporal/snapshot_lag.py (12-hour windows from 48 h before to 48 h after an event):

  control   a creator's YouTube UPLOAD -> views gained on their YouTube channel.      Must be detected, or the method is broken.
  ig_to_yt  an Instagram POST          -> views gained on their YouTube videos older than 72 h (attention reaching the catalogue,
            not the new upload). Also run only on Instagram posts with no YouTube upload within 24 h either side ("pure").
  yt_to_ig  a YouTube UPLOAD           -> Instagram posting rate (does the creator post more on Instagram afterwards?).

Re-run it as data accumulates (it is cheap): the result says how many units and creators it rests on, and whether it is
"not enough data yet". A p-value is one-sided (activity higher than placebo) per window and is not corrected across windows;
the corrected threshold for the 4 windows after the event is printed next to it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.temporal.snapshot_lag import WUnit, gain_points, weighted_event_study  # noqa: E402

import psycopg2  # noqa: E402

EDGES = np.array([-48, -36, -24, -12, 0, 12, 24, 36, 48], dtype=float)
N_PRE = 4
WINDOW_LABELS = [f"{int(a)}..{int(b)}h" for a, b in zip(EDGES[:-1], EDGES[1:])]
AFTER = slice(4, 8)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        for env in (ROOT / ".env", ROOT / "backend" / ".env"):
            if env.exists():
                m = re.search(r"^DATABASE_URL=(.+)$", env.read_text(encoding="utf-8"), re.M)
                if m:
                    url = m.group(1).strip().strip('"')
                    break
    return (url or "").replace("postgresql+psycopg2://", "postgresql://")


def load(cur):
    ver = "(select creator_id from creator_verification where creator_id is not null and link_level in ('confirmed','probable'))"
    cur.execute(f"""select post_id, creator_id::text, extract(epoch from fetched_at)/3600.0, view_count from post_snapshots
                    where platform='youtube' and creator_id in {ver} and view_count is not null order by post_id, fetched_at""")
    readings = defaultdict(list); owner = {}
    for pid, cid, hour, views in cur.fetchall():
        readings[pid].append((float(hour), float(views))); owner[pid] = cid
    cur.execute(f"select video_id, creator_id::text, extract(epoch from published_at)/3600.0 from youtube_videos where creator_id in {ver}")
    published = {v: (c, float(h)) for v, c, h in cur.fetchall() if h is not None}
    cur.execute(f"select creator_id::text, extract(epoch from posted_at)/3600.0 from instagram_posts where creator_id in {ver} and posted_at is not null")
    ig = defaultdict(list)
    for c, h in cur.fetchall():
        ig[c].append(float(h))
    return readings, owner, published, {c: np.sort(np.array(v)) for c, v in ig.items()}


def build(readings, owner, published, ig):
    """Per creator: the YouTube gain points (all ages, and catalogue-only), the observed period, upload times, Instagram times."""
    per = defaultdict(lambda: {"all_t": [], "all_w": [], "cat_t": [], "cat_w": [], "lo": np.inf, "hi": -np.inf})
    for pid, pts in readings.items():
        cid = owner[pid]; pub = published.get(pid, (cid, None))[1]
        d = per[cid]
        d["lo"] = min(d["lo"], min(h for h, _ in pts)); d["hi"] = max(d["hi"], max(h for h, _ in pts))
        t, w = gain_points(pts)
        d["all_t"] += list(t); d["all_w"] += list(w)
        t2, w2 = gain_points(pts, published=pub, min_age_hours=72.0) if pub is not None else (np.array([]), np.array([]))
        d["cat_t"] += list(t2); d["cat_w"] += list(w2)
    uploads = defaultdict(list)
    for vid, (cid, h) in published.items():
        uploads[cid].append(h)
    return per, {c: np.sort(np.array(v)) for c, v in uploads.items()}


def unit_series(t, w):
    o = np.argsort(t)
    return np.array(t)[o], np.array(w)[o]


def summarise(name, study, extra=""):
    if study is None:
        return {"name": name, "status": "not enough data yet (no unit has a full 96-hour window inside the observed period)"}
    p_after = study.p_values[AFTER]
    return {
        "name": name, "status": "ok", "n_units": study.n_units, "n_creators": study.n_creators, "windows": WINDOW_LABELS,
        "excess_in_units_of_the_creators_mean_rate": [round(float(x), 4) for x in study.excess],
        "placebo_mean": [round(float(x), 4) for x in study.placebo_mean],
        "p_one_sided": [round(float(x), 4) for x in study.p_values],
        "smallest_p_after_event": round(float(p_after.min()), 4), "window_of_smallest_p": WINDOW_LABELS[4 + int(np.argmin(p_after))],
        "bonferroni_threshold_for_4_after_windows": 0.0125,
        "detected_after_correction": bool(p_after.min() < 0.0125), "note": extra,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placebo", type=int, default=1000)
    ap.add_argument("--out", default=str(ROOT / "models" / "snapshot_lag.json"))
    args = ap.parse_args()
    conn = psycopg2.connect(database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    readings, owner, published, ig = load(conn.cursor())
    conn.close()
    per, uploads = build(readings, owner, published, ig)
    now_h = datetime.now(timezone.utc).timestamp() / 3600.0
    first = min(d["lo"] for d in per.values()); last = max(d["hi"] for d in per.values())
    print(f"YouTube readings: {sum(len(v) for v in readings.values())} on {len(readings)} videos of {len(per)} creators; "
          f"observed {(last - first) / 24:.1f} days", flush=True)

    control, ig_yt, ig_yt_pure, yt_ig = [], [], [], []
    for cid, d in per.items():
        lo, hi = d["lo"], d["hi"]
        if hi - lo < 96:
            continue
        t_all, w_all = unit_series(d["all_t"], d["all_w"]); t_cat, w_cat = unit_series(d["cat_t"], d["cat_w"])
        ups = uploads.get(cid, np.array([])); posts = ig.get(cid, np.array([]))
        for e in ups:
            if lo + 48 <= e <= hi - 48 and len(t_all):
                control.append(WUnit(float(e), t_all, w_all, lo, hi, cid))
        for e in posts:
            if lo + 48 <= e <= hi - 48 and len(t_cat):
                u = WUnit(float(e), t_cat, w_cat, lo, hi, cid)
                ig_yt.append(u)
                if not len(ups) or np.min(np.abs(ups - e)) > 24:
                    ig_yt_pure.append(u)
        if len(posts) >= 5:
            p_lo, p_hi = float(posts.min()), now_h
            for e in ups:
                if p_lo + 48 <= e <= p_hi - 48:
                    yt_ig.append(WUnit(float(e), posts, np.ones(len(posts)), p_lo, p_hi, cid))
    results = []
    for name, units, note in (
            ("control: YouTube upload -> YouTube views gained", control, "must be detected, or the method is broken"),
            ("ig_to_yt: Instagram post -> views gained on YouTube videos older than 72 h", ig_yt, ""),
            ("ig_to_yt_pure: same, only Instagram posts with no YouTube upload within 24 h", ig_yt_pure, "removes cross-promotion of a new upload"),
            ("yt_to_ig: YouTube upload -> Instagram posts", yt_ig, "posting behaviour, not audience attention")):
        study = weighted_event_study(units, EDGES, N_PRE, n_placebo=args.placebo, seed=7)
        r = summarise(name, study, note)
        results.append(r)
        if r["status"] != "ok":
            print(f"- {name}: {r['status']}", flush=True)
            continue
        print(f"- {name}\n    units {r['n_units']}, creators {r['n_creators']}", flush=True)
        print("    window      " + "  ".join(f"{w:>9}" for w in WINDOW_LABELS))
        print("    excess      " + "  ".join(f"{x:9.3f}" for x in r["excess_in_units_of_the_creators_mean_rate"]))
        print("    p (1-sided) " + "  ".join(f"{x:9.3f}" for x in r["p_one_sided"]))
        print(f"    smallest p after the event: {r['smallest_p_after_event']} in {r['window_of_smallest_p']} -> "
              f"{'DETECTED (survives correction)' if r['detected_after_correction'] else 'not detected after correction'}", flush=True)
    ctl = results[0]
    verdict = ("METHOD CHECK PASSED: the positive control is detected" if ctl.get("detected_after_correction")
               else "METHOD CHECK NOT PASSED YET: the positive control is not detected, so no other result can be trusted")
    print("\n" + verdict)
    out = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "days_of_readings": round((last - first) / 24, 1),
           "windows": WINDOW_LABELS, "method_check": verdict, "results": results,
           "limits": "units from the same creator are not independent (p-values optimistic); the observed period is short; "
                     "Instagram times come from the post code (exact), Instagram engagement is not used here"}
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
