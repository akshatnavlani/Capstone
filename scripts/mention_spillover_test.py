"""'Came from A' comments: do B's comments start naming A after A tags B? Plan: MENTION_SPILLOVER_PLAN_8NOV.md.

    python scripts/mention_spillover_test.py

READ-ONLY on the database. Reuses the events, windows and placebo times of scripts/audience_flow_test.py.
Writes models/mention_spillover_results_8nov.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from audience_flow_test import boot_ci, load_events, placebo_times, windows_videos  # noqa: E402
from orchestrator import load_env  # noqa: E402

OUT = ROOT / "models" / "mention_spillover_results_8nov.json"
MIN_COMMENTS = 50


def name_pattern(name: str, handles: list[str]) -> re.Pattern | None:
    terms = [h.lstrip("@").lower() for h in handles if h]
    base = re.split(r"[(\[|]", name or "")[0].strip().lower()
    if len(re.sub(r"[^a-z]", "", base)) >= 6:
        terms.append(base)
    terms = [t for t in dict.fromkeys(terms) if t]
    if not terms:
        return None
    return re.compile(r"(?<![a-z0-9_])@?(?:" + "|".join(re.escape(t) for t in terms) + r")(?![a-z0-9_])", re.I)


def comments(cur, vids):
    if not vids:
        return []
    cur.execute("select text from youtube_comments where video_id = any(%s) and text is not null", (vids,))
    return [r[0] for r in cur.fetchall()]


def main() -> int:
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    cur.execute("select creator_id::text, name, youtube_handle, instagram_handle from creators")
    who = {cid: (name, [yt, ig]) for cid, name, yt, ig in cur.fetchall()}
    events = load_events()

    def measure(a, b, t, examples=None):
        _va, vb0, vb1 = windows_videos(cur, a, b, t)
        before, after = comments(cur, vb0), comments(cur, vb1)
        if len(before) < MIN_COMMENTS or len(after) < MIN_COMMENTS:
            return None
        pat = name_pattern(*who[a])
        if pat is None:
            return None
        hb = [c for c in before if pat.search(c)]
        ha = [c for c in after if pat.search(c)]
        if examples is not None and ha and not hb:
            examples.append({"A": who[a][0], "B": who[b][0], "tag": t.date().isoformat(), "comments": [re.sub(r"\s+", " ", c)[:200] for c in ha[:2]]})
        return 1000 * len(ha) / len(after) - 1000 * len(hb) / len(before), bool(ha), bool(hb)

    ex: list = []
    main_rows, newly = [], 0
    for a, b, t in events:
        m = measure(a, b, t, ex)
        if m:
            main_rows.append(((a, b), m[0]))
            newly += m[1] and not m[2]
    plac_rows = [((a, b), m[0]) for a, b, _t, p in placebo_times(events) if (m := measure(a, b, p))]
    eff, plac = boot_ci(main_rows), boot_ci(plac_rows)
    if not eff or eff["n"] < 20:
        verdict = "fewer than 20 counted events: printed, not a result"
    else:
        verdict = "DETECTED" if eff["lo"] > 0 and plac and plac["lo"] <= 0 <= plac["hi"] else "NOT detected"
    res = {"plan": "MENTION_SPILLOVER_PLAN_8NOV.md", "unit": "comments naming A per 1,000 of B's comments, after minus before",
           "effect": eff, "placebo": plac, "verdict": verdict,
           "events_with_A_named_after_but_not_before": newly, "examples": ex[:10]}
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
