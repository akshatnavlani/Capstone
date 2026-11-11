"""Brand-awareness spillover through the creator network. Plan: BRAND_SPILLOVER_PLAN_8NOV.md.

    python scripts/brand_spillover_test.py videos   # events + the videos whose comments are needed
    python scripts/brand_spillover_test.py run      # the test, once

READ-ONLY on the database. Writes models/brand_spillover_{events,videos}_8nov.* and models/brand_spillover_results_8nov.json.
"""
from __future__ import annotations

import csv
import json
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
from audience_flow_test import TOP, boot_ci  # noqa: E402
from known_brands import KNOWN_BRANDS  # noqa: E402
from orchestrator import load_env  # noqa: E402

EVENTS = ROOT / "models" / "brand_spillover_events_8nov.json"
VIDEOS = ROOT / "models" / "brand_spillover_videos_8nov.txt"
OUT = ROOT / "models" / "brand_spillover_results_8nov.json"
D = timedelta
WIN, EXCL, PLACEBOS, MIN_COMMENTS = 30, 60, 5, 50
NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)
FIT = {"athlete", "team", "league", "fitness_influencer"}
MENTION = re.compile(r"@([a-z0-9_.]{3,30})")


def build(cur):
    ov = {r["name"].strip().lower(): r["include"].strip().lower()
          for r in csv.DictReader(open(ROOT / "data" / "creator_scope_overrides.csv", encoding="utf-8")) if r.get("name")}
    labels = {r["content_id"]: r["fitness"].strip().lower()
              for r in csv.DictReader(open(ROOT / "data" / "event_brand_labels.csv", encoding="utf-8"))}
    cur.execute("select creator_id::text, name, category, lower(youtube_handle), lower(instagram_handle) from creators")
    scope, h2c = set(), {}
    for cid, n, c, yt, ig in cur.fetchall():
        o = ov.get((n or "").strip().lower())
        if o == "yes" or (c in FIT and o not in ("no", "overseas")):
            scope.add(cid)
        for h in (yt, ig):
            if h:
                h2c[h.lstrip("@")] = cid
    cur.execute("select distinct creator_id::text from youtube_videos where creator_id is not null")
    on_yt = {r[0] for r in cur.fetchall()}
    links = defaultdict(set)
    cur.execute("select creator_id::text, lower(handle) from creator_related_accounts")
    for a, h in cur.fetchall():
        if h and h.lstrip("@") in h2c:
            links[a].add(h2c[h.lstrip("@")])
    cur.execute("""select creator_id::text, lower(coalesce(title,'')||' '||coalesce(description,'')) from youtube_videos where creator_id is not null
                   union all select creator_id::text, lower(coalesce(caption,'')) from instagram_posts where creator_id is not null""")
    for a, txt in cur.fetchall():
        for m in MENTION.findall(txt or ""):
            if m.rstrip(".") in h2c:
                links[a].add(h2c[m.rstrip(".")])
    cur.execute("""select creator_id::text, video_id::text, published_at, brand_id::text from youtube_videos where is_sponsored and brand_id is not null and published_at is not null
                   union all select creator_id::text, post_id::text, posted_at, brand_id::text from instagram_posts
                    where (is_sponsored or has_paid_partnership_label) and brand_id is not null and posted_at is not null""")
    sp = [r for r in cur.fetchall() if r[0]]
    by_cb = defaultdict(list)
    for cid, _pid, t, bid in sp:
        by_cb[(cid, bid)].append(t)
    cur.execute("select brand_id::text, name from brands")
    bname = dict(cur.fetchall())
    events, last = [], {}
    for a, pid, t, bid in sorted(sp, key=lambda r: r[2]):
        if labels.get(pid) != "yes":
            continue
        for b in links.get(a, ()):
            if b == a or b not in scope or b not in on_yt:
                continue
            if any(abs((x - t).days) <= EXCL for x in by_cb.get((b, bid), [])):
                continue
            k = (a, b, bid)
            if k in last and (t - last[k]).days < WIN:
                continue
            last[k] = t
            events.append((a, b, bid, bname.get(bid, ""), t))
    return events, by_cb


def placebo(events, by_cb):
    rng = random.Random(0)
    out = []
    for a, b, bid, name, _t in events:
        got = tries = 0
        while got < PLACEBOS and tries < 1000:
            tries += 1
            p = NOW - D(days=730) + D(seconds=rng.uniform(0, 700 * 86400))
            if any(abs((x - p).days) <= EXCL for x in by_cb.get((a, bid), []) + by_cb.get((b, bid), [])):
                continue
            got += 1
            out.append((a, b, bid, name, p))
    return out


