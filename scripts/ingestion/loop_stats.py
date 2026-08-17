"""Per-platform ATTEMPT coverage across all creators — the loop's progress metric.

Deliberately measures ATTEMPTED, not SUCCEEDED. A creator that was tried and returned
nothing (dead handle, no channel, blocked) is covered; one never tried is not. Conflating
the two is what let the YouTube/Reddit gap sit unnoticed while headline counts grew.

Sources of truth per platform, and why:
  Instagram : an instagram_posts row OR an instagram_profiles row carrying our creator_id.
              Either proves a real fetch was made against that creator.
  YouTube   : presence in yt_discovery_checkpoint.json (found / needs_review /
              no_confident_match / no_channel_found / handle_clash all count as attempted),
              OR already having a youtube_handle (the pre-existing seeded set).
  Reddit    : a reddit_post_creators row = search actually ran and matched. Having topic
              subs configured but no rows means it ran and found nothing -- also attempted.
              Everything else splits into NAME-GATED (name == instagram_handle, so the
              topic-sub search would query a handle and return 0 by construction) versus
              genuinely untouched.

Run: python loop_stats.py [--json]
"""

import json
import os
import sys

import psycopg2

from orchestrator import ENV

CKPT = os.path.join(os.path.dirname(__file__), "yt_discovery_checkpoint.json")


def main() -> None:
    conn = psycopg2.connect(ENV["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute("select count(*) from creators")
    total = cur.fetchone()[0]

    # --- Instagram: attempted = we have posts or a profile row tied to this creator
    cur.execute("""
        select count(*) from creators c where exists (
            select 1 from instagram_posts p where p.creator_id = c.creator_id
        ) or exists (
            select 1 from instagram_profiles ip where ip.creator_id = c.creator_id
        )""")
    ig_attempted = cur.fetchone()[0]
    cur.execute("select count(distinct creator_id) from instagram_posts")
    ig_with_content = cur.fetchone()[0]

    # --- YouTube: attempted = in the discovery checkpoint, or already had a handle
    ckpt = {}
    if os.path.exists(CKPT):
        with open(CKPT, encoding="utf-8") as f:
            ckpt = json.load(f)
    cur.execute("select creator_id::text, youtube_handle from creators")
    rows = cur.fetchall()
    yt_attempted = sum(1 for cid, h in rows if cid in ckpt or h)
    yt_with_handle = sum(1 for _, h in rows if h)
    cur.execute("select count(distinct creator_id) from youtube_videos")
    yt_with_videos = cur.fetchone()[0]

    # --- Reddit: attempted vs name-gated vs untouched
    cur.execute("""
        select count(*) from creators c where exists (
            select 1 from reddit_post_creators r where r.creator_id = c.creator_id
        ) or coalesce(array_length(c.reddit_topic_subs,1),0) > 0
          or coalesce(array_length(c.reddit_handles,1),0) > 0""")
    rd_attempted = cur.fetchone()[0]
    cur.execute("select count(distinct creator_id) from reddit_post_creators")
    rd_with_content = cur.fetchone()[0]
    cur.execute("""
        select count(*) from creators c
        where lower(c.name) = lower(c.instagram_handle)
          and not exists (select 1 from reddit_post_creators r where r.creator_id = c.creator_id)
          and coalesce(array_length(c.reddit_topic_subs,1),0) = 0
          and coalesce(array_length(c.reddit_handles,1),0) = 0""")
    rd_name_gated = cur.fetchone()[0]
    rd_untouched = total - rd_attempted - rd_name_gated

    # --- the actual objective
    cur.execute("""
        with events as (
            -- Events must be counted on EVERY platform, not just Instagram. Kerala Blasters'
            -- 2 sponsorship events live on YouTube ("brought to you by"), and an
            -- Instagram-only event query silently excluded them -- the same cross-platform
            -- blind spot already fixed on the NEIGHBOUR side of this calculation.
            select creator_id, post_id, posted_at from instagram_posts
            where (is_sponsored or has_paid_partnership_label) and posted_at is not null
            union all
            select creator_id, video_id, published_at from youtube_videos
            where is_sponsored and published_at is not null
            union all
            select creator_id, post_id, posted_at from reddit_posts
            where is_sponsored and posted_at is not null),
        pairs as (select distinct x.creator_id a, c2.creator_id b
                  from creator_related_accounts x
                  join creators c2 on lower(c2.instagram_handle)=lower(x.handle)
                                   and c2.creator_id<>x.creator_id)
        select count(*) from (
          select 1 from events e join pairs pr on pr.a = e.creator_id
          where (select count(*) from instagram_posts q where q.creator_id=pr.b and q.posted_at<e.posted_at)
               +(select count(*) from youtube_videos v where v.creator_id=pr.b and v.published_at<e.posted_at)
               +(select count(*) from reddit_posts r where r.creator_id=pr.b and r.posted_at<e.posted_at) > 0
            and (select count(*) from instagram_posts q where q.creator_id=pr.b and q.posted_at>e.posted_at)
               +(select count(*) from youtube_videos v where v.creator_id=pr.b and v.published_at>e.posted_at)
               +(select count(*) from reddit_posts r where r.creator_id=pr.b and r.posted_at>e.posted_at) > 0
        ) t""")
    pairs = cur.fetchone()[0]
    cur.execute("""select count(*) from (
        select distinct least(a.name,c.name), greatest(a.name,c.name)
        from creator_related_accounts x
        join creators a on a.creator_id=x.creator_id
        join creators c on lower(c.instagram_handle)=lower(x.handle) and c.creator_id<>x.creator_id) t""")
    edge_pairs = cur.fetchone()[0]
    conn.close()

    pct = lambda n: f"{100*n/total:5.1f}%"
    stats = {
        "creators": total,
        "ig_attempted": ig_attempted, "ig_with_content": ig_with_content,
        "yt_attempted": yt_attempted, "yt_with_handle": yt_with_handle,
        "yt_with_videos": yt_with_videos,
        "rd_attempted": rd_attempted, "rd_with_content": rd_with_content,
        "rd_name_gated": rd_name_gated, "rd_untouched": rd_untouched,
        "computable_pairs": pairs, "collab_edge_pairs": edge_pairs,
    }
    if "--json" in sys.argv:
        print(json.dumps(stats))
        return

    print(f"creators: {total}\n")
    print(f"INSTAGRAM  attempted        {ig_attempted:>4}/{total}  {pct(ig_attempted)}")
    print(f"           with content     {ig_with_content:>4}/{total}  {pct(ig_with_content)}")
    print(f"YOUTUBE    attempted        {yt_attempted:>4}/{total}  {pct(yt_attempted)}")
    print(f"           with handle      {yt_with_handle:>4}/{total}  {pct(yt_with_handle)}")
    if yt_with_handle:
        print(f"           of those, deepened {yt_with_videos:>2}/{yt_with_handle}  "
               f"{100*yt_with_videos/yt_with_handle:5.1f}%")
    print(f"REDDIT     attempted        {rd_attempted:>4}/{total}  {pct(rd_attempted)}")
    print(f"           with content     {rd_with_content:>4}/{total}  {pct(rd_with_content)}")
    print(f"           NAME-GATED       {rd_name_gated:>4}/{total}  {pct(rd_name_gated)}  "
           f"(precondition failure, not a search failure)")
    print(f"           untouched        {rd_untouched:>4}/{total}  {pct(rd_untouched)}")
    print(f"\nCOMPUTABLE TRAINING PAIRS  {pairs}   (target >= 20)")
    print(f"collaboration edge pairs   {edge_pairs}")


if __name__ == "__main__":
    main()
