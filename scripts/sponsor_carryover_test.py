"""Sponsorship spillover onto the same creator's other videos. Plan: SPONSOR_CARRYOVER_PLAN_9NOV.md (fixed before any count).

    python scripts/sponsor_carryover_test.py     # the test, once

READ-ONLY on the database. Writes models/sponsor_carryover_results_9nov.json.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from audience_flow_test import boot_ci  # noqa: E402
from brand_spillover_test import _Retry, brand_pattern  # noqa: E402
from orchestrator import load_env  # noqa: E402

OUT = ROOT / "models" / "sponsor_carryover_results_9nov.json"
D = timedelta
NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)
WIN, EXCL, PLACEBOS, MIN_COMMENTS, TOP, DAYS = 30, 60, 5, 50, 5, 730
FIT = {"athlete", "team", "league", "fitness_influencer"}


def main() -> int:
    cur = _Retry(load_env()["DATABASE_URL"])
    ov = {r["name"].strip().lower(): r["include"].strip().lower()
          for r in csv.DictReader(open(ROOT / "data" / "creator_scope_overrides.csv", encoding="utf-8")) if r.get("name")}
    labels = {r["content_id"]: r["fitness"].strip().lower()
              for r in csv.DictReader(open(ROOT / "data" / "event_brand_labels.csv", encoding="utf-8"))}
    cur.execute("select creator_id::text, name, category from creators")
    scope = {cid for cid, n, c in cur.fetchall()
             if (o := ov.get((n or "").strip().lower())) == "yes" or (c in FIT and o not in ("no", "overseas"))}
    cur.execute("select brand_id::text, name from brands")
    bname = dict(cur.fetchall())
    cur.execute("""select creator_id::text, video_id, published_at, coalesce(is_sponsored,false), brand_id::text, comment_count
                   from youtube_videos where creator_id is not null and published_at is not null""")
    vids = defaultdict(list)
    for cid, vid, t, sp, bid, cc in cur.fetchall():
        if cid in scope:
            vids[cid].append((t, vid, sp, bid, cc))
    spons = defaultdict(list)  # (A, brand) -> times of A's videos sponsored by that brand
    for cid, vs in vids.items():
        for t, vid, sp, bid, _cc in vs:
            if sp and bid:
                spons[(cid, bid)].append((t, vid))

    events = []
    for (a, bid), ts in spons.items():
        last = None
        for t, vid in sorted(ts):
            if labels.get(vid) != "yes":
                continue
            if last and (t - last).days < EXCL:
                continue
            last = t
            events.append((a, bid, t, vid))

    def window_videos(a, bid, lo, hi):
        sp_times = [t for t, _v in spons.get((a, bid), [])]
        cand = [(-(cc if cc is not None else -1), vid) for t, vid, sp, b, cc in vids[a]
                if lo <= t < hi and not (sp and b == bid)]
        return [v for _k, v in sorted(cand)[:TOP]], sp_times

    needed = set()
    plan = []
    rng = random.Random(0)
    for a, bid, t, vid in events:
        plan.append(("event", a, bid, t))
        got = tries = 0
        while got < PLACEBOS and tries < 1000:
            tries += 1
            p = NOW - D(days=DAYS) + D(seconds=rng.uniform(0, (DAYS - WIN) * 86400))
            if any(abs((p - x).days) <= EXCL for x, _v in spons.get((a, bid), [])):
                continue
            got += 1
            plan.append(("placebo", a, bid, p))
    for _k, a, bid, t in plan:
        for lo, hi in ((t - D(days=WIN), t), (t + D(seconds=1), t + D(days=WIN))):
            needed.update(window_videos(a, bid, lo, hi)[0])
    texts = defaultdict(list)
    needed = list(needed)
    for i in range(0, len(needed), 2000):
        cur.execute("select video_id, text from youtube_comments where video_id = any(%s) and text is not null", (needed[i:i + 2000],))
        for v, txt in cur.fetchall():
            texts[v].append(txt)

    rows, prow = [], []
    for kind, a, bid, t in plan:
        pat = brand_pattern(bname.get(bid, ""))
        if pat is None:
            continue
        out = []
        for lo, hi in ((t - D(days=WIN), t), (t + D(seconds=1), t + D(days=WIN))):
            cs = [c for v in window_videos(a, bid, lo, hi)[0] for c in texts.get(v, ())]
            if len(cs) < MIN_COMMENTS:
                break
            out.append(1000 * sum(bool(pat.search(c)) for c in cs) / len(cs))
        if len(out) == 2:
            (rows if kind == "event" else prow).append((a, out[1] - out[0]))
    eff, pl = boot_ci(rows), boot_ci(prow)
    if not eff or eff["n"] < 20:
        verdict = "fewer than 20 counted events: printed, not a result"
    else:
        verdict = "DETECTED" if eff["lo"] > 0 and pl and pl["lo"] <= 0 <= pl["hi"] else "NOT detected"
    res = {"plan": "SPONSOR_CARRYOVER_PLAN_9NOV.md",
           "unit": "comments naming the sponsored brand per 1,000 comments on A's own NON-sponsored videos, 30 days after minus before",
           "events": len(events), "effect": eff, "placebo": pl, "verdict": verdict}
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