def brand_pattern(name: str):
    for n, _cat, handle, aliases, _common in KNOWN_BRANDS:
        if n == name:
            terms = [n.lower(), *aliases] + ([handle] if handle else [])
            return re.compile(r"(?<![a-z0-9])@?(?:" + "|".join(re.escape(x.lower()) for x in terms) + r")(?![a-z0-9])", re.I)
    return re.compile(r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])", re.I) if len(name) >= 4 else None


class _Retry:
    """Reconnect and retry a query when the server drops the connection (seen on 7-8 Nov). Changes no result."""

    def __init__(self, url):
        self.url, self.cur = url, psycopg2.connect(url).cursor()

    def execute(self, sql, params=None):
        import time
        for attempt in range(12):  # 8 Nov: the Wi-Fi DNS also drops for a minute or two, so reconnecting must wait too
            try:
                return self.cur.execute(sql, params)
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                if attempt == 11:
                    raise
                time.sleep(min(60, 5 * (attempt + 1)))
                try:
                    self.cur = psycopg2.connect(self.url, connect_timeout=20).cursor()
                except psycopg2.OperationalError:
                    pass  # still offline: the next round waits longer

    def __getattr__(self, name):
        return getattr(self.cur, name)


def video_index(cur):
    """All YouTube videos in one query (8 Nov: one query per window meant ~57,000 round trips)."""
    cur.execute("select creator_id::text, video_id, published_at, comment_count from youtube_videos "
                "where creator_id is not null and published_at is not null")
    idx = defaultdict(list)
    for cid, vid, t, cc in cur.fetchall():
        idx[cid].append((t, vid, cc))
    return idx


def top_videos(idx, cid, lo, hi, n=TOP):
    """Same rule as audience_flow_test.top_videos: top n by comment count in [lo, hi), nulls last (ties by video id)."""
    vs = [(-(cc if cc is not None else -1), vid) for t, vid, cc in idx.get(cid, ()) if lo <= t < hi]
    return [vid for _k, vid in sorted(vs)[:n]]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    cur = _Retry(load_env()["DATABASE_URL"])
    events, by_cb = build(cur)
    plac = placebo(events, by_cb)
    idx = video_index(cur)
    if mode == "videos":
        vids = []
        for _a, b, _bid, _n, t in events + plac:
            vids += top_videos(idx, b, t - D(days=WIN), t) + top_videos(idx, b, t + D(seconds=1), t + D(days=WIN))
        vids = list(dict.fromkeys(vids))
        VIDEOS.write_text("\n".join(vids))
        EVENTS.write_text(json.dumps([(a, b, bid, n, t.isoformat()) for a, b, bid, n, t in events]))
        cur.execute("select count(distinct video_id) from youtube_comments where video_id = any(%s)", (vids,))
        print(f"{len(events)} events ({len({(a, b) for a, b, *_ in events})} pairs, {len({e[3] for e in events})} brands); "
              f"{len(plac)} placebo times; {len(vids)} videos, {cur.fetchone()[0]} already have comments")
        return 0

    cur.execute("select video_id, text from youtube_comments where video_id = any(%s) and text is not null",
                (VIDEOS.read_text().split(),))
    texts = defaultdict(list)
    for vid, txt in cur.fetchall():
        texts[vid].append(txt)

    def measure(b, name, t):
        pat = brand_pattern(name)
        if pat is None:
            return None
        out = []
        for lo, hi in ((t - D(days=WIN), t), (t + D(seconds=1), t + D(days=WIN))):
            cs = [c for v in top_videos(idx, b, lo, hi) for c in texts.get(v, ())]
            if len(cs) < MIN_COMMENTS:
                return None
            out.append(1000 * sum(bool(pat.search(c)) for c in cs) / len(cs))
        return out[1] - out[0]

    rows = [((a, b), m) for a, b, _bid, n, t in events if (m := measure(b, n, t)) is not None]
    prow = [((a, b), m) for a, b, _bid, n, p in plac if (m := measure(b, n, p)) is not None]
    eff, pl = boot_ci(rows), boot_ci(prow)
    if not eff or eff["n"] < 20:
        verdict = "fewer than 20 counted events: printed, not a result"
    else:
        verdict = "DETECTED" if eff["lo"] > 0 and pl and pl["lo"] <= 0 <= pl["hi"] else "NOT detected"
    res = {"plan": "BRAND_SPILLOVER_PLAN_8NOV.md", "unit": "comments mentioning the brand per 1,000 of B's comments, after minus before",
           "events": len(events), "effect": eff, "placebo": pl, "verdict": verdict}
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
