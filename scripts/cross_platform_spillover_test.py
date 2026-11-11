"""Cross-platform sponsorship spillover (same creator). Plan: CROSS_PLATFORM_SPILLOVER_PLAN_8NOV.md.

    python scripts/cross_platform_spillover_test.py

READ-ONLY on the database. Writes models/cross_platform_spillover_results_8nov.json.
"""
from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from audience_flow_test import boot_ci  # noqa: E402
from orchestrator import load_env  # noqa: E402

OUT = ROOT / "models" / "cross_platform_spillover_results_8nov.json"
D = timedelta
AFTER, BEFORE, BURST, SETTLE, PLACEBOS = 7, 30, 14, 14, 5
NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)
FIT = {"athlete", "team", "league", "fitness_influencer"}


def main() -> int:
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    ov = {r["name"].strip().lower(): r["include"].strip().lower()
          for r in csv.DictReader(open(ROOT / "data" / "creator_scope_overrides.csv", encoding="utf-8")) if r.get("name")}
    labels = {r["content_id"]: r["fitness"].strip().lower()
              for r in csv.DictReader(open(ROOT / "data" / "event_brand_labels.csv", encoding="utf-8"))}
    cur.execute("select creator_id::text, name, category from creators")
    scope = {cid for cid, n, c in cur.fetchall()
             if ov.get((n or "").strip().lower()) == "yes" or (c in FIT and ov.get((n or "").strip().lower()) not in ("no", "overseas"))}

    cur.execute("""select creator_id::text, video_id, published_at, coalesce(is_sponsored,false),
                          ln(coalesce(view_count,0)+coalesce(like_count,0)+1), coalesce(duration_seconds,0) <= 180
                   from youtube_videos where creator_id is not null and published_at is not null""")
    yt = cur.fetchall()
    cur.execute("""select creator_id::text, post_id, posted_at, coalesce(is_sponsored,false) or coalesce(has_paid_partnership_label,false),
                          ln(coalesce(like_count,0)+coalesce(comment_count,0)+1), false
                   from instagram_posts where creator_id is not null and posted_at is not null and like_count is not null""")
    ig = cur.fetchall()
    posts = {"youtube": defaultdict(list), "instagram": defaultdict(list)}
    for plat, rows in (("youtube", yt), ("instagram", ig)):
        for cid, pid, t, sp, eng, short in rows:
            if cid in scope:
                posts[plat][cid].append((t, str(pid), sp, float(eng), short))
    for plat in posts:
        for cid in posts[plat]:
            posts[plat][cid].sort()

    # creator medians of NON-sponsored settled posts, per platform and kind
    med = {}
    for plat in posts:
        for cid, ps in posts[plat].items():
            by = defaultdict(list)
            for t, _p, sp, e, short in ps:
                if not sp and t < NOW - D(days=SETTLE):
                    by[short].append(e)
            med[(plat, cid)] = {k: statistics.median(v) for k, v in by.items() if v}

    def other_change(plat, cid, t):
        m = med.get((plat, cid), {})
        ps = posts[plat].get(cid, [])

        def window(lo, hi):
            return [e - m[s] for tt, _p, sp, e, s in ps if lo <= tt < hi and not sp and tt < NOW - D(days=SETTLE) and s in m]

        before, after = window(t - D(days=BEFORE), t), window(t, t + D(days=AFTER))
        if not before or not after:
            return None
        return statistics.mean(after) - statistics.mean(before)

    sponsored_times = defaultdict(list)  # cid -> times of sponsored posts on either platform
    for plat in posts:
        for cid, ps in posts[plat].items():
            sponsored_times[cid] += [t for t, _p, sp, _e, _s in ps if sp]
    for cid in sponsored_times:
        sponsored_times[cid].sort()

    rows, dirs, plac = [], defaultdict(list), []
    rng = random.Random(0)
    for plat, other in (("youtube", "instagram"), ("instagram", "youtube")):
        for cid, ps in posts[plat].items():
            if cid not in posts[other]:
                continue
            last = None
            for t, pid, sp, _e, _s in ps:
                if not sp or labels.get(pid) != "yes":
                    continue
                if last and (t - last).days < BURST:
                    continue
                last = t
                ch = other_change(other, cid, t)
                if ch is None:
                    continue
                rows.append((cid, ch))
                dirs[f"{plat}->{other}"].append((cid, ch))
                got = tries = 0
                st = sponsored_times[cid]
                while got < PLACEBOS and tries < 1000:
                    tries += 1
                    p = NOW - D(days=730) + D(seconds=rng.uniform(0, 716 * 86400))
                    i = bisect_left(st, p - D(days=BURST))
                    if i < len(st) and st[i] <= p + D(days=BURST):
                        continue
                    got += 1
                    pc = other_change(other, cid, p)
                    if pc is not None:
                        plac.append((cid, pc))

    eff, pl = boot_ci(rows), boot_ci(plac)
    if not eff or eff["n"] < 20:
        verdict = "fewer than 20 counted events: printed, not a result"
    elif pl and pl["lo"] <= 0 <= pl["hi"] and (eff["lo"] > 0 or eff["hi"] < 0):
        verdict = "DETECTED (" + ("positive" if eff["lo"] > 0 else "negative") + ")"
    else:
        verdict = "NOT detected"
    res = {"plan": "CROSS_PLATFORM_SPILLOVER_PLAN_8NOV.md", "unit": "log engagement vs the creator's own median, 7 days after minus 30 days before",
           "effect": eff, "placebo": pl, "verdict": verdict, "by_direction": {k: boot_ci(v) for k, v in dirs.items()}}
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
