"""Real cases: a creator whose linked collaborator posted a sponsored video, and what happened to that creator's engagement. Read only; writes models/spillover_cases.json.

    python scripts/find_spillover_cases.py [--obs models/gail_observations_31oct.json] [--top 10]

Each EXPOSED observation of the real-data spillover test (the same 60 used by GAIL-R and the matched estimate) is listed with the creator, the window, the linked sponsoring collaborator and the sponsored video
nearest the middle of the window, and the creator's lift (robust change of engagement after versus before, log scale, 0.5 is about +65%). The best cases are shown, but a few big rises appear by chance everywhere,
so the same share is computed for the UNEXPOSED observations. A case list is an illustration, not proof: only an excess of big rises among the exposed would be evidence of spillover.
"""
import argparse
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        for env in (ROOT / ".env", ROOT / "backend" / ".env"):
            if env.exists():
                m = re.search(r"^DATABASE_URL=(.+)$", env.read_text(encoding="utf-8"), re.M)
                if m:
                    url = m.group(1).strip().strip('"')
                    break
    return (url or "").replace("postgresql+psycopg2://", "postgresql://")


def share(vals, cut):
    return sum(v > cut for v in vals) / len(vals) if vals else 0.0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # video titles carry emoji; the Windows console is cp1252
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--obs", default=str(ROOT / "models" / "gail_observations_31oct.json"))
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", default=str(ROOT / "models" / "spillover_cases.json"))
    args = ap.parse_args()
    obs = json.loads(Path(args.obs).read_text(encoding="utf-8"))
    ex = [o for o in obs if o["exposed"]]
    ct = [o for o in obs if not o["exposed"]]
    conn = psycopg2.connect(database_url(), connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute("select creator_id::text, name from creators")
    name = dict(cur.fetchall())
    cur.execute("""select distinct x.creator_id::text, c2.creator_id::text from creator_related_accounts x
                   join creators c2 on (lower(c2.instagram_handle) = lower(x.handle) or (x.platform = 'youtube' and lower(c2.youtube_handle) = lower(x.handle))) and c2.creator_id <> x.creator_id""")
    nb = defaultdict(set)
    for a, b in cur.fetchall():
        nb[a].add(b)
        nb[b].add(a)
    cases = []
    for o in sorted(ex, key=lambda r: -r["value"]):
        start, end = (date.fromisoformat(d) for d in o["span"])
        mid = datetime.combine(start + (end - start) / 2, datetime.min.time(), tzinfo=timezone.utc)
        best = None
        for a in nb.get(o["neighbour"], ()):
            cur.execute("""select title, published_at from youtube_videos where creator_id = %s and is_sponsored and published_at between %s and %s""",
                        (a, datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc), datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)))
            for title, when in cur.fetchall():
                gap = abs((when - mid).total_seconds())
                if best is None or gap < best[0]:
                    best = (gap, a, title, when)
        cases.append({"creator": name.get(o["neighbour"], o["neighbour"]), "category": o["category"], "window": o["span"], "lift": round(o["value"], 2),
                      "sponsoring_collaborator": name.get(best[1]) if best else None, "sponsored_video": (best[2] or "")[:90] if best else None,
                      "sponsored_on": best[3].date().isoformat() if best else None})
    conn.close()
    ev, cv = [o["value"] for o in ex], [o["value"] for o in ct]
    summary = {"exposed": len(ev), "unexposed": len(cv), "median_lift_exposed": round(statistics.median(ev), 3), "median_lift_unexposed": round(statistics.median(cv), 3),
               "share_above_0_5_exposed": round(share(ev, 0.5), 3), "share_above_0_5_unexposed": round(share(cv, 0.5), 3),
               "share_above_1_exposed": round(share(ev, 1.0), 3), "share_above_1_unexposed": round(share(cv, 1.0), 3)}
    out = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"), "summary": summary, "top_cases": cases[:args.top], "all_exposed_cases": len(cases),
           "reading": ("Exposed creators are not more likely to show a big rise than unexposed ones, so these cases are what chance alone produces; they illustrate the situation, they do not show spillover."
                       if summary["share_above_0_5_exposed"] <= summary["share_above_0_5_unexposed"] else
                       "Exposed creators show big rises more often than unexposed ones; check the placebo tests before reading this as spillover."),
           "limits": "illustration, not proof; the sponsored video is the one nearest the middle of the window among linked collaborators; mention-linked exposure is weaker than co-author posts"}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(summary))
    for c in cases[:args.top]:
        print(f"  lift {c['lift']:+.2f} | {c['creator'][:28]:28s} ({c['category']}) {c['window'][0]}..{c['window'][1]} | sponsored by {c['sponsoring_collaborator']} on {c['sponsored_on']}: {c['sponsored_video']}")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
