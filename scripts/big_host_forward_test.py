"""Big host -> small guest, forward subscriber test. Plan: BIG_HOST_SPILLOVER_PLAN_9NOV.md (fixed 9 Nov 2026, before data).

    python scripts/big_host_forward_test.py count         # how many events so far (no outcome is computed)
    python scripts/big_host_forward_test.py run           # the test: on 20 Nov 2026 (and a final run on 30 Nov)
    python scripts/big_host_forward_test.py exploratory   # past joint videos with host >= 10x (context only, not confirmatory)

READ-ONLY on the database. Writes models/big_host_events.json and models/big_host_results_<date>.json.
"""
from __future__ import annotations

import bisect
import json
import math
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
from joint_video_spillover_test import AFTER_MARK, BEFORE_MARK, load  # noqa: E402
from orchestrator import load_env  # noqa: E402

D = timedelta
START = datetime(2026, 11, 9, 18, 30, tzinfo=timezone.utc)   # 10 Nov 2026 00:00 IST
END = datetime(2026, 11, 30, 18, 30, tzinfo=timezone.utc)
READ_START = datetime(2026, 11, 7, tzinfo=timezone.utc)
RATIO, RATIO2, WIN, TOL, GAP, PLACEBOS = 3, 10, 48, 3, 7, 200
EVENTS = ROOT / "models" / "big_host_events.json"


def readings(cur):
    cur.execute("""select creator_id::text, fetched_at, follower_count from profile_snapshots
                   where platform = 'youtube' and creator_id is not null and follower_count is not null and fetched_at >= %s
                   order by fetched_at""", (READ_START,))
    out = defaultdict(list)
    for cid, t, f in cur.fetchall():
        out[cid].append((t, int(f)))
    return out


def at(rs, t):
    """Subscriber reading nearest to t within TOL hours, else None."""
    if not rs:
        return None
    ts = [x[0] for x in rs]
    i = bisect.bisect_left(ts, t)
    best = min((rs[j] for j in (i - 1, i) if 0 <= j < len(rs)), key=lambda r: abs((r[0] - t).total_seconds()))
    return best[1] if abs((best[0] - t).total_seconds()) <= TOL * 3600 and best[1] > 0 else None


def before(rs, t):
    prev = [f for tt, f in rs if tt <= t]
    return prev[-1] if prev else None


