"""Confirmation of tag -> 7-day engagement on NEW creator pairs. Plan: TAG_ENGAGEMENT_CONFIRMATION_PLAN_12NOV.md (pushed first).

    python scripts/tag_engagement_confirmation_test.py count   # build the new-pair event list (no outcome)
    python scripts/tag_engagement_confirmation_test.py run     # the one run

Reuses audience_flow_test (replication settings: 730 days before 9 Nov 2026) for the event rule's window, the outcome
(engagement_change) and the bootstrap (boot_ci). READ ONLY on the database.
"""
import csv
import json
import random
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_argv, sys.argv = sys.argv, [sys.argv[0], "--rep"]   # replication constants (DAYS = 730, NOW = 9 Nov 2026)
import audience_flow_test as af  # noqa: E402
sys.argv = _argv

import psycopg2  # noqa: E402

EVENTS = ROOT / "models" / "tag_confirmation_events_12nov.json"
OUT = ROOT / "models" / "tag_confirmation_results_12nov.json"


def build(cur):
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
                   where creator_id is not null and posted_at >= %s and posted_at < %s""", (af.NOW - af.D(days=af.DAYS), af.NOW) * 2)
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
    rep = json.load(open(ROOT / "models" / "audience_flow_events_rep_9nov.json"))
    old_pairs = {(a, b) for a, b, _ in rep}
    new = [(a, b, t) for a, b, t in events if (a, b) not in old_pairs]
    EVENTS.write_text(json.dumps([(a, b, t.isoformat()) for a, b, t in new]))
    print(f"{len(events)} events under the rule today; {len(new)} on {len({(a, b) for a, b, _ in new})} NEW pairs "
          f"(replication had {len(rep)} events) -> {EVENTS.name}")
    return rep


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "count"
    cur = psycopg2.connect(af.load_env()["DATABASE_URL"]).cursor()
    rep = build(cur)
    if mode != "run":
        return 0
    assert not OUT.exists(), "already run once (plan: run once)"
    events = [(a, b, datetime.fromisoformat(t)) for a, b, t in json.load(open(EVENTS))]
    cache: dict = {}
    eff = [((a, b), f) for a, b, t in events if (f := af.engagement_change(cur, b, t, cache)) is not None]
    tag_times = defaultdict(list)
    for a, b, t in events + [(a, b, datetime.fromisoformat(t)) for a, b, t in rep]:
        tag_times[b].append(t)
    rng, plac = random.Random(1), []
    for a, b, t in events:
        got = tries = 0
        while got < af.PLACEBOS and tries < 1000:
            tries += 1
            p = af.NOW - af.D(days=af.DAYS) + af.D(seconds=rng.uniform(0, af.DAYS * 86400))
            if all(abs((p - x).days) > 30 for x in tag_times[b]):
                got += 1
                if (f := af.engagement_change(cur, b, p, cache)) is not None:
                    plac.append(((a, b), f))
    e, pl = af.boot_ci(eff), af.boot_ci(plac)
    if not e or e["n"] < 20:
        verdict = "fewer than 20 counted events: printed, not a result"
    else:
        verdict = "DETECTED" if e["lo"] > 0 and pl and pl["lo"] <= 0 <= pl["hi"] else "NOT detected"
    rep_bs = {b for _, b, _ in rep}
    res = {"plan": "TAG_ENGAGEMENT_CONFIRMATION_PLAN_12NOV.md", "events_new_pairs": len(events),
           "B_creators_also_in_replication": len({b for _, b, _ in events} & rep_bs), "B_creators": len({b for _, b, _ in events}),
           "effect": e, "placebo": pl, "verdict": verdict}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
