"""READ-ONLY funnel audit: which collaborators (B) block exposure, and which to collect.

Links A -> B come from two sources: creator_related_accounts (any relation)
and @mentions in A's YouTube titles/descriptions and Instagram captions.
Brand accounts and self-mentions are dropped. Each link then passes or fails:

  1. B is a creator we hold (handle resolves, unambiguous)
  2. B has at least --min-posts posts (YouTube videos + Instagram posts)
  3. A has at least one dated sponsorship
  4. B has posts within +-window days on both sides of one of A's sponsorships

Writes:
  models/collab_funnel_missing.csv   B not in our database, ranked by how many of
                                     A's sponsorships B could pair with
  models/collab_funnel_thin.csv      B held but with too few posts, same ranking
  models/collab_funnel_summary.txt   the funnel counts

Usage:
    python scripts/audit_collab_funnel.py [--min-posts 20] [--window 30] [--months 24]
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.collab_funnel import mentions, straddles  # noqa: E402
from ml.creator_links import _norm  # noqa: E402


def database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("DATABASE_URL not set and not found in .env")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-posts", type=int, default=20)
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--months", type=int, default=24, help="how far back a missing B could be back-filled")
    args = ap.parse_args()

    conn = psycopg2.connect(database_url())
    conn.set_session(readonly=True)
    cur = conn.cursor()

    # Creators and their handles.
    cur.execute("select creator_id::text, name, youtube_handle, instagram_handle from creators")
    names, owners = {}, defaultdict(set)
    for cid, name, yt, ig in cur.fetchall():
        names[cid] = name or ""
        for h in (yt, ig):
            if h:
                owners[_norm(h)].add(cid)
    resolve = {h: next(iter(s)) for h, s in owners.items() if len(s) == 1}
    own = defaultdict(set)
    for h, cid in resolve.items():
        own[cid].add(h)

    cur.execute("select youtube_handle, instagram_handle, name from brands")
    brand_handles = {_norm(h) for row in cur.fetchall() for h in row if h}

    # Links A -> handle, with where they came from.
    links: dict[tuple[str, str], set[str]] = defaultdict(set)
    cur.execute("select creator_id::text, handle, coalesce(relation_type, '') from creator_related_accounts")
    for a, h, rel in cur.fetchall():
        if h:
            links[(a, _norm(h))].add(f"related:{rel}")
    for source, sql in (("yt_mention", "select creator_id::text, coalesce(title,'') || ' ' || coalesce(description,'') "
                                       "from youtube_videos where creator_id is not null"),
                        ("ig_mention", "select creator_id::text, coalesce(caption,'') "
                                       "from instagram_posts where creator_id is not null")):
        cur.execute(sql)
        for a, text in cur.fetchall():
            for h in mentions(text):
                links[(a, h)].add(source)
    links = {k: v for k, v in links.items()
             if k[1] and k[1] not in brand_handles and k[1] not in own.get(k[0], set())}

    # Post times per creator, and dated sponsorships per creator.
    posts: dict[str, list[datetime]] = defaultdict(list)
    sponsored: dict[str, list[datetime]] = defaultdict(list)
    for sql in ("select creator_id::text, published_at, coalesce(is_sponsored, false) from youtube_videos "
                "where creator_id is not null and published_at is not null",
                "select creator_id::text, posted_at, coalesce(is_sponsored, false) or coalesce(has_paid_partnership_label, false) "
                "from instagram_posts where creator_id is not null and posted_at is not null"):
        cur.execute(sql)
        for cid, t, sp in cur.fetchall():
            posts[cid].append(t)
            if sp:
                sponsored[cid].append(t)
    for v in posts.values():
        v.sort()

    now = datetime.now(timezone.utc)
    horizon = now - timedelta(days=30 * args.months)

    def recent_events(a: str) -> int:
        return sum(1 for t in sponsored.get(a, []) if (t if t.tzinfo else t.replace(tzinfo=timezone.utc)) >= horizon)

    counts = {"all links": len(links)}
    held = {k: resolve[k[1]] for k in links if k[1] in resolve and resolve[k[1]] != k[0]}
    counts["B is a creator we hold"] = len(held)
    enough = {k: b for k, b in held.items() if len(posts.get(b, [])) >= args.min_posts}
    counts[f"B has >= {args.min_posts} posts"] = len(enough)
    with_spons = {k: b for k, b in enough.items() if sponsored.get(k[0])}
    counts["A has a dated sponsorship"] = len(with_spons)
    windows, window_creators = 0, set()
    for (a, _), b in with_spons.items():
        n = sum(straddles(t, posts[b], args.window) for t in sponsored[a])
        if n:
            windows += n
            window_creators.add(b)
    counts["B straddles one of A's sponsorships (windows)"] = windows
    counts["  distinct B creators with a window"] = len(window_creators)

    # Missing B: not a creator we hold.
    missing: dict[str, dict] = {}
    for (a, h), src in links.items():
        if h in resolve:
            continue
        m = missing.setdefault(h, {"handle": h, "mentioned_by": set(), "sponsored_A": set(),
                                   "A_events_recent": 0, "sources": set()})
        m["mentioned_by"].add(a)
        m["sources"] |= src
        if sponsored.get(a):
            m["sponsored_A"].add(a)
            m["A_events_recent"] += recent_events(a)
    missing_rows = sorted(
        ({"handle": "@" + m["handle"], "A_events_recent": m["A_events_recent"],
          "sponsored_A": len(m["sponsored_A"]), "mentioned_by": len(m["mentioned_by"]),
          "example_A": "; ".join(sorted(names.get(a, a) for a in m["sponsored_A"] or m["mentioned_by"])[:3]),
          "sources": " ".join(sorted(m["sources"]))} for m in missing.values()),
        key=lambda r: (-r["A_events_recent"], -r["sponsored_A"], -r["mentioned_by"]))

    # Thin B: held but too few posts.
    thin: dict[str, dict] = {}
    for k, b in held.items():
        if len(posts.get(b, [])) >= args.min_posts:
            continue
        t = thin.setdefault(b, {"sponsored_A": set(), "A_events_recent": 0})
        if sponsored.get(k[0]) and k[0] not in t["sponsored_A"]:
            t["sponsored_A"].add(k[0])
            t["A_events_recent"] += recent_events(k[0])
    cur.execute("select creator_id::text, youtube_handle, instagram_handle from creators")
    handles = {cid: (yt or "", ig or "") for cid, yt, ig in cur.fetchall()}
    cur.execute("select creator_id::text, count(*) from youtube_videos group by 1")
    yt_n = dict(cur.fetchall())
    cur.execute("select creator_id::text, count(*) from instagram_posts group by 1")
    ig_n = dict(cur.fetchall())
    thin_rows = sorted(
        ({"name": names.get(b, ""), "creator_id": b, "youtube_handle": handles.get(b, ("", ""))[0],
          "instagram_handle": handles.get(b, ("", ""))[1], "youtube_videos": yt_n.get(b, 0),
          "instagram_posts": ig_n.get(b, 0), "A_events_recent": t["A_events_recent"],
          "sponsored_A": len(t["sponsored_A"])} for b, t in thin.items()),
        key=lambda r: (-r["A_events_recent"], -r["sponsored_A"]))

    out = ROOT / "models"
    out.mkdir(exist_ok=True)
    write_csv(out / "collab_funnel_missing.csv", missing_rows)
    write_csv(out / "collab_funnel_thin.csv", thin_rows)
    lines = [f"{k:48s} {v}" for k, v in counts.items()]
    lines += ["", f"missing B handles: {len(missing_rows)} "
                  f"({sum(1 for r in missing_rows if r['sponsored_A'])} mentioned by a sponsored A)",
              f"thin B creators:   {len(thin_rows)} "
              f"({sum(1 for r in thin_rows if r['sponsored_A'])} linked to a sponsored A)",
              f"(missing B on YouTube can be back-filled ~{args.months} months; Instagram is capped)"]
    (out / "collab_funnel_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("Wrote models/collab_funnel_missing.csv, collab_funnel_thin.csv, collab_funnel_summary.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
