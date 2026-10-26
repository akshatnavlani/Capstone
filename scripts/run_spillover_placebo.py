"""Model-free spillover test: is a neighbour's engagement lift after a sponsored event different from the SAME neighbour's lift at placebo dates?

    PYTHONPATH=<checkout of review2-eesha-model> python scripts/run_spillover_placebo.py --rows <dir>/training_pair_deltas.json [--out models/spillover_placebo_test.json]

WHY (26 Oct 2026): comparing exposed creators with unexposed ones (scripts/run_spillover_check.py) can pick up what KIND of creator is exposed (exposed creators were already
growing faster at ordinary dates), not spillover. This test compares each neighbour with ITSELF: its lift around the event minus its mean lift at placebo dates
(whole months away, -150/-120/-90 and +90/+120/+150 days). Creator-level growth cancels. A difference that survives this is much harder to explain away.

`--rows` is the training_pair_deltas.json written by scripts/make_shared_brand_targets.py (shared_brand rows carry the event, the neighbour and `robust_lift`, the median-based
lift from Eesha's definition). Needs ml.engagement_lift and ml.target_clustering from her branch. READ ONLY on the database.
Reports every row twice: all events, and with a MATURITY GUARD (events older than 90 days, placebo dates earlier than the event, so every window has had time to grow),
and for neighbours inside the verified 150 and for everyone. Bootstrap intervals resample neighbours (and, separately, sponsoring creators): rows of one creator are not independent.
"""
import argparse
import json
import os
import random
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

from ml.engagement_lift import platform_lift, row_target
from ml.target_clustering import DEFAULT_WINDOW_DAYS, windowed_engagement

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
TABLES = {"instagram": ("instagram_posts", "posted_at", "like_count", "comment_count"),
          "youtube": ("youtube_videos", "published_at", "view_count", "like_count"),
          "reddit": ("reddit_posts", "posted_at", "score", "num_comments")}
SHIFTS_ALL = [-150, -120, -90, 90, 120, 150]
SHIFTS_MATURE = [-150, -120, -90]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", default=str(ROOT / "models" / "spillover_placebo_test.json"))
    ap.add_argument("--boot", type=int, default=5000)
    ap.add_argument("--strong-only", action="store_true",
                    help="keep only events whose sponsorship evidence is strong (official label, disclosure tag, spoken, creator comment): a check that the result is not driven by the weaker brand-name / promo-code tiers")
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env")["DATABASE_URL"]
    cur = psycopg2.connect(url).cursor()
    cur.execute("select creator_id::text from creator_verification where creator_id is not null and link_level in ('confirmed','probable')")
    ver = {r[0] for r in cur.fetchall()}
    series = defaultdict(list)
    for platform, (table, dcol, e1, e2) in TABLES.items():
        cur.execute(f"select creator_id::text, {dcol}, {e1}, {e2} from {table} where creator_id is not null and {dcol} is not null "
                    f"and {e1} is not null and {e2} is not null order by {dcol}")
        for cid, d, a, b in cur.fetchall():
            series[(cid, platform)].append((d, a + b))

    def lift_at(neighbour, when):
        pl = {}
        for platform in TABLES:
            s = series.get((neighbour, platform))
            if s:
                before, after = windowed_engagement(s, when, DEFAULT_WINDOW_DAYS)
                if before and after:
                    pl[platform] = platform_lift(before, after)
        return row_target(pl, "median") if pl else None

    all_rows = [r for r in json.load(open(args.rows, encoding="utf-8")) if r.get("relation") == "shared_brand" and r.get("robust_lift") is not None]
    if args.strong_only:
        cur.execute("select content_id from creator_sponsorship_events where sponsorship_evidence in ('official_label','spoken','creator_comment','disclosure_tag')")
        strong_ids = {r[0] for r in cur.fetchall()}
        all_rows = [r for r in all_rows if r["event_item_id"] in strong_ids]
        print(f"STRONG-EVIDENCE EVENTS ONLY: {len(strong_ids)} strong events in the database", flush=True)
    print(f"shared-brand event rows with a lift: {len(all_rows)}", flush=True)
    result = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "strong_evidence_only": args.strong_only, "shifts_days": {"all": SHIFTS_ALL, "mature": SHIFTS_MATURE}, "scopes": {}}
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    for scope, keep in (("in_the_150", lambda r: r["neighbour_id"] in ver), ("everyone", lambda r: True)):
        rows_scope = [r for r in all_rows if keep(r)]
        result["scopes"][scope] = {}
        for mode, shifts in (("all", SHIFTS_ALL), ("mature", SHIFTS_MATURE)):
            rows = rows_scope
            if mode == "mature":
                rows = [r for r in rows if datetime.fromisoformat(r["event_date"]) < cutoff]
            diffs = []
            for r in rows:
                when = datetime.fromisoformat(r["event_date"])
                base = [x for x in (lift_at(r["neighbour_id"], when + timedelta(days=d)) for d in shifts) if x is not None]
                if base:
                    diffs.append((r["neighbour_id"], r["event_creator_id"], r["robust_lift"] - st.mean(base), r["robust_lift"], st.mean(base)))
            if not diffs:
                result["scopes"][scope][mode] = {"event_rows": len(rows), "with_placebo": 0}
                continue
            by_nb, by_ev = defaultdict(list), defaultdict(list)
            for nb, ec, d, *_ in diffs:
                by_nb[nb].append(d)
                by_ev[ec].append(d)
            nbm = {k: st.mean(v) for k, v in by_nb.items()}
            evm = {k: st.mean(v) for k, v in by_ev.items()}
            rnd = random.Random(3)

            def boot(means):
                keys = list(means)
                vals = sorted(st.median(means[rnd.choice(keys)] for _ in keys) for _ in range(args.boot))
                return vals[int(0.025 * args.boot)], vals[int(0.975 * args.boot)]

            nb_lo, nb_hi = boot(nbm)
            ev_lo, ev_hi = boot(evm)
            diff_list = [d[2] for d in diffs]
            result["scopes"][scope][mode] = {
                "event_rows": len(rows), "with_placebo": len(diffs),
                "median_event_lift": st.median(d[3] for d in diffs), "median_placebo_lift": st.median(d[4] for d in diffs),
                "median_paired_difference": st.median(diff_list), "mean_paired_difference": st.mean(diff_list),
                "share_event_higher_than_placebo": sum(1 for x in diff_list if x > 0) / len(diff_list),
                "per_neighbour": {"n": len(nbm), "median_of_means": st.median(nbm.values()), "ci": [nb_lo, nb_hi], "events_beat_placebo": sum(1 for v in nbm.values() if v > 0)},
                "per_sponsoring_creator": {"n": len(evm), "median": st.median(evm.values()), "ci": [ev_lo, ev_hi]},
            }
            p = result["scopes"][scope][mode]["per_neighbour"]
            print(f"{scope:11s} {mode:6s} rows {len(diffs):6d} | median paired difference {st.median(diff_list):+.3f} | per neighbour {p['median_of_means']:+.3f} "
                  f"[{nb_lo:+.3f}, {nb_hi:+.3f}] | neighbours where events beat placebo {p['events_beat_placebo']} of {p['n']}", flush=True)
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
