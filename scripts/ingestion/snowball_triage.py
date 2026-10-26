"""Snowball sampling, step 1 (READ ONLY): which listed collaborators of our creators could become new creators?

    python snowball_triage.py [--limit N] [--out models/snowball_candidates.json]

`creator_related_accounts` lists 790 distinct Instagram accounts as frequent collaborators of our creators; 623 are not in `creators`.
For each one this script asks the YouTube API for the channel with the SAME handle (channels.list forHandle = 1 quota unit) and keeps what the channel shows:
country, subscribers, title, description. A channel is only treated as the SAME PERSON when its DESCRIPTION carries the Instagram handle (the custom url is the handle itself, so it proves nothing)
(this project's rule since August: about 4 of 5 guessed handles pointed at fan or unrelated channels). Everything else is reported as unverified.
Fitness / India signals are keyword counts, shown so a person can decide; nothing is written to the database.
"""
import argparse
import json
import re
import sys
import urllib.error
from pathlib import Path

import psycopg2

from orchestrator import ENV, youtube_api_get

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
FITNESS = re.compile(r"\b(fitness|gym|workout|bodybuild\w*|muscle|protein|diet|nutrition|yoga|crossfit|trainer|coach|calisthenics|weight ?loss|health|transformation|athlete)\b", re.I)
INDIA = re.compile(r"\b(india|indian|hindi|mumbai|delhi|bangalore|bengaluru|hyderabad|chennai|pune|kolkata|desi)\b", re.I)
BRAND_LIKE = re.compile(r"(official|india$|sports|nutrition|store|shop|fitness$)", re.I)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "models" / "snowball_candidates.json"))
    args = ap.parse_args()
    cur = psycopg2.connect(ENV["DATABASE_URL"]).cursor()
    cur.execute("""
        select lower(r.handle), count(distinct r.creator_id), bool_or(r.creator_id in (select creator_id from creator_verification where link_level in ('confirmed','probable')))
          from creator_related_accounts r
         where lower(r.handle) not in (select lower(coalesce(instagram_handle, '')) from creators)
           and lower(r.handle) not in (select lower(coalesce(youtube_handle, '')) from creators)
         group by 1 order by 2 desc, 1""")
    handles = cur.fetchall()
    if args.limit:
        handles = handles[: args.limit]
    out, units = [], 0
    for i, (h, n_creators, listed_by_core) in enumerate(handles, 1):
        item = {"instagram_handle": h, "listed_by_creators": n_creators, "listed_by_core_150": bool(listed_by_core)}
        try:
            resp = youtube_api_get("channels", forHandle=h.lstrip("@"), part="snippet,statistics")
            units += 1
        except urllib.error.HTTPError as e:
            item["error"] = f"HTTP {e.code}"
            out.append(item)
            if e.code in (403, 429):
                print("stopping: quota or permission problem", e.code)
                break
            continue
        ch = (resp.get("items") or [None])[0]
        if ch:
            sn, st = ch["snippet"], ch.get("statistics", {})
            text = f"{sn.get('title', '')} {sn.get('description', '')}"
            item.update({"channel_id": ch["id"], "title": sn.get("title"), "country": sn.get("country"), "subscribers": int(st.get("subscriberCount", 0)),
                         "videos": int(st.get("videoCount", 0)), "fitness_words": len(FITNESS.findall(text)), "india_words": len(INDIA.findall(text)),
                         "same_person": h.lstrip("@") in sn.get("description", "").lower()})
        else:
            item["channel_id"] = None
        out.append(item)
        if i % 100 == 0:
            print(f"{i}/{len(handles)} checked, {units} quota units")
    found = [x for x in out if x.get("channel_id")]
    print(f"checked {len(out)}; channel with the same handle: {len(found)}; same person confirmed by description: {sum(1 for x in found if x['same_person'])}")
    strong = [x for x in found if x["same_person"] and x["fitness_words"] and (x["country"] == "IN" or x["india_words"])]
    print(f"confirmed + fitness words + India signal: {len(strong)}; quota units used: {units}")
    Path(args.out).write_text(json.dumps({"checked": len(out), "quota_units": units, "candidates": out}, indent=1), encoding="utf-8")
    print("saved", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