def find_events(cur, scope, names, handles, subs_now, reads):
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    pat = re.compile(rf"(?<![a-z0-9]){BEFORE_MARK}\s+@?({alt})(?![a-z0-9])|(?<![a-z0-9])({alt})\s+{AFTER_MARK}(?![a-z0-9])")
    hpat = re.compile(r"@([a-z0-9_.]{6,30})")
    cur.execute("""select creator_id::text, video_id, published_at, lower(coalesce(title,'')), lower(coalesce(description,''))
                   from youtube_videos where creator_id is not null and published_at >= %s and published_at < %s""", (START, END))
    raw = []
    for a, vid, t, title, desc in cur.fetchall():
        hit = {names[m.group(1) or m.group(2)] for m in pat.finditer(title)}
        hit |= {handles[h.rstrip(".")] for h in hpat.findall(title + " " + desc) if h.rstrip(".") in handles}
        for b in hit:
            if b == a or b not in scope:
                continue
            sa = before(reads.get(a, []), t) or subs_now.get(a)
            sb = before(reads.get(b, []), t) or subs_now.get(b)
            if sa and sb and sa >= RATIO * sb:
                raw.append((b, t, a, vid, sa / sb))
    events, last = [], {}
    for b, t, a, vid, r in sorted(raw, key=lambda x: x[1]):
        if b in last and (t - last[b]).days < GAP:
            continue
        last[b] = t
        events.append((b, t, a, vid, r))
    return events


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "count"
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    scope, names, handles, subs_now, vids = load(cur)
    reads = readings(cur)
    if mode == "exploratory":
        return exploratory(subs_now)
    events = find_events(cur, scope, names, handles, subs_now, reads)
    cur.execute("select creator_id::text, name from creators")
    cname = dict(cur.fetchall())
    EVENTS.write_text(json.dumps([{"guest": cname.get(b), "host": cname.get(a), "t": t.isoformat(), "video_id": v, "ratio": round(r, 1)}
                                  for b, t, a, v, r in events], ensure_ascii=False, indent=0), encoding="utf-8")
    now = max((x[-1][0] for x in reads.values() if x), default=START)
    complete = [e for e in events if e[1] + D(hours=WIN) <= now]
    print(f"{len(events)} big-host events since 10 Nov ({len(complete)} with 48 h passed); latest reading {now:%d %b %H:%M} UTC -> {EVENTS.name}")
    if mode == "count":
        return 0

    def growth(b, t):
        rs = reads.get(b, [])
        s0, s1, s2 = at(rs, t - D(hours=WIN)), at(rs, t), at(rs, t + D(hours=WIN))
        if not (s0 and s1 and s2):
            return None
        return math.log(s2 / s1) - math.log(s1 / s0)

    rng = random.Random(0)
    rows, rows10, plac = [], [], []
    ev_times = defaultdict(list)
    for b, t, *_ in events:
        ev_times[b].append(t)
    for b, t, a, _v, r in events:
        if (g := growth(b, t)) is not None:
            rows.append((b, g))
            if r >= RATIO2:
                rows10.append((b, g))
    for b in ev_times:
        lo, hi = READ_START + D(hours=WIN), now - D(hours=WIN)
        got = tries = 0
        while got < PLACEBOS and tries < 5000 and hi > lo:
            tries += 1
            p = lo + D(seconds=rng.uniform(0, (hi - lo).total_seconds()))
            if any(abs((p - x).days) < GAP for x in ev_times[b]):
                continue
            got += 1
            if (g := growth(b, p)) is not None:
                plac.append((b, g))

    def verdict(eff, pl):
        if not eff or eff["n"] < 20:
            return "fewer than 20 counted events: early evidence, not a result"
        return "DETECTED" if eff["lo"] > 0 and pl and pl["lo"] <= 0 <= pl["hi"] else "NOT detected"

    res = {"plan": "BIG_HOST_SPILLOVER_PLAN_9NOV.md", "run_at": datetime.now(timezone.utc).isoformat(),
           "unit": "log subscriber growth of the guest, 48 h after minus 48 h before", "events": len(events),
           "primary_host_3x": {"effect": boot_ci(rows), "placebo": boot_ci(plac)},
           "secondary_host_10x": {"effect": boot_ci(rows10), "placebo": boot_ci(plac)}}
    for k in ("primary_host_3x", "secondary_host_10x"):
        res[k]["verdict"] = verdict(res[k]["effect"], res[k]["placebo"])
    out = ROOT / "models" / f"big_host_results_{datetime.now():%d%b}.json".lower()
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


def exploratory(subs_now) -> int:
    """Past joint videos with host >= 10x guest, joint-video measure. Context only (these videos were already analysed pooled)."""
    import joint_video_spillover_test as jv
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    scope, names, handles, subs, vids = jv.load(cur)
    events = [(a, b, t, v) for a, b, t, v in jv.find_events(scope, names, handles, vids)
              if subs.get(a) and subs.get(b) and subs[a] >= RATIO2 * subs[b]]
    cur.execute("select creator_id::text, name from creators")
    cname = dict(cur.fetchall())
    med = {}
    for cid, vs in vids.items():
        by = defaultdict(list)
        for t, _v, _ti, e, s in vs:
            if t < jv.NOW - D(days=jv.SETTLE):
                by[s].append(e)
        med[cid] = {k: statistics.median(x) for k, x in by.items() if x}

    def change(who, other, t):
        m = med.get(who, {})
        oname = re.sub(r"\s+", " ", re.sub(r"\(.*?\)", " ", (cname.get(other) or "").lower())).strip()
        w = lambda lo, hi: [e - m[s] for tt, _v, ti, e, s in vids.get(who, ())  # noqa: E731
                            if lo <= tt < hi and tt < jv.NOW - D(days=jv.SETTLE) and s in m and not (oname and oname in ti)]
        b0, b1 = w(t - D(days=jv.BEFORE), t), w(t, t + D(days=jv.AFTER))
        return statistics.mean(b1) - statistics.mean(b0) if b0 and b1 else None

    rows = [((a, b), c) for a, b, t, _v in events if (c := change(b, a, t)) is not None]
    res = {"label": "EXPLORATORY (context only; these videos were already analysed in the pooled joint-video test)",
           "plan": "BIG_HOST_SPILLOVER_PLAN_9NOV.md, section Exploratory", "events": len(events), "effect": boot_ci(rows)}
    (ROOT / "models" / "big_host_exploratory_9nov.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
