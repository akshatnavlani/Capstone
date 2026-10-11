"""Check the collected data against the targets we set. READ ONLY.

    python scripts\\validate_collection.py

Prints each check as PASS or FAIL against its target, so a collection stage can be accepted or
sent back. The targets are proposals from the data plan (exact time on 95% of posts and so on), not
proven thresholds; change TARGETS below if the team agrees on different ones.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (label, target, unit) -- percentages are 0-100, counts are plain numbers
TARGETS = {
    "ig_exact_time": 95, "ig_caption": 90, "ig_image": 90, "yt_duration": 95,
    "ig_comment_time": 90, "reddit_comment_time": 90,
    "creators_deep_on_both": 100,      # >= 20 posts on each platform
    "total_posts": 20000,
    "sponsored_with_brand": 150,
    "posts_with_3_snapshots": 500,
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    from sqlalchemy import create_engine, text

    results: list[tuple[str, str, float, float, bool]] = []

    def pct(label, key, num, den):
        v = 100 * num / den if den else 0.0
        results.append((label, f"{num:,} of {den:,}", v, TARGETS[key], v >= TARGETS[key]))

    def count(label, key, n):
        results.append((label, f"{n:,}", float(n), TARGETS[key], n >= TARGETS[key]))

    with create_engine(url).connect() as c:
        c.execute(text("set transaction read only"))
        one = lambda sql: c.execute(text(sql)).one()  # noqa: E731
        scalar = lambda sql: c.execute(text(sql)).scalar()  # noqa: E731

        ig = one("""select count(*),
                           count(*) filter (where (posted_at at time zone 'UTC')::time <> time '00:00'),
                           count(caption), count(thumbnail_url) from instagram_posts""")
        pct("Instagram posts with an exact time of day", "ig_exact_time", ig[1], ig[0])
        pct("Instagram posts with a caption", "ig_caption", ig[2], ig[0])
        pct("Instagram posts with an image link", "ig_image", ig[3], ig[0])

        yt = one("select count(*), count(duration_seconds) from youtube_videos")
        pct("YouTube videos with a length", "yt_duration", yt[1], yt[0])

        ic = one("select count(posted_at), count(*) from instagram_comments")
        pct("Instagram comments with a time", "ig_comment_time", ic[0], ic[1])
        rc = one("select count(posted_at), count(*) from reddit_comments")
        pct("Reddit comments with a time", "reddit_comment_time", rc[0], rc[1])

        deep = scalar("""select count(*) from (
                           select creator_id from instagram_posts where creator_id is not null group by 1 having count(*) >= 20
                           intersect
                           select creator_id from youtube_videos group by 1 having count(*) >= 20) x""")
        count("Creators with 20+ posts on BOTH Instagram and YouTube", "creators_deep_on_both", deep)

        reddit_posts = scalar("select count(*) from reddit_posts")
        count("Total posts (YouTube + Instagram + Reddit)", "total_posts", yt[0] + ig[0] + reddit_posts)

        sponsored = scalar("""select count(*) from instagram_posts
                              where brand_id is not null and (is_sponsored or has_paid_partnership_label)""")
        count("Sponsored Instagram posts with a brand (NOT hand-verified)", "sponsored_with_brand", sponsored)

        have_snap = scalar("select to_regclass('public.post_snapshots') is not null")
        if have_snap:
            multi = scalar("select count(*) from (select 1 from post_snapshots group by platform, post_id having count(*) >= 3) x")
            count("Posts with 3 or more snapshots (growth curves)", "posts_with_3_snapshots", multi)
        else:
            results.append(("Snapshot tables exist", "missing: apply 20261009000000_snapshots.sql", 0.0, 1.0, False))

        span = one("select min(posted_at), max(posted_at) from instagram_posts")
        yspan = one("select min(published_at), max(published_at) from youtube_videos")

    width = max(len(r[0]) for r in results)
    print(f"{'CHECK':{width}s}  {'FOUND':>26s}  {'VALUE':>9s}  {'TARGET':>8s}  RESULT")
    for label, found, value, target, ok in results:
        print(f"{label:{width}s}  {found:>26s}  {value:>9,.1f}  {target:>8,.0f}  {'PASS' if ok else 'FAIL'}")
    print(f"\nInstagram posts span {span[0]} to {span[1]}")
    print(f"YouTube videos span  {yspan[0]} to {yspan[1]}")
    failed = sum(1 for r in results if not r[4])
    print(f"\n{len(results) - failed} passed, {failed} failed")


if __name__ == "__main__":
    main()
