"""Re-test of tag -> 7-day engagement on events no simple test has used. Plan: TAG_ENGAGEMENT_REREPLICATION_PLAN_23NOV.md (pushed first).

    python scripts/tag_engagement_rereplication_test.py count   # list the events (no outcome)
    python scripts/tag_engagement_rereplication_test.py run     # the one run

Same outcome, placebo and bootstrap as the 9 Nov replication (audience_flow_test --rep) and the 12 Nov confirmation.
READ ONLY on the database.
"""
import json
import random
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

M = ROOT / "models"
REP = M / "audience_flow_events_rep_9nov.json"             # the +10% run
FINAL = M / "audience_flow_events_rep_9nov_final21nov.json"  # same rule, 21 Nov data
CONF = M / "tag_confirmation_events_12nov.json"             # tested 12 Nov
OUT = M / "tag_rereplication_results_23nov.json"


def load(p):
    return [(a, b, t) for a, b, t in json.load(open(p, encoding="utf-8"))]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "count"
    rep, final, conf = load(REP), load(FINAL), load(CONF)
    used = set(rep) | set(conf)
    events = [e for e in final if e not in used]
    print(f"{len(final)} events in the 21 Nov list; {len(events)} never tested by a simple test "
          f"on {len({(a, b) for a, b, _ in events})} pairs, {len({b for _, b, _ in events})} tagged creators")
    if mode != "run":
        return 0
    assert not OUT.exists(), "already run once (plan: run once)"
    cur = psycopg2.connect(af.load_env()["DATABASE_URL"]).cursor()
    ev = [(a, b, datetime.fromisoformat(t)) for a, b, t in events]
    cache: dict = {}
    eff = [((a, b), f) for a, b, t in ev if (f := af.engagement_change(cur, b, t, cache)) is not None]
    tag_times = defaultdict(list)
    for a, b, t in set(final) | set(rep) | set(conf):
        tag_times[b].append(datetime.fromisoformat(t))
    rng, plac = random.Random(1), []
    for a, b, t in ev:
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
    res = {"plan": "TAG_ENGAGEMENT_REREPLICATION_PLAN_23NOV.md", "events_never_tested": len(events),
           "tagged_creators": len({b for _, b, _ in events}), "effect": e, "placebo": pl, "verdict": verdict}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
