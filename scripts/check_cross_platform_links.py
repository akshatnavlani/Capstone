"""Check every creator's YouTube <-> Instagram link for evidence. READ ONLY.

    python scripts\\check_cross_platform_links.py            # summary + the links a person must review
    python scripts\\check_cross_platform_links.py --all      # every link with its evidence
    python scripts\\check_cross_platform_links.py --csv links_to_review.csv

Uses ml/link_evidence.py. For NEW candidate links (after collecting more channels), load the candidate
into the same fields and call score_link: confirmed / probable can be accepted, review needs a person.
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--csv", help="write the links that need review to this CSV file")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    from sqlalchemy import create_engine, text

    from ml.link_evidence import score_link

    with create_engine(url).connect() as c:
        rows = c.execute(text("""
            select cr.name, cr.instagram_handle, ip.username, ip.full_name, ip.bio, ip.follower_count,
                   yc.channel_handle, yc.title, yc.description, yc.subscriber_count
            from creators cr
            join youtube_channels yc on yc.creator_id = cr.creator_id
            left join instagram_profiles ip on ip.creator_id = cr.creator_id
            order by cr.name""")).all()

    results = []
    for name, ig_handle, ig_user, ig_full, ig_bio, ig_fol, yh, yt_title, yt_desc, yt_subs in rows:
        r = score_link(name, ig_user or (ig_handle or "").lstrip("@"), ig_full, ig_bio, ig_fol, yh, yt_title, yt_desc, yt_subs)
        results.append((name, yh, yt_title, ig_fol, yt_subs, r))

    counts = collections.Counter(r["level"] for *_, r in results)
    print(f"{len(results)} creators have both a YouTube channel and an Instagram account linked")
    for lvl in ("confirmed", "probable", "review"):
        print(f"   {lvl:10s} {counts[lvl]:3d}  ({100 * counts[lvl] / max(1, len(results)):.0f}%)")
    print("   confirmed = a strong sign (handle in the description, bio points at the channel), no fan-page warning")
    print("   probable  = the name matches and the audience sizes are plausible; review = a person must look\n")

    show = results if args.all else [x for x in results if x[5]["level"] == "review"]
    print("ALL LINKS" if args.all else "LINKS THAT NEED A PERSON TO REVIEW")
    for name, yh, yt_title, ig_fol, yt_subs, r in show:
        why = "; ".join(r["strong"] + r["medium"] + [f"weak: {w}" for w in r["weak"]] + [f"WARNING: {f}" for f in r["flags"]]) or "no evidence found"
        print(f"  [{r['level']:9s}] {name[:28]:28s} yt:{(yh or '')[:22]:22s} '{(yt_title or '')[:30]}' ig={ig_fol} yt={yt_subs} | {why}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["creator", "youtube_handle", "youtube_title", "ig_followers", "yt_subscribers", "level", "evidence", "warnings"])
            for name, yh, yt_title, ig_fol, yt_subs, r in results:
                if r["level"] == "review":
                    w.writerow([name, yh, yt_title, ig_fol, yt_subs, r["level"], "; ".join(r["strong"] + r["medium"] + r["weak"]), "; ".join(r["flags"])])
        print(f"\nwrote {args.csv}")


if __name__ == "__main__":
    main()
