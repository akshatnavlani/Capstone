"""Collaborator lag test on real data (PendingWork S1): after creator A's sponsored post,
does a collaborator B show extra activity in the next hours / days, on the same platform or
another one? READ ONLY; writes models/event_lag.json.

    python scripts\\run_event_lag.py

Why not "growth": the database holds one snapshot per account, no follower history, and a post's
likes are the totals at scrape time. So B's reaction is measured as ATTENTION on each platform:
  reddit_mentions  Reddit posts that name B            reddit_comments  comments on those posts
  yt_videos        B's uploads                          yt_comments      comments on B's videos
  ig_posts         B's Instagram posts (day level for most)

Time resolution limits what can be tested. 53 of 55 Instagram sponsored events carry only a date,
so those use DAY windows (event day, next day, day after). The 9 events with a time of day use 12 h windows
when the response series has hours too. A "24 hour lag" is the next-day window for date-only events and
the 12-24 h window for timed ones.

Collaborators B are A's neighbours in the SUPPORTED graph: collaboration tags plus Reddit co-occurrences
that name both creators in full (backend/app/feature_store.py). Significance comes from a placebo test
(ml/temporal/event_study.py). A positive control (a creator's own YouTube upload -> comments on their
channel) must be detected, otherwise the method is broken.
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

DAY_EDGES = np.array([-72, -48, -24, 0, 24, 48, 72], dtype=float)          # windows 0-2 pre, 3 event day, 4 next day, 5 day after
HOUR_EDGES = np.array([-48, -36, -24, -12, 0, 12, 24, 36, 48], dtype=float)  # windows 0-3 pre, 4: 0-12h, 5: 12-24h, 6: 24-36h, 7: 36-48h
DAY_LABELS = ["event day", "next day (24h)", "day after"]
HOUR_LABELS = ["0-12h", "12-24h", "24-36h", "36-48h"]
SAME_PLATFORM = {"instagram": {"ig_posts"}, "youtube": {"yt_videos", "yt_comments"}, "reddit": {"reddit_mentions", "reddit_comments"}}
HOUR_RESPONSES = {"yt_videos", "yt_comments", "reddit_mentions", "reddit_comments"}  # have a time of day


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    os.environ["DATABASE_URL"] = url
    from ml._scipy_compat import avoid_blocked_scipy_solver

    avoid_blocked_scipy_solver()
    from sqlalchemy import text
    from sqlmodel import Session, create_engine

    from app import feature_store
    from ml.temporal.event_study import Unit, event_study

    engine = create_engine(url)
    with Session(engine) as s:
        neighbours = collections.defaultdict(set)
        for e in feature_store.build_collaboration_edges(s) + feature_store.build_supported_co_occurrence_edges(s):
            neighbours[str(e.source_creator_id)].add(str(e.target_creator_id))
        q = lambda sql: s.exec(text(sql)).all()
        events = q("select creator_id::text, platform, posted_at from creator_sponsorship_events where creator_id is not null and posted_at is not null")
        queries = {
            "reddit_mentions": "select pc.creator_id::text, p.posted_at from reddit_post_creators pc join reddit_posts p on p.post_id = pc.post_id where p.posted_at is not null",
            "reddit_comments": "select pc.creator_id::text, c.posted_at from reddit_post_creators pc join reddit_comments c on c.post_id = pc.post_id where c.posted_at is not null",
            "yt_videos": "select creator_id::text, published_at from youtube_videos where creator_id is not null and published_at is not null",
            "yt_comments": "select v.creator_id::text, c.published_at from youtube_comments c join youtube_videos v on v.video_id = c.video_id where v.creator_id is not null and c.published_at is not null",
            "ig_posts": "select creator_id::text, posted_at from instagram_posts where creator_id is not null and posted_at is not null",
        }
        series: dict[str, dict[str, np.ndarray]] = {}
        for name, sql in queries.items():
            by = collections.defaultdict(list)
            for cid, ts in q(sql):
                by[cid].append(ts.timestamp() / 3600.0)
            series[name] = {cid: np.sort(np.array(v)) for cid, v in by.items()}

    def is_day_level(ts) -> bool:
        return ts.hour == 0 and ts.minute == 0 and ts.second == 0

    n_hour = sum(not is_day_level(e[2]) for e in events)
    print(f"{len(events)} sponsored events with a creator and a time ({n_hour} with a time of day); "
          f"{sum(1 for e in events if neighbours.get(e[0]))} have at least one collaborator in the supported graph\n")

    # ---- units per (event platform, response platform, resolution) ---------------------------------
    groups: dict[tuple[str, str, str], list] = collections.defaultdict(list)
    for a, plat, ts in events:
        t0 = ts.timestamp() / 3600.0
        for b in neighbours.get(a, ()):
            for resp, by in series.items():
                arr = by.get(b)
                if arr is None or len(arr) < 5:
                    continue
                res = "hour" if (not is_day_level(ts) and resp in HOUR_RESPONSES) else "day"
                groups[(plat, resp, res)].append(Unit(t0=t0, times=arr, lo=float(arr[0]), hi=float(arr[-1])))

    results = {}
    print("COLLABORATOR REACTION AFTER A's SPONSORED POST (excess activity vs B's own pre-event rate; placebo p, one-sided)")
    print(f"{'event on':10s} -> {'B active on':16s} {'windows':6s} {'pairs':>5s} {'usable':>6s} | excess per window (p) at the post windows")
    for (plat, resp, res), units in sorted(groups.items()):
        edges, n_pre, labels = (HOUR_EDGES, 4, HOUR_LABELS) if res == "hour" else (DAY_EDGES, 3, DAY_LABELS)
        st = event_study(units, edges, n_pre, n_placebo=2000, seed=0)
        cross = resp not in SAME_PLATFORM[plat]
        if st is None:
            print(f"{plat:10s} -> {resp:16s} {res:6s} {len(units):5d} {0:6d} | no pair has B's data covering the whole window")
            results[f"{plat}->{resp}/{res}"] = {"pairs": len(units), "usable": 0, "cross_platform": cross}
            continue
        cells = "  ".join(f"{lab} {st.excess[n_pre + i]:+.2f} (p {st.p_values[n_pre + i]:.2f})" for i, lab in enumerate(labels[: len(edges) - 1 - n_pre]))
        print(f"{plat:10s} -> {resp:16s} {res:6s} {len(units):5d} {st.n_units:6d} | {cells}{'  [CROSS-PLATFORM]' if cross else ''}")
        results[f"{plat}->{resp}/{res}"] = {"pairs": len(units), "usable": st.n_units, "cross_platform": cross,
                                            "excess": st.excess.tolist(), "p": st.p_values.tolist(), "labels": labels}

    # ---- all cross-platform / all same-platform pooled ----------------------------------------------------------
    for label, want_cross in (("ALL CROSS-PLATFORM", True), ("ALL SAME-PLATFORM", False)):
        for res, edges, n_pre, labs in (("day", DAY_EDGES, 3, DAY_LABELS), ("hour", HOUR_EDGES, 4, HOUR_LABELS)):
            units = [u for (plat, resp, r), us in groups.items() if r == res and (resp not in SAME_PLATFORM[plat]) == want_cross for u in us]
            st = event_study(units, edges, n_pre, n_placebo=2000, seed=1)
            if st is None:
                continue
            cells = "  ".join(f"{lab} {st.excess[n_pre + i]:+.2f} (p {st.p_values[n_pre + i]:.2f})" for i, lab in enumerate(labs[: len(edges) - 1 - n_pre]))
            print(f"{label:20s} {res:5s} usable pairs {st.n_units:4d} | {cells}")
            results[f"{label}/{res}"] = {"usable": st.n_units, "excess": st.excess.tolist(), "p": st.p_values.tolist(), "labels": labs}

    # ---- positive control ------------------------------------------------------------------------------------------------
    rng = np.random.default_rng(0)
    ctrl = []
    for cid, uploads in series["yt_videos"].items():
        com = series["yt_comments"].get(cid)
        if com is None or len(com) < 5:
            continue
        pick = rng.choice(uploads, size=min(8, len(uploads)), replace=False)
        ctrl += [Unit(t0=float(t), times=com, lo=float(com[0]), hi=float(com[-1])) for t in pick]
    st = event_study(ctrl, HOUR_EDGES, 4, n_placebo=1000, seed=2)
    print("\nPOSITIVE CONTROL: a creator's own YouTube upload -> comments on their channel (must be detected)")
    if st is None:
        print("   no usable units")
    else:
        cells = "  ".join(f"{lab} {st.excess[4 + i]:+.1f} (p {st.p_values[4 + i]:.3f})" for i, lab in enumerate(HOUR_LABELS))
        print(f"   {st.n_units} uploads | {cells}")
        results["positive_control"] = {"usable": st.n_units, "excess": st.excess.tolist(), "p": st.p_values.tolist()}

    (ROOT / "models" / "event_lag.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\nsaved models/event_lag.json")


if __name__ == "__main__":
    main()
