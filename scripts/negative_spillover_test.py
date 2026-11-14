"""Negative spillover test. Plan: NEGATIVE_SPILLOVER_PLAN_14NOV.md (pushed 62fac33 before any data).

    python scripts/negative_spillover_test.py score   # mood per video for linked creators -> models/video_mood_14nov.json (resumable)
    python scripts/negative_spillover_test.py count   # links and bad-moment events only (no outcome)
    python scripts/negative_spillover_test.py run     # the test, once

READ ONLY on the database.
"""
import json
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_argv, sys.argv = sys.argv, [sys.argv[0], "--rep"]   # replication constants: NOW = 9 Nov 2026, 14-day settling
import audience_flow_test as af  # noqa: E402
sys.argv = _argv
import psycopg2  # noqa: E402

from joint_video_spillover_test import load  # noqa: E402

MOOD = ROOT / "models" / "video_mood_14nov.json"
EVENTS = ROOT / "models" / "negative_spillover_events_14nov.json"
OUT = ROOT / "models" / "negative_spillover_results_14nov.json"
LO, HI = datetime(2024, 11, 10, tzinfo=timezone.utc), datetime(2026, 11, 9, tzinfo=timezone.utc)
MIN_COMMENTS, PER_VIDEO, MIN_VIDEOS, PCT, ABS, GAP = 30, 50, 10, 0.10, 0.5, 30
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def connect():
    return psycopg2.connect(af.load_env()["DATABASE_URL"], connect_timeout=20)


def links(cur):
    scope = load(cur)[0]
    pairs = set()
    for f in ("audience_flow_events_rep_9nov.json", "tag_older_period_events.json"):
        for a, b, _t in json.load(open(ROOT / "models" / f)):
            pairs.add(frozenset((a, b)))
    for f in ("joint_video_events_9nov.json", "joint_video_events_9nov_older.json"):
        for e in json.load(open(ROOT / "models" / f)):
            pairs.add(frozenset((e["a_id"], e["b_id"])))
    cur.execute("select lower(youtube_handle), lower(instagram_handle), creator_id::text from creators")
    h2c = {}
    for yt, ig, cid in cur.fetchall():
        for h in (yt, ig):
            if h:
                h2c[h.lstrip("@")] = cid
    cur.execute("select creator_id::text, lower(handle) from creator_related_accounts")
    for a, h in cur.fetchall():
        b = h2c.get((h or "").lstrip("@"))
        if b and b != a:
            pairs.add(frozenset((a, b)))
    directed = defaultdict(set)   # A -> linked B (B in scope)
    for p in pairs:
        if len(p) != 2:
            continue
        a, b = tuple(p)
        if b in scope:
            directed[a].add(b)
        if a in scope:
            directed[b].add(a)
    return directed


def score():
    """The app's own scorers (ml/temporal/sentiment.py): English RoBERTa, and XLM-R for Devanagari from the local cache;
    safety = expected value with negative 0, neutral 0.5, positive 1 (= P(pos) + 0.5 P(neu))."""
    sys.path.insert(0, str(ROOT))
    from ml.temporal.sentiment import SentimentScorer, multilingual_scorer
    en_s, hi_s = SentimentScorer(), multilingual_scorer()

    def en(texts, batch_size=32):
        return [float(x) for x in en_s.score(texts)]

    def hi(texts, batch_size=32):
        return [float(x) for x in hi_s.score(texts)]

    done = json.loads(MOOD.read_text()) if MOOD.exists() else {}
    cur = connect().cursor()
    creators = sorted(links(cur))
    cur.execute("""select v.video_id, v.creator_id::text, v.published_at from youtube_videos v
                   where v.creator_id::text = any(%s) and v.published_at >= %s and v.published_at < %s
                     and (select count(*) from youtube_comments c where c.video_id = v.video_id) >= %s""", (creators, LO, HI, MIN_COMMENTS))
    vids = [r for r in cur.fetchall() if r[0] not in done]
    print(f"{len(creators)} linked creators; {len(vids)} videos to score ({len(done)} already)", flush=True)
    for i, (vid, cid, t) in enumerate(vids, 1):
        try:
            cur.execute("select text from youtube_comments where video_id = %s order by like_count desc nulls last limit %s", (vid, PER_VIDEO))
            texts = [x[0] for x in cur.fetchall() if x[0]]
        except psycopg2.Error:
            cur = connect().cursor()
            continue
        dev = [x for x in texts if DEVANAGARI.search(x)]
        lat = [x for x in texts if not DEVANAGARI.search(x)]
        scores = [x for x in (en(lat) if lat else []) + (hi(dev) if dev else []) if x == x]
        if scores:
            done[vid] = {"creator": cid, "t": t.isoformat(), "mood": sum(scores) / len(scores), "n": len(scores)}
        if i % 200 == 0:
            MOOD.write_text(json.dumps(done))
            print(f"  {i}/{len(vids)} videos scored", flush=True)
    MOOD.write_text(json.dumps(done))
    print(f"done: {len(done)} videos with a mood -> {MOOD.name}")


