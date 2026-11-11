"""Collaboration spillover on past data: audience flow (Test 1) and 7-day engagement (Test 2). 8 Nov 2026.

    python scripts/audience_flow_test.py placebo-videos   # write the videos whose comments the placebo needs
    python scripts/audience_flow_test.py run              # both tests, exactly as AUDIENCE_FLOW_PLAN_8NOV.md
    python scripts/audience_flow_test.py build-events --rep   # the pre-registered replication (plan section "Replication"):
    python scripts/audience_flow_test.py placebo-videos --rep #   tags from 730 days, comments up to 300 per video
    python scripts/audience_flow_test.py run --rep

Plan, windows and pass mark: AUDIENCE_FLOW_PLAN_8NOV.md (fixed before any number was computed). READ-ONLY on the
database. Placebo times are drawn once with a fixed seed (0), so the placebo video list and the test use the same times.
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from orchestrator import load_env  # noqa: E402

REP = "--rep" in sys.argv  # 9 Nov 2026: the replication fixed in the plan on 8 Nov (730 days, up to 300 comments per video)
EVENTS = ROOT / "models" / ("audience_flow_events_rep_9nov.json" if REP else "audience_flow_events_7nov.json")
EVENT_VIDEOS = ROOT / "models" / "audience_flow_videos_rep_9nov.txt"
PLACEBO_VIDEOS = ROOT / "models" / ("audience_flow_placebo_videos_rep_9nov.txt" if REP else "audience_flow_placebo_videos_8nov.txt")
OUT = ROOT / "models" / ("audience_flow_results_rep_9nov.json" if REP else "audience_flow_results_8nov.json")
D = timedelta
A_DAYS, B_DAYS, T2_AFTER, MIN_AUTHORS, PLACEBOS, GAP, TOP = 60, 30, 7, 20, 5, 45, 5
DAYS = 730 if REP else 365
# the event list was built on 7 Nov (replication: 9 Nov); placebo times come from its past DAYS
NOW = datetime(2026, 11, 9, tzinfo=timezone.utc) if REP else datetime(2026, 11, 7, tzinfo=timezone.utc)


def load_events():
    return [(a, b, datetime.fromisoformat(t)) for a, b, t in json.load(open(EVENTS))]


def build_events(cur):
    """Replication only: the plan's event rule (identity rules only) on the last DAYS days. Writes EVENTS and EVENT_VIDEOS."""
    import csv
    import re
    assert REP, "the first run's event list is fixed (models/audience_flow_events_7nov.json)"
    fit = {"athlete", "team", "league", "fitness_influencer"}
    ov = {r["name"].strip().lower(): r["include"].strip().lower()
          for r in csv.DictReader(open(ROOT / "data" / "creator_scope_overrides.csv", encoding="utf-8")) if r.get("name")}
    cur.execute("select creator_id::text, name, category, lower(youtube_handle), lower(instagram_handle) from creators")
    scope, h2c = set(), {}
    for cid, n, c, yt, ig in cur.fetchall():
        o = ov.get((n or "").strip().lower())
        if o == "yes" or (c in fit and o not in ("no", "overseas")):
            scope.add(cid)
        for h in (yt, ig):
            if h:
                h2c[h.lstrip("@")] = cid
    cur.execute("select distinct creator_id::text from youtube_videos where creator_id is not null")
    on_yt = {r[0] for r in cur.fetchall()}
    cur.execute("""select creator_id::text, published_at, lower(coalesce(title,'')||' '||coalesce(description,'')) from youtube_videos
                   where creator_id is not null and published_at >= %s and published_at < %s
                   union all select creator_id::text, posted_at, lower(coalesce(caption,'')) from instagram_posts
                   where creator_id is not null and posted_at >= %s and posted_at < %s""", (NOW - D(days=DAYS), NOW) * 2)
    tags = []
    for a, t, txt in cur.fetchall():
        for m in set(re.findall(r"@([a-z0-9_.]{3,30})", txt or "")):
            b = h2c.get(m.rstrip("."))
            if b and b != a and b in scope and a in on_yt and b in on_yt:
                tags.append((a, b, t))
    events, last = [], {}
    for a, b, t in sorted(tags, key=lambda x: x[2]):
        if (a, b) in last and (t - last[(a, b)]).days < 30:
            continue
        last[(a, b)] = t
        events.append((a, b, t))
    EVENTS.write_text(json.dumps([(a, b, t.isoformat()) for a, b, t in events]))
    vids = list(dict.fromkeys(v for a, b, t in events for part in windows_videos(cur, a, b, t) for v in part))
    EVENT_VIDEOS.write_text(chr(10).join(vids))
    print(f"{len(events)} events, {len({(a, b) for a, b, _ in events})} pairs (last {DAYS} days); {len(vids)} event videos -> {EVENT_VIDEOS.name}")
    return 0


def placebo_times(events):
    """5 random times per event for the same (A, B), at least GAP days from every tag between them. Seed 0."""
    rng = random.Random(0)
    tags = defaultdict(list)
    for a, b, t in events:
        tags[(a, b)].append(t)
    out = []
    for a, b, t in events:
        got, tries = 0, 0
        while got < PLACEBOS and tries < 1000:
            tries += 1
            p = NOW - D(days=DAYS) + D(seconds=rng.uniform(0, DAYS * 86400))
            if all(abs((p - x).days) > GAP for x in tags[(a, b)]):
                out.append((a, b, t, p))
                got += 1
    return out


