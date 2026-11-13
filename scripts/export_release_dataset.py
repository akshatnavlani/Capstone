r"""Anonymised release dataset for the paper (14 Nov 2026). READ ONLY on the database; writes CSVs to exports/release_dataset/
(git-ignored: nothing is published by this script; publishing is the team's decision).

    venv\Scripts\python.exe scripts\export_release_dataset.py

What is left out on purpose: names, handles, channel and video ids, titles, descriptions, captions, comments, thumbnails,
brand names. Creators, videos and posts get salted hash keys; the salt is generated once and kept only on this laptop
(exports/release_dataset/.salt), so keys cannot be reversed from the files. Counts and dates are kept because the analyses
need them; subscriber counts are given only as a size band. See release/DATASHEET.md.
"""
import csv
import hashlib
import json
import secrets
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from joint_video_spillover_test import load  # noqa: E402
from orchestrator import load_env  # noqa: E402

OUT = ROOT / "exports" / "release_dataset"
OUT.mkdir(parents=True, exist_ok=True)
salt_file = OUT / ".salt"
if not salt_file.exists():
    salt_file.write_text(secrets.token_hex(16))
SALT = salt_file.read_text().strip()


def key(kind: str, raw) -> str:
    return hashlib.sha256(f"{SALT}|{kind}|{raw}".encode()).hexdigest()[:12]


def band(n):
    if n is None:
        return ""
    for lim, lab in ((1e4, "<10K"), (1e5, "10K-100K"), (1e6, "100K-1M"), (1e7, "1M-10M")):
        if n < lim:
            return lab
    return "10M+"


def write(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"{name}: {len(rows):,} rows")


def fresh():
    """A new connection per section: the hosted database drops long idle connections."""
    return psycopg2.connect(load_env()["DATABASE_URL"], connect_timeout=20).cursor()


cur = fresh()
scope = load(cur)[0]
cur.execute("select brand_id::text, category from brands")
bcat = dict(cur.fetchall())
cur.execute("""select c.creator_id::text, c.category, lower(c.youtube_handle), lower(c.instagram_handle),
                      (select max(subscriber_count) from youtube_channels y where y.creator_id = c.creator_id),
                      exists (select 1 from youtube_videos v where v.creator_id = c.creator_id),
                      exists (select 1 from instagram_posts p where p.creator_id = c.creator_id)
               from creators c""")
creators, h2c = [], {}
for cid, cat, yt, ig, subs, has_yt, has_ig in cur.fetchall():
    creators.append([key("c", cid), cat or "", int(cid in scope), int(has_yt), int(has_ig), band(subs)])
    for h in (yt, ig):
        if h:
            h2c[h.lstrip("@")] = cid
write("creators.csv", ["creator_key", "category", "in_scope", "has_youtube", "has_instagram", "subscriber_band"], creators)

cur = fresh()
cur.execute("""select creator_id::text, video_id, published_at::date, coalesce(duration_seconds, 0) <= 180, view_count, like_count,
                      comment_count, is_sponsored, sponsorship_evidence, brand_id::text
               from youtube_videos where creator_id is not null""")
write("youtube_videos.csv", ["creator_key", "video_key", "published_date", "is_short", "views", "likes", "comments", "is_sponsored",
                             "sponsorship_evidence", "brand_category"],
      [[key("c", c), key("v", v), d, int(s), vw, lk, cm, int(bool(sp)), ev or "", bcat.get(b, "")] for c, v, d, s, vw, lk, cm, sp, ev, b in cur.fetchall()])

cur = fresh()
cur.execute("""select creator_id::text, post_id, posted_at::date, media_type, like_count, comment_count, is_sponsored,
                      has_paid_partnership_label, sponsorship_evidence, brand_id::text
               from instagram_posts where creator_id is not null and posted_at is not null""")
write("instagram_posts.csv", ["creator_key", "post_key", "posted_date", "media_type", "likes", "comments", "is_sponsored",
                              "paid_partnership_label", "sponsorship_evidence", "brand_category"],
      [[key("c", c), key("p", p), d, mt or "", lk, cm, int(bool(sp)), int(bool(pl)), ev or "", bcat.get(b, "")]
       for c, p, d, mt, lk, cm, sp, pl, ev, b in cur.fetchall()])

# edges: listed related accounts that are held creators (collaborates_with); creators discussed in the same Reddit post (co_occurs_with)
cur = fresh()
cur.execute("select creator_id::text, lower(handle) from creator_related_accounts")
collab = Counter()
for a, h in cur.fetchall():
    b = h2c.get((h or "").lstrip("@"))
    if b and b != a:
        collab[tuple(sorted((a, b)))] += 1
cur = fresh()
cur.execute("select post_id, creator_id::text from reddit_post_creators")
by_post = {}
for p, c in cur.fetchall():
    by_post.setdefault(p, set()).add(c)
cooc = Counter(pair for cs in by_post.values() for pair in combinations(sorted(cs), 2))
write("edges.csv", ["creator_key_a", "creator_key_b", "relation", "weight"],
      [[key("c", a), key("c", b), "collaborates_with", n] for (a, b), n in collab.items()]
      + [[key("c", a), key("c", b), "co_occurs_with", n] for (a, b), n in cooc.items()])

tags = json.load(open(ROOT / "models" / "audience_flow_events_rep_9nov.json"))
write("tag_events.csv", ["tagger_key", "tagged_key", "tag_date"], [[key("c", a), key("c", b), t[:10]] for a, b, t in tags])
print("->", OUT)
