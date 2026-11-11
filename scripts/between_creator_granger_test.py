"""Between-creator Granger spillover test. Plan: BETWEEN_CREATOR_GRANGER_PLAN_10NOV.md (fixed and pushed before any number).
READ ONLY on the database; writes models/between_creator_granger_10nov.json. Run once.

    python scripts/between_creator_granger_test.py
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from run_platform_pairs import granger_f  # noqa: E402

PLACEBO, MIN_POSTS, MIN_PAIRS = 500, 5, 20


def load(ids):
    import psycopg2
    from dotenv import dotenv_values

    conn = psycopg2.connect(dotenv_values(ROOT / ".env")["DATABASE_URL"], connect_timeout=15)
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute("""select v.creator_id::text, (m.published_at at time zone 'utc')::date, count(*) from youtube_comments m join youtube_videos v using(video_id)
                   where v.creator_id::text = any(%s) and m.published_at > now() - interval '400 days'
                     and (m.published_at - v.published_at) > interval '72 hours' group by 1, 2""", (ids,))
    com = defaultdict(dict)
    for c, d, n in cur.fetchall():
        com[c][d] = int(n)
    cur.execute("""select creator_id::text, (published_at at time zone 'utc')::date from youtube_videos where creator_id::text = any(%s) and published_at > now() - interval '400 days'
                   union all select creator_id::text, (posted_at at time zone 'utc')::date from instagram_posts where creator_id::text = any(%s) and posted_at > now() - interval '400 days'""", (ids, ids))
    posts = defaultdict(lambda: defaultdict(int))
    for c, d in cur.fetchall():
        posts[c][d] += 1
    conn.close()
    return com, posts


def series(pairs, com, posts, days):
    S = {}
    for a, b in pairs:
        x = np.array([float(posts[a].get(d, 0)) for d in days])
        y = np.array([np.log1p(com[b].get(d, 0)) for d in days])
        if x.sum() >= MIN_POSTS and x.std() > 0 and y.std() > 0:
            S[f"{a}|{b}"] = (y, x)
    return S


def test(pairs, com, posts, days, pool, links):
    S = series(pairs, com, posts, days)
    out = {"pairs_listed": len(pairs), "pairs_used": len(S)}
    if len(S) < MIN_PAIRS:
        out["verdict"] = f"fewer than {MIN_PAIRS} pairs: printed, not a result"
        return out
    real = granger_f(S, cause=1)
    rng = np.random.default_rng(5)
    timing = [granger_f(S, cause=1, shifts={k: rng.integers(10, 300) for k in S}) for _ in range(PLACEBO)]
    p_t = (1 + sum(f >= real for f in timing)) / (1 + PLACEBO)
    rng = np.random.default_rng(0)
    used = [k.split("|") for k in S]
    cand = {b: [a2 for a2 in pool if a2 != b and frozenset((a2, b)) not in links] for _, b in used}
    unl = []
    for _ in range(PLACEBO):
        P = {}
        for i, (a, b) in enumerate(used):
            for _try in range(50):
                a2 = cand[b][rng.integers(len(cand[b]))]
                x = np.array([float(posts[a2].get(d, 0)) for d in days])
                if x.sum() >= MIN_POSTS and x.std() > 0:
                    P[f"{i}|{a2}|{b}"] = (S[f"{a}|{b}"][0], x)
                    break
        unl.append(granger_f(P, cause=1))
    p_u = (1 + sum(f >= real for f in unl)) / (1 + PLACEBO)
    out.update({"F": round(real, 3), "timing_placebo_F_median": round(float(np.median(timing)), 3), "p_timing": round(p_t, 4),
                "unlinked_placebo_F_median": round(float(np.median(unl)), 3), "p_unlinked": round(p_u, 4),
                "verdict": "DETECTED (between-creator)" if p_t < 0.05 and p_u < 0.05 else "NOT detected"})
    return out


def main() -> int:
    tags = json.load(open(ROOT / "models" / "audience_flow_events_rep_9nov.json"))
    joint = json.load(open(ROOT / "models" / "joint_video_events_9nov.json"))
    primary = sorted({(a, b) for a, b, _ in tags})
    secondary = sorted({(e["a_id"], e["b_id"]) for e in joint if e["a_id"] != e["b_id"]})
    links = {frozenset(p) for p in primary + secondary}
    pool = sorted({a for a, _ in primary})
    ids = sorted({c for p in primary + secondary for c in p})
    com, posts = load(ids)
    end = datetime.now(timezone.utc).date()
    days = [end.fromordinal(end.toordinal() - k) for k in range(365, 0, -1)]
    res = {"plan": "BETWEEN_CREATOR_GRANGER_PLAN_10NOV.md", "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "primary_tag_pairs": test(primary, com, posts, days, pool, links),
           "secondary_joint_video_pairs": test(secondary, com, posts, days, pool, links)}
    (ROOT / "models" / "between_creator_granger_10nov.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