def top_videos(cur, cid, lo, hi, n=TOP):
    cur.execute("select video_id from youtube_videos where creator_id = %s and published_at >= %s and published_at < %s "
                "order by comment_count desc nulls last limit %s", (cid, lo, hi, n))
    return [r[0] for r in cur.fetchall()]


def windows_videos(cur, a, b, t):
    return (top_videos(cur, a, t - D(days=A_DAYS), t), top_videos(cur, b, t - D(days=B_DAYS), t),
            top_videos(cur, b, t + D(seconds=1), t + D(days=B_DAYS)))


def authors(cur, vids):
    if not vids:
        return set()
    cur.execute("select distinct author_handle from youtube_comments where video_id = any(%s) and author_handle is not null", (vids,))
    return {r[0] for r in cur.fetchall()}


def flow(cur, a, b, t):
    """share after - share before, or None when B has fewer than MIN_AUTHORS commenters on a side."""
    va, vb0, vb1 = windows_videos(cur, a, b, t)
    aud, before, after = authors(cur, va), authors(cur, vb0), authors(cur, vb1)
    if len(before) < MIN_AUTHORS or len(after) < MIN_AUTHORS or not aud:
        return None
    return len(after & aud) / len(after) - len(before & aud) / len(before)


def engagement_change(cur, b, t, median_cache):
    """Test 2: mean relative log engagement of B's videos in 7 days after minus 30 days before (settled videos only)."""
    if b not in median_cache:
        cur.execute("select coalesce(duration_seconds,0) <= 180, ln(coalesce(view_count,0) + coalesce(like_count,0) + 1) "
                    "from youtube_videos where creator_id = %s and published_at < %s", (b, NOW - D(days=14)))
        by = defaultdict(list)
        for short, v in cur.fetchall():
            by[short].append(float(v))
        median_cache[b] = {k: statistics.median(v) for k, v in by.items() if v}
    med = median_cache[b]

    def rel(lo, hi):
        cur.execute("select coalesce(duration_seconds,0) <= 180, ln(coalesce(view_count,0) + coalesce(like_count,0) + 1) "
                    "from youtube_videos where creator_id = %s and published_at >= %s and published_at < %s and published_at < %s",
                    (b, lo, hi, NOW - D(days=14)))
        return [float(v) - med[s] for s, v in cur.fetchall() if s in med]

    before, after = rel(t - D(days=B_DAYS), t), rel(t + D(seconds=1), t + D(days=T2_AFTER))
    if not before or not after:
        return None
    return statistics.mean(after) - statistics.mean(before)


def boot_ci(rows, seed=0, n=2000):
    """rows: [(pair, value)]. Mean and 95% interval resampling pairs."""
    by = defaultdict(list)
    for k, v in rows:
        by[k].append(v)
    keys = list(by)
    if not keys:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        vals = [v for k in (rng.choice(keys) for _ in keys) for v in by[k]]
        means.append(sum(vals) / len(vals))
    means.sort()
    allv = [v for _, v in rows]
    return {"mean": sum(allv) / len(allv), "lo": means[int(0.025 * n)], "hi": means[int(0.975 * n) - 1], "n": len(allv), "pairs": len(keys)}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    if mode == "build-events":
        return build_events(cur)
    events = load_events()
    plac = placebo_times(events)
    if mode == "placebo-videos":
        vids = []
        for a, b, _t, p in plac:
            for part in windows_videos(cur, a, b, p):
                vids += part
        vids = list(dict.fromkeys(vids))
        PLACEBO_VIDEOS.write_text("\n".join(vids))
        cur.execute("select count(distinct video_id) from youtube_comments where video_id = any(%s)", (vids,))
        print(f"{len(plac)} placebo times; {len(vids)} videos, {cur.fetchone()[0]} already have comments -> {PLACEBO_VIDEOS}")
        return 0

    t1 = [((a, b), f) for a, b, t in events if (f := flow(cur, a, b, t)) is not None]
    t1p = [((a, b), f) for a, b, _t, p in plac if (f := flow(cur, a, b, p)) is not None]
    cache: dict = {}
    t2 = [((a, b), f) for a, b, t in events if (f := engagement_change(cur, b, t, cache)) is not None]
    rng = random.Random(1)
    t2p = []
    tag_times = defaultdict(list)
    for _a, b, t in events:
        tag_times[b].append(t)
    for a, b, t in events:
        got = tries = 0
        while got < PLACEBOS and tries < 1000:
            tries += 1
            p = NOW - D(days=DAYS) + D(seconds=rng.uniform(0, DAYS * 86400))
            if all(abs((p - x).days) > 30 for x in tag_times[b]):
                got += 1
                if (f := engagement_change(cur, b, p, cache)) is not None:
                    t2p.append(((a, b), f))

    def verdict(main_ci, plac_ci):
        if not main_ci or main_ci["n"] < 20:
            return "fewer than 20 counted events: printed, not a result"
        placebo_ok = plac_ci is not None and plac_ci["lo"] <= 0 <= plac_ci["hi"]
        return "DETECTED" if main_ci["lo"] > 0 and placebo_ok else "NOT detected"

    res = {"plan": "AUDIENCE_FLOW_PLAN_8NOV.md", "events": len(events),
           "test1_audience_flow": {"effect": boot_ci(t1), "placebo": boot_ci(t1p)},
           "test2_engagement_7d": {"effect": boot_ci(t2), "placebo": boot_ci(t2p)}}
    res["test1_audience_flow"]["verdict"] = verdict(res["test1_audience_flow"]["effect"], res["test1_audience_flow"]["placebo"])
    res["test2_engagement_7d"]["verdict"] = verdict(res["test2_engagement_7d"]["effect"], res["test2_engagement_7d"]["placebo"])
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
