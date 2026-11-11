"""Collaboration spillover, forward subscriber test. Plan: COLLAB_SPILLOVER_PLAN_7NOV.md (fixed 7 Nov 2026, timing note 10 Nov).

    python scripts/collab_forward_test.py count   # events so far (no outcome)
    python scripts/collab_forward_test.py run     # 10 Nov: early look only; 20 Nov: the one result run

Event: A's YouTube video or Instagram post (on/after 7 Nov 2026) with @handle of held, in-scope creator B; first tag of
B by A within 30 days; self-tags excluded. Effect = log(subs t+48h / t) - log(subs t / t-48h), readings within 3 h.
Placebo: 200 random times per B with no tag of B within 7 days. Bootstrap over B creators. READ ONLY on the database.
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from audience_flow_test import boot_ci  # noqa: E402
from big_host_forward_test import at, readings  # noqa: E402  (same reading rule: nearest within 3 h, from 7 Nov)
from joint_video_spillover_test import load  # noqa: E402  (same creator scope rule)
from orchestrator import load_env  # noqa: E402

D = timedelta
START = datetime(2026, 11, 7, tzinfo=timezone.utc)
WIN, GAP_SAME, GAP_PLACEBO, PLACEBOS = 48, 30, 7, 200


def find_events(cur, scope):
    cur.execute("select creator_id::text, lower(youtube_handle), lower(instagram_handle) from creators")
    h2c = {}
    for cid, yt, ig in cur.fetchall():
        for h in (yt, ig):
            if h:
                h2c[h.lstrip("@")] = cid
    cur.execute("""select creator_id::text, published_at, lower(coalesce(title,'')||' '||coalesce(description,'')) from youtube_videos
                   where creator_id is not null and published_at >= %s
                   union all select creator_id::text, posted_at, lower(coalesce(caption,'')) from instagram_posts
                   where creator_id is not null and posted_at >= %s""", (START, START))
    tags = []
    for a, t, txt in cur.fetchall():
        for m in set(re.findall(r"@([a-z0-9_.]{3,30})", txt or "")):
            b = h2c.get(m.rstrip("."))
            if b and b != a and b in scope:
                tags.append((a, b, t))
    events, last = [], {}
    for a, b, t in sorted(tags, key=lambda x: x[2]):
        if (a, b) in last and (t - last[(a, b)]).days < GAP_SAME:
            continue
        last[(a, b)] = t
        events.append((a, b, t))
    return events, tags


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "count"
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    scope, _names, _handles, subs_now, _vids = load(cur)
    reads = readings(cur)
    events, tags = find_events(cur, scope)
    now = max((x[-1][0] for x in reads.values() if x), default=START)
    done = [e for e in events if e[2] + D(hours=WIN) <= now]
    print(f"{len(events)} collaboration events since 7 Nov ({len(done)} with 48 h passed); latest reading {now:%d %b %H:%M} UTC")
    if mode == "count":
        return 0

    def growth(b, t):
        rs = reads.get(b, [])
        s0, s1, s2 = at(rs, t - D(hours=WIN)), at(rs, t), at(rs, t + D(hours=WIN))
        return None if not (s0 and s1 and s2) else math.log(s2 / s1) - math.log(s1 / s0)

    rows, small = [], []
    for a, b, t in events:
        if (g := growth(b, t)) is not None:
            rows.append((b, g))
            if (subs_now.get(b) or 0) < 100_000:
                small.append((b, g))
    tag_times = defaultdict(list)
    for _a, b, t in tags:
        tag_times[b].append(t)
    rng, plac = random.Random(0), []
    lo, hi = START + D(hours=WIN), now - D(hours=WIN)
    for b in sorted({b for _, b, _ in events}):
        got = tries = 0
        while got < PLACEBOS and tries < 5000 and hi > lo:
            tries += 1
            p = lo + D(seconds=rng.uniform(0, (hi - lo).total_seconds()))
            if any(abs((p - x).total_seconds()) < GAP_PLACEBO * 86400 for x in tag_times[b]):
                continue
            got += 1
            if (g := growth(b, p)) is not None:
                plac.append((b, g))
    eff, pl = boot_ci(rows), boot_ci(plac)
    if not eff or eff["n"] < 20:
        verdict = "fewer than 20 counted events: early evidence, not a result"
    else:
        verdict = "DETECTED" if eff["lo"] > 0 and pl and pl["lo"] <= 0 <= pl["hi"] else "NOT detected"
    early = datetime.now(timezone.utc) < datetime(2026, 11, 19, 18, 30, tzinfo=timezone.utc)
    res = {"plan": "COLLAB_SPILLOVER_PLAN_7NOV.md", "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "run_type": "EARLY LOOK (not the result run)" if early else "RESULT RUN (20 Nov)",
           "unit": "log subscriber growth of B, 48 h after minus 48 h before the tag", "events": len(events), "events_48h_passed": len(done),
           "primary": {"effect": eff, "placebo": pl, "verdict": verdict},
           "subgroup_B_under_100k_not_the_pass_mark": boot_ci(small)}
    out = ROOT / "models" / f"collab_forward_results_{datetime.now():%d%b}.json".lower()
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
