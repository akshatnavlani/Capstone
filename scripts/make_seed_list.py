"""Build a collection seed list from the creators already in the database. READ ONLY.

    python scripts\\make_seed_list.py                     # both-platform creators with a confirmed/probable link
    python scripts\\make_seed_list.py --include-review    # also the links a person has not yet checked
    python scripts\\make_seed_list.py --instagram-only    # also creators that only have an Instagram handle
    python scripts\\make_seed_list.py --out my_list.json

Writes JSON in the same shape as scripts/ingestion/target_list.json, so it can be passed to
orchestrator.py --target-list. Names are copied exactly from `creators.name`, because the
orchestrator looks a creator up by name: that is what makes a re-run attach to the SAME creator_id
instead of minting a duplicate.

A YouTube <-> Instagram pair is only included when ml/link_evidence.py rates the link
"confirmed" or "probable" (a handle in the channel description, a bio that points at the channel,
or a matching name with a plausible audience size). Everything else needs a person to look first.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "scripts" / "ingestion" / "seed_list.json"
ACCEPT = {"confirmed", "probable"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-review", action="store_true", help="also include links rated 'review'")
    ap.add_argument("--instagram-only", action="store_true", help="also include creators with only an Instagram handle")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    from sqlalchemy import create_engine, text

    from ml.link_evidence import score_link

    with create_engine(url).connect() as c:
        c.execute(text("set transaction read only"))
        rows = c.execute(text("""
            select cr.name, cr.category, cr.instagram_handle, cr.youtube_handle,
                   coalesce(cr.reddit_handles, '{}'), coalesce(cr.reddit_topic_subs, '{}'),
                   ip.username, ip.full_name, ip.bio, ip.follower_count,
                   yc.channel_handle, yc.title, yc.description, yc.subscriber_count
            from creators cr
            left join lateral (select * from instagram_profiles p where p.creator_id = cr.creator_id
                               order by follower_count desc nulls last limit 1) ip on true
            left join lateral (select * from youtube_channels y where y.creator_id = cr.creator_id
                               order by subscriber_count desc nulls last limit 1) yc on true
            order by cr.name""")).all()

    seed, counts = [], collections.Counter()
    for (name, category, ig_h, yt_h, reddit, topics, ig_user, ig_full, ig_bio, ig_fol,
         yt_chan, yt_title, yt_desc, yt_subs) in rows:
        ig_handle = (ig_h or ig_user or "").lstrip("@") or None
        yt_handle = yt_h or yt_chan
        entry = {"name": name, "category": category or "other", "reddit_handles": list(reddit),
                 "reddit_topic_subs": list(topics)}
        if ig_handle and yt_handle and yt_chan:
            level = score_link(name, ig_user or ig_handle, ig_full, ig_bio, ig_fol, yt_chan, yt_title, yt_desc, yt_subs)["level"]
            counts[f"both: {level}"] += 1
            if level not in ACCEPT and not args.include_review:
                continue
            entry.update(instagram_handle=ig_handle, youtube_handle=yt_handle, link_level=level)
        elif ig_handle and args.instagram_only:
            counts["instagram only"] += 1
            entry.update(instagram_handle=ig_handle)
        else:
            counts["skipped (no usable handles)" if not (ig_handle or yt_handle) else "skipped (one platform, not requested)"] += 1
            continue
        seed.append(entry)

    Path(args.out).write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rows)} creators in the database")
    for k, v in sorted(counts.items()):
        print(f"   {k:42s} {v:4d}")
    print(f"\nwrote {len(seed)} creators to {args.out}")


if __name__ == "__main__":
    main()
