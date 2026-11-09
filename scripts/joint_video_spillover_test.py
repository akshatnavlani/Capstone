"""Joint-video spillover. Plan: JOINT_VIDEO_SPILLOVER_PLAN_9NOV.md (fixed before any effect was computed).

    python scripts/joint_video_spillover_test.py events   # list the joint videos only (no outcome)
    python scripts/joint_video_spillover_test.py run      # the test, once

READ-ONLY on the database. Writes models/joint_video_events_9nov.json and models/joint_video_results_9nov.json.
"""
from __future__ import annotations

import csv
import json
import random
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from audience_flow_test import boot_ci  # noqa: E402
from orchestrator import load_env  # noqa: E402

EVENTS = ROOT / "models" / "joint_video_events_9nov.json"
OUT = ROOT / "models" / "joint_video_results_9nov.json"
D = timedelta
NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)
DAYS, AFTER, BEFORE, GAP, PLACEBOS, SETTLE, SMALL = 730, 14, 30, 30, 5, 14, 100_000
FIT = {"athlete", "team", "league", "fitness_influencer"}
BAD = re.compile(r"fitness|official|\bfc\b|club|team|league|cricket|\btv\b|yoga|india")
BEFORE_MARK = r"(?:ft\.?|feat\.?|featuring|with|x|×|&|vs\.?|and|collab)"
AFTER_MARK = r"(?:x|×|&)"


def load(cur):
    ov = {r["name"].strip().lower(): r["include"].strip().lower()
          for r in csv.DictReader(open(ROOT / "data" / "creator_scope_overrides.csv", encoding="utf-8")) if r.get("name")}
    cur.execute("select creator_id::text, name, category, lower(youtube_handle), lower(instagram_handle) from creators")
    scope, names, handles = set(), {}, {}
    for cid, n, c, yt, ig in cur.fetchall():
        o = ov.get((n or "").strip().lower())
        if not (o == "yes" or (c in FIT and o not in ("no", "overseas"))):
            continue
        scope.add(cid)
        base = re.sub(r"\s+", " ", re.sub(r"\(.*?\)", " ", n or "")).strip().lower()
        if len(base.split()) >= 2 and len(base) >= 8 and not BAD.search(base):
            names[base] = cid
        for h in (yt, ig):
            h = (h or "").lstrip("@")
            if len(h) >= 6:
                handles[h] = cid
    cur.execute("select creator_id::text, max(subscriber_count) from youtube_channels where creator_id is not null group by 1")
    subs = dict(cur.fetchall())
    cur.execute("""select creator_id::text, video_id, published_at, lower(coalesce(title,'')),
                          ln(coalesce(view_count,0)+coalesce(like_count,0)+1), coalesce(duration_seconds,0) <= 180
                   from youtube_videos where creator_id is not null and published_at is not null""")
    vids = defaultdict(list)
    for cid, vid, t, title, eng, short in cur.fetchall():
        vids[cid].append((t, vid, title, float(eng), short))
    return scope, names, handles, subs, vids


def find_events(scope, names, handles, vids):
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    pat = re.compile(rf"(?<![a-z0-9]){BEFORE_MARK}\s+@?({alt})(?![a-z0-9])|(?<![a-z0-9])({alt})\s+{AFTER_MARK}(?![a-z0-9])")
    hpat = re.compile(r"@([a-z0-9_.]{6,30})")
    tags = []
    for a, vs in vids.items():
        if a not in scope:
            continue
        for t, vid, title, _e, _s in vs:
            if not (NOW - D(days=DAYS) <= t < NOW):
                continue
            hit = {names[m.group(1) or m.group(2)] for m in pat.finditer(title)}
            hit |= {handles[h.rstrip(".")] for h in hpat.findall(title) if h.rstrip(".") in handles}
            for b in hit:
                if b != a and b in vids:
                    tags.append((a, b, t, vid))
    events, last = [], {}
    for a, b, t, vid in sorted(tags, key=lambda x: x[2]):
        if (a, b) in last and (t - last[(a, b)]).days < GAP:
            continue
        last[(a, b)] = t
        events.append((a, b, t, vid))
    return events


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    scope, names, handles, subs, vids = load(cur)
    events = find_events(scope, names, handles, vids)
    cur.execute("select creator_id::text, name from creators")
    cname = dict(cur.fetchall())
    EVENTS.write_text(json.dumps([{"a": cname.get(a), "b": cname.get(b), "a_id": a, "b_id": b, "t": t.isoformat(), "video_id": v}
                                  for a, b, t, v in events], ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(events)} joint-video events, {len({(a, b) for a, b, *_ in events})} pairs -> {EVENTS.name}")
    if mode == "events":
        return 0

    med = {}
    for cid, vs in vids.items():
        by = defaultdict(list)
        for t, _v, _ti, e, s in vs:
            if t < NOW - D(days=SETTLE):
                by[s].append(e)
        med[cid] = {k: statistics.median(v) for k, v in by.items() if v}

    def change(who, other, t):
        """mean relative engagement of who's videos in AFTER days minus BEFORE days; videos naming `other` left out."""
        m = med.get(who, {})
        oname = (cname.get(other) or "").lower()
        oname = re.sub(r"\s+", " ", re.sub(r"\(.*?\)", " ", oname)).strip()

        def window(lo, hi):
            return [e - m[s] for tt, _v, ti, e, s in vids.get(who, ())
                    if lo <= tt < hi and tt < NOW - D(days=SETTLE) and s in m and not (oname and oname in ti)]

        before, after = window(t - D(days=BEFORE), t), window(t, t + D(days=AFTER))
        if not before or not after:
            return None
        return statistics.mean(after) - statistics.mean(before)

    joint_times = defaultdict(list)
    for a, b, t, _v in events:
        joint_times[a].append(t)
        joint_times[b].append(t)
    rng = random.Random(0)
    rows, small, host, plac, plac_small = [], [], [], [], []
    for a, b, t, _v in events:
        if (c := change(b, a, t)) is not None:
            rows.append(((a, b), c))
            if (subs.get(b) or 0) < SMALL:
                small.append(((a, b), c))
        if (h := change(a, b, t)) is not None:
            host.append(((a, b), h))
        got = tries = 0
        while got < PLACEBOS and tries < 1000:
            tries += 1
            p = NOW - D(days=DAYS) + D(seconds=rng.uniform(0, (DAYS - SETTLE) * 86400))
            if any(abs((p - x).days) <= GAP for x in joint_times[b]):
                continue
            got += 1
            if (c := change(b, a, p)) is not None:
                plac.append(((a, b), c))
                if (subs.get(b) or 0) < SMALL:
                    plac_small.append(((a, b), c))

    def verdict(eff, pl):
        if not eff or eff["n"] < 20:
            return "fewer than 20 counted events: printed, not a result"
        return "DETECTED" if eff["lo"] > 0 and pl and pl["lo"] <= 0 <= pl["hi"] else "NOT detected"

    res = {"plan": "JOINT_VIDEO_SPILLOVER_PLAN_9NOV.md",
           "unit": "log(views+likes+1) of B's own videos vs B's median, 14 days after minus 30 days before",
           "events": len(events),
           "primary_all_B": {"effect": boot_ci(rows), "placebo": boot_ci(plac)},
           "secondary_B_under_100k": {"effect": boot_ci(small), "placebo": boot_ci(plac_small)},
           "host_A_printed_only": boot_ci(host)}
    for k in ("primary_all_B", "secondary_B_under_100k"):
        res[k]["verdict"] = verdict(res[k]["effect"], res[k]["placebo"])
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