def events():
    mood = json.loads(MOOD.read_text())
    by = defaultdict(list)
    for v in mood.values():
        by[v["creator"]].append((datetime.fromisoformat(v["t"]), v["mood"]))
    ev = []
    for cid, rows in by.items():
        if len(rows) < MIN_VIDEOS:
            continue
        ms = sorted(m for _t, m in rows)
        cut = ms[int(PCT * (len(ms) - 1))]
        last = None
        for t, m in sorted(rows):
            if m <= cut and m < ABS and (last is None or (t - last).days >= GAP):
                ev.append((cid, t))
                last = t
    return ev, by


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "count"
    if mode == "score":
        score()
        return 0
    cur = connect().cursor()
    directed = links(cur)
    ev, by = events()
    pairs = [(a, b, t) for a, t in ev for b in directed.get(a, ())]
    EVENTS.write_text(json.dumps([(a, b, t.isoformat()) for a, b, t in pairs]))
    print(f"{len(ev)} bad moments of {len({a for a, _ in ev})} creators; {len(pairs)} (bad moment, linked B) events -> {EVENTS.name}")
    if mode != "run":
        return 0
    assert not OUT.exists(), "already run once (plan: run once)"
    cur = connect().cursor()
    cache: dict = {}
    eff = [((a, b), f) for a, b, t in pairs if (f := af.engagement_change(cur, b, t, cache)) is not None]
    bad = defaultdict(list)
    for a, t in ev:
        bad[a].append(t)
    rng, plac = random.Random(1), []
    span = (HI - LO).total_seconds()
    for a, b, t in pairs:
        got = tries = 0
        while got < af.PLACEBOS and tries < 1000:
            tries += 1
            p = LO + af.D(seconds=rng.uniform(0, span))
            if all(abs((p - x).days) > GAP for x in bad[a]):
                got += 1
                if (f := af.engagement_change(cur, b, p, cache)) is not None:
                    plac.append(((a, b), f))
    cur.execute("select creator_id::text, max(subscriber_count) from youtube_channels group by 1")
    subs = dict(cur.fetchall())
    small = [r for r in eff if (subs.get(r[0][1]) or 0) < 100_000]
    small_p = [r for r in plac if (subs.get(r[0][1]) or 0) < 100_000]

    def verdict(e, p):
        if not e or e["n"] < 20:
            return "fewer than 20 counted events: printed, not a result"
        ok = p is not None and p["lo"] <= 0 <= p["hi"]
        if e["hi"] < 0 and ok:
            return "NEGATIVE spillover DETECTED"
        if e["lo"] > 0 and ok:
            return "positive effect (interval above 0)"
        return "NOT detected"

    res = {"plan": "NEGATIVE_SPILLOVER_PLAN_14NOV.md", "run_at": datetime.now().isoformat(timespec="seconds"),
           "bad_moments": len(ev), "events": len(pairs)}
    for name, e_rows, p_rows in (("primary_all_B", eff, plac), ("secondary_B_under_100k", small, small_p)):
        e, p = af.boot_ci(e_rows), af.boot_ci(p_rows)
        res[name] = {"effect": e, "placebo": p, "verdict": verdict(e, p)}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
