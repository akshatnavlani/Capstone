"""Short-term ATTENTION spillover on the growth readings: when creator A posts a SPONSORED video, do the older videos of A's linked collaborators gain more views than usual in the next 48 hours?
READ ONLY on the database; writes models/spillover_event_study.json.

    python scripts/run_spillover_event_study.py [--placebo 1000] [--out models/spillover_event_study.json]

WHY (31 Oct 2026). The before/after engagement test (GAIL-R, difference-in-differences) rests on a few dozen sparse medians and cannot see effects below about 1.5x. The 2-hourly growth readings
since 11 Oct give hundreds of readings per creator, so a creator's views gained per hour can be followed closely around each sponsorship. Same machinery and placebo as the cross-platform lag tests
(ml/temporal/snapshot_lag.py: 12-hour windows from 48 h before to 48 h after; placebo events keep the hour of day; one-sided p per window; Bonferroni threshold 0.0125 for the 4 windows after).

TESTS
  spillover        event = a sponsored YouTube video of A; response = views gained on B's videos older than 72 h, for each creator B linked to A (collaboration, listed collaborator or @mention).
  spillover_pure   the same, only where B uploaded nothing within 24 h of the event (so B's own upload cannot be the cause).
  random_pairs     the same events with a RANDOM unlinked creator in place of B: must NOT be detected. This is the false-alarm check.
  direct           A's own sponsored video -> A's own older videos (the sponsored creator itself): a positive control that shows the method can see an effect when there is one.

COMMENTS FAMILY (same four tests on timed YouTube comments, which reach back to 2022 and carry thousands of sponsored videos instead of the few dozen inside the 3 weeks of readings): the response is the arrival
of comments on B's videos older than 72 h, as in scripts/run_long_lag.py. Comments were collected as the newest per video at one moment, so older months are thinner; each unit is compared with its own surrounding rate.

LIMITS: the observed period of the readings family is about three weeks; units that share an event are not independent, so the p-values are optimistic (the random-pairs row shows by how much); attention (views), not sales;
only creators with readings (the verified 150) can be responders.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from ml.temporal.snapshot_lag import WUnit, weighted_event_study  # noqa: E402
from run_snapshot_lag import EDGES, N_PRE, WINDOW_LABELS, build, database_url, load, summarise, unit_series  # noqa: E402
import run_long_lag as ll  # noqa: E402


def load_all(cur):
    """Same as run_snapshot_lag.load but for EVERY creator that has readings, not only the verified 150: collaborators of sponsoring creators are often outside it."""
    cur.execute("""select post_id, creator_id::text, extract(epoch from fetched_at)/3600.0, view_count from post_snapshots
                   where platform='youtube' and creator_id is not null and view_count is not null order by post_id, fetched_at""")
    readings = defaultdict(list)
    owner = {}
    for pid, cid, hour, views in cur.fetchall():
        readings[pid].append((float(hour), float(views)))
        owner[pid] = cid
    cur.execute("select video_id, creator_id::text, extract(epoch from published_at)/3600.0 from youtube_videos where creator_id is not null")
    published = {v: (c, float(h)) for v, c, h in cur.fetchall() if h is not None}
    cur.execute("select creator_id::text, extract(epoch from posted_at)/3600.0 from instagram_posts where creator_id is not null and posted_at is not null")
    ig = defaultdict(list)
    for c, h in cur.fetchall():
        ig[c].append(float(h))
    return readings, owner, published, {c: np.sort(np.array(v)) for c, v in ig.items()}


def links(cur) -> dict[str, set[str]]:
    """Undirected links from creator_related_accounts (platform instagram resolves on instagram_handle, platform youtube on youtube_handle), same rule as scripts/ingestion/pair_count.py."""
    cur.execute("""select distinct x.creator_id::text, c2.creator_id::text from creator_related_accounts x
                   join creators c2 on (lower(c2.instagram_handle) = lower(x.handle) or (x.platform = 'youtube' and lower(c2.youtube_handle) = lower(x.handle)))
                    and c2.creator_id <> x.creator_id""")
    out: dict[str, set[str]] = defaultdict(set)
    for a, b in cur.fetchall():
        out[a].add(b)
        out[b].add(a)
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--placebo", type=int, default=1000)
    ap.add_argument("--out", default=str(ROOT / "models" / "spillover_event_study.json"))
    args = ap.parse_args()
    conn = psycopg2.connect(database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    readings, owner, published, ig = load_all(cur)
    nb = links(cur)
    cur.execute("select creator_id::text, extract(epoch from published_at)/3600.0 from youtube_videos where is_sponsored and creator_id is not null and published_at is not null")
    sponsored = defaultdict(list)
    for c, h in cur.fetchall():
        sponsored[c].append(float(h))
    conn.close()
    per, uploads = build(readings, owner, published, ig)
    first = min(d["lo"] for d in per.values())
    last = max(d["hi"] for d in per.values())
    print(f"readings on {len(readings)} videos of {len(per)} creators; observed {(last - first) / 24:.1f} days; {sum(len(v) for v in nb.values()) // 2} linked pairs overall", flush=True)

    def series(c):
        d = per[c]
        t, w = unit_series(d["cat_t"], d["cat_w"])
        return t, w, d["lo"], d["hi"]

    usable_creators = [c for c, d in per.items() if d["hi"] - d["lo"] >= 96 and len(d["cat_t"])]
    rng = np.random.default_rng(11)
    spill, pure, rand, direct = [], [], [], []
    n_events = n_pairs = 0
    for a, evs in sponsored.items():
        if a not in per:
            continue
        for e in evs:
            if not (first + 48 <= e <= last - 48):
                continue
            n_events += 1
            partners = [b for b in nb.get(a, ()) if b in per and b in usable_creators and b != a]
            for b in partners:
                t, w, lo, hi = series(b)
                if not (lo + 48 <= e <= hi - 48):
                    continue
                n_pairs += 1
                u = WUnit(float(e), t, w, lo, hi, b)
                spill.append(u)
                ups = uploads.get(b, np.array([]))
                if not len(ups) or np.min(np.abs(ups - e)) > 24:
                    pure.append(u)
                # a random unlinked creator with the same number of draws
                pool = [c for c in usable_creators if c != a and c not in nb.get(a, ()) and c != b]
                if pool:
                    c = pool[int(rng.integers(len(pool)))]
                    t2, w2, lo2, hi2 = series(c)
                    if lo2 + 48 <= e <= hi2 - 48:
                        rand.append(WUnit(float(e), t2, w2, lo2, hi2, c))
            if a in usable_creators:
                t, w, lo, hi = series(a)
                if lo + 48 <= e <= hi - 48:
                    direct.append(WUnit(float(e), t, w, lo, hi, a))
    print(f"sponsored events in the observed period: {n_events}; (event, linked responder) pairs: {n_pairs}", flush=True)
    results = []

    def report(name, units, note):
        study = weighted_event_study(units, EDGES, N_PRE, n_placebo=args.placebo, seed=7)
        r = summarise(name, study, note)
        results.append(r)
        if r["status"] != "ok":
            print(f"- {name}: {r['status']}", flush=True)
            return
        print(f"- {name}\n    units {r['n_units']}, responders {r['n_creators']}")
        print("    window      " + "  ".join(f"{w:>9}" for w in WINDOW_LABELS))
        print("    excess      " + "  ".join(f"{x:9.3f}" for x in r["excess_in_units_of_the_creators_mean_rate"]))
        print("    p (1-sided) " + "  ".join(f"{x:9.3f}" for x in r["p_one_sided"]))
        print(f"    smallest p after the event: {r['smallest_p_after_event']} in {r['window_of_smallest_p']} -> {'DETECTED (survives correction)' if r['detected_after_correction'] else 'not detected after correction'}", flush=True)

    report("readings spillover: sponsored video of A -> views gained on B's older videos (B linked to A)", spill, "the test of interest")
    report("readings spillover_pure: same, B uploaded nothing within 24 h of the event", pure, "B's own upload cannot be the cause")
    report("readings random_pairs: same events, a random UNLINKED creator as the responder", rand, "false-alarm check: must not be detected")
    report("readings direct: A's sponsored video -> A's own older videos", direct, "positive control: the sponsored creator itself")

    # ---- comments family: the long history -------------------------------------------------------------------------------------------------------
    conn2 = psycopg2.connect(database_url(), connect_timeout=15)
    conn2.set_session(readonly=True)
    c_uploads, _c_all, c_cat, _c_ig = ll.load(conn2.cursor())
    conn2.close()
    ok_c = [c for c, v in c_cat.items() if len(v) >= 20]
    cs, cpure, crand, cdirect = [], [], [], []
    ce = cp = 0
    rng2 = np.random.default_rng(23)
    for a, evs in sponsored.items():
        for e in evs:
            ce += 1
            for b in [b for b in nb.get(a, ()) if b in c_cat and b in ok_c and b != a]:
                sr = c_cat[b]
                lo, hi = float(sr[0]), float(sr[-1])
                if not (lo + 48 <= e <= hi - 48):
                    continue
                cp += 1
                u = WUnit(float(e), sr, np.ones(len(sr)), lo, hi, b)
                cs.append(u)
                ups = c_uploads.get(b, np.array([]))
                if not len(ups) or np.min(np.abs(ups - e)) > 24:
                    cpure.append(u)
                pool = [c for c in ok_c if c != a and c not in nb.get(a, ()) and c != b]
                if pool:
                    c = pool[int(rng2.integers(len(pool)))]
                    s2 = c_cat[c]
                    if float(s2[0]) + 48 <= e <= float(s2[-1]) - 48:
                        crand.append(WUnit(float(e), s2, np.ones(len(s2)), float(s2[0]), float(s2[-1]), c))
            if a in ok_c:
                sr = c_cat[a]
                if float(sr[0]) + 48 <= e <= float(sr[-1]) - 48:
                    cdirect.append(WUnit(float(e), sr, np.ones(len(sr)), float(sr[0]), float(sr[-1]), a))
    print(f"\ncomments family: {ce} sponsored events in total; (event, linked responder) pairs inside the comment history: {cp}", flush=True)
    report("comments spillover: sponsored video of A -> comments arriving on B's older videos (B linked to A)", cs, "the test of interest, long history")
    report("comments spillover_pure: same, B uploaded nothing within 24 h of the event", cpure, "B's own upload cannot be the cause")
    report("comments random_pairs: same events, a random UNLINKED creator as the responder", crand, "false-alarm check: must not be detected")
    report("comments direct: A's sponsored video -> comments on A's own older videos", cdirect, "positive control: the sponsored creator itself")
    Path(args.out).write_text(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "days_of_readings": round((last - first) / 24, 1), "windows": WINDOW_LABELS,
        "sponsored_events": n_events, "event_responder_pairs": n_pairs, "comments_events": ce, "comments_event_responder_pairs": cp, "results": results,
        "limits": "about three weeks of readings; units sharing an event are not independent (p optimistic; see random_pairs); attention not sales; only creators with readings can respond"}, indent=2), encoding="utf-8")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
