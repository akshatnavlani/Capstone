"""Draft the creator list we will collect data for. READ ONLY on the database.

    python scripts\\build_creator_list.py
    python scripts\\build_creator_list.py --include-adjacent    # also athletes / lifestyle creators with fitness signals
    python scripts\\build_creator_list.py --out-dir some\\folder

Every creator already has ONE unique id, `creators.creator_id` (a UUID). Every platform table
(youtube_channels, youtube_videos, instagram_profiles, instagram_posts, reddit_post_creators)
carries that id, so a YouTube video and an Instagram post by the same person are joined on it. The
accounts themselves are identified by `youtube_channels.channel_id` and `instagram_profiles.username`.

Writes into scripts/ingestion/creator_list/:
  creator_list_draft.csv     every creator with the signals below and why they are in or out
  seed_list.json             the chosen creators, in the shape orchestrator.py --target-list reads
  youtube_lookup_todo.csv    Instagram-only fitness creators whose YouTube channel is still to be found

Groups (for the creators that pass the filters):
  A  on both platforms, link confirmed/probable, with sponsorship activity   -> cross-platform + GAIL labels
  B  on both platforms, link confirmed/probable, no sponsorship seen          -> comparison creators
  R  on both platforms, link NOT yet verified                                  -> a person must check
  C  Instagram only                                                            -> single-platform parts; YouTube lookup pending
Tiers: core = fitness creator; adjacent = athlete/lifestyle creator whose bio has fitness words.
Excluded: brands, teams, leagues, institutions, unclassified accounts.

NOTHING here is a live reachability test: no YouTube key and no OpenCLI on this machine. "reachable"
below only means "we already hold collected rows for this account".
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))

MIN_POSTS = 20  # per platform, for a creator to be "deep" already

_INDIC = re.compile("[ऀ-෿]")
_INDIA_WORDS = re.compile(r"\b(india|indian|bharat|hindustan|desi)\b|\+91|🇮🇳|\.in\b", re.I)
_INDIAN_CITIES = re.compile(
    r"\b(mumbai|delhi|new delhi|bengaluru|bangalore|hyderabad|chennai|kolkata|pune|ahmedabad|jaipur|"
    r"chandigarh|lucknow|gurgaon|gurugram|noida|kochi|indore|bhopal|surat|goa)\b", re.I)
_INDIAN_SUB = re.compile(r"india", re.I)

SQL = """
with ig as (
  select creator_id, count(*) n, max(posted_at) last_at,
         count(*) filter (where (posted_at at time zone 'UTC')::time <> time '00:00') exact,
         count(*) filter (where brand_id is not null or coalesce(is_sponsored, false)
                            or coalesce(has_paid_partnership_label, false)) sponsored
  from instagram_posts where creator_id is not null group by 1),
yt as (
  select creator_id, count(*) n, max(published_at) last_at,
         count(*) filter (where brand_id is not null) sponsored
  from youtube_videos group by 1),
rd as (select creator_id, count(*) n from reddit_post_creators group by 1)
select cr.creator_id::text, cr.name, cr.category, cr.instagram_handle, cr.youtube_handle,
       coalesce(cr.reddit_handles, '{}'), coalesce(cr.reddit_topic_subs, '{}'),
       ip.username, ip.full_name, ip.bio, ip.follower_count,
       yc.channel_id, yc.channel_handle, yc.title, yc.description, yc.subscriber_count, yc.country,
       coalesce(ig.n, 0), ig.last_at, coalesce(ig.exact, 0), coalesce(ig.sponsored, 0),
       coalesce(yt.n, 0), yt.last_at, coalesce(yt.sponsored, 0), coalesce(rd.n, 0)
from creators cr
left join lateral (select * from instagram_profiles p where p.creator_id = cr.creator_id
                   order by follower_count desc nulls last limit 1) ip on true
left join lateral (select * from youtube_channels y where y.creator_id = cr.creator_id
                   order by subscriber_count desc nulls last limit 1) yc on true
left join ig on ig.creator_id = cr.creator_id
left join yt on yt.creator_id = cr.creator_id
left join rd on rd.creator_id = cr.creator_id
order by cr.name
"""


def indian_signals(bio, full_name, yt_country, topic_subs, yt_desc):
    """Evidence list. An empty list means 'no evidence', NOT 'not Indian'."""
    text = f"{bio or ''} {full_name or ''}"
    found = []
    if yt_country == "IN":
        found.append("YouTube channel country is IN")
    if _INDIC.search(text) or _INDIC.search(yt_desc or ""):
        found.append("Indic script in bio or channel description")
    if _INDIA_WORDS.search(text) or _INDIA_WORDS.search(yt_desc or ""):
        found.append("India marker in bio or channel description")
    if _INDIAN_CITIES.search(text) or _INDIAN_CITIES.search(yt_desc or ""):
        found.append("Indian city in bio or channel description")
    if any(_INDIAN_SUB.search(s) for s in topic_subs):
        found.append("assigned to an India-related subreddit")
    return found


def indian_level(signals: list[str]) -> str:
    if "YouTube channel country is IN" in signals or len(signals) >= 2:
        return "high"
    return "medium" if signals else "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-adjacent", action="store_true")
    ap.add_argument("--out-dir", default=None,
                    help="write CSV/JSON copies here. Off by default: the data lives in Supabase, "
                         "so by default this only prints a summary.")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    env = (ROOT / "backend" / ".env").read_text(encoding="utf-8")
    url = os.environ.get("DATABASE_URL") or re.search(r"^DATABASE_URL=(.+)$", env, re.M).group(1).strip().strip('"')
    from sqlalchemy import create_engine, text

    from account_classify import BRAND, _FITNESS, classify_from_profile
    from ml.link_evidence import score_link

    with create_engine(url).connect() as c:
        c.execute(text("set transaction read only"))
        rows = c.execute(text(SQL)).all()
        known_orgs = {(h or "").lower().lstrip("@") for (h,) in c.execute(text(
            "select instagram_handle from creators where category in ('team', 'league') and instagram_handle is not null"))}

    records = []
    for (cid, name, category, ig_h, yt_h, reddit, topics, ig_user, ig_full, ig_bio, ig_fol,
         yt_chan, yt_chan_handle, yt_title, yt_desc, yt_subs, yt_country,
         ig_n, ig_last, ig_exact, ig_spons, yt_n, yt_last, yt_spons, rd_n) in rows:
        ig_handle = (ig_h or ig_user or "").lstrip("@") or None
        yt_handle = yt_h or yt_chan_handle
        has_ig, has_yt = bool(ig_handle), bool(yt_chan)

        guess, why = classify_from_profile(ig_full or name, ig_bio or "", ig_handle or "", known_orgs)
        if guess == BRAND:
            tier, tier_why = "excluded", f"classifier: {why}"
        elif category == "fitness_influencer" and guess not in ("team", "league"):
            tier, tier_why = "core", "category is fitness_influencer"
        elif category in ("athlete", "lifestyle_influencer") and _FITNESS.search(f"{ig_bio or ''} {name}"):
            tier, tier_why = "adjacent", f"{category} with fitness words in the bio"
        else:
            tier, tier_why = "excluded", f"category {category}, no fitness signal"

        link = None
        if has_ig and has_yt:
            link = score_link(name, ig_user or ig_handle, ig_full, ig_bio, ig_fol, yt_chan_handle, yt_title, yt_desc, yt_subs)

        signals = indian_signals(ig_bio, ig_full, yt_country, topics, yt_desc)
        sponsored = ig_spons + yt_spons
        verified = link is not None and link["level"] in ("confirmed", "probable")
        if tier == "excluded":
            group = "X"
        elif has_ig and has_yt:
            group = ("A" if sponsored else "B") if verified else "R"
        elif has_ig:
            group = "C"
        else:
            group = "X"

        needs = []
        if group == "R":
            needs.append("YouTube-Instagram link must be checked by a person")
        if group == "C":
            needs.append("find the YouTube channel (see youtube_lookup_todo.csv)")
        if has_ig and ig_n < MIN_POSTS:
            needs.append(f"only {ig_n} Instagram posts stored")
        if has_yt and yt_n < MIN_POSTS:
            needs.append(f"only {yt_n} YouTube videos stored")
        if ig_n and ig_exact < ig_n:
            needs.append("Instagram times of day to be decoded")
        if not signals:
            needs.append("no Indian evidence found (not proof they are not Indian)")

        records.append(dict(
            creator_id=cid, name=name, category=category, tier=tier, tier_reason=tier_why, group=group,
            instagram_handle=ig_handle, youtube_handle=yt_handle, youtube_channel_id=yt_chan,
            link_level=(link or {}).get("level"), link_evidence="; ".join((link or {}).get("strong", []) + (link or {}).get("medium", [])),
            link_warnings="; ".join((link or {}).get("flags", [])),
            ig_followers=ig_fol, yt_subscribers=yt_subs,
            ig_posts=ig_n, ig_last_post=ig_last.date().isoformat() if ig_last else "", ig_exact_times=ig_exact,
            yt_videos=yt_n, yt_last_video=yt_last.date().isoformat() if yt_last else "",
            sponsored_posts=sponsored, reddit_mentions=rd_n,
            indian_level=indian_level(signals), indian_evidence="; ".join(signals),
            needs="; ".join(needs),
            _reddit=list(reddit), _topics=list(topics), _bio=(ig_bio or "")[:80],
        ))

    chosen = [r for r in records if r["group"] in ("A", "B", "R", "C") and (r["tier"] == "core" or (args.include_adjacent and r["tier"] == "adjacent"))]

    todo = [r for r in chosen if r["group"] == "C"]
    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        public = [k for k in records[0] if not k.startswith("_")]
        with open(out / "creator_list_draft.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=public, extrasaction="ignore")
            w.writeheader()
            w.writerows(records)

        seed = []
        for r in chosen:
            e = {"creator_id": r["creator_id"], "name": r["name"], "category": r["category"] or "other", "group": r["group"],
                 "tier": r["tier"], "reddit_handles": r["_reddit"], "reddit_topic_subs": r["_topics"]}
            if r["instagram_handle"]:
                e["instagram_handle"] = r["instagram_handle"]
            if r["youtube_handle"] and r["youtube_channel_id"]:
                e["youtube_handle"] = r["youtube_handle"]
            seed.append(e)
        (out / "seed_list.json").write_text(json.dumps(seed, indent=2, ensure_ascii=False), encoding="utf-8")

        with open(out / "youtube_lookup_todo.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["creator_id", "name", "instagram_handle", "ig_followers", "bio_start", "handle_to_try_on_youtube"])
            for r in todo:
                w.writerow([r["creator_id"], r["name"], r["instagram_handle"], r["ig_followers"], r["_bio"], r["instagram_handle"]])

    # ------------------------------------------------------------------ summary
    def table(title, keyfn, items, order=None):
        counts: dict = {}
        for r in items:
            counts[keyfn(r)] = counts.get(keyfn(r), 0) + 1
        print(title)
        for k in (order or sorted(counts)):
            print(f"   {str(k):12s} {counts.get(k, 0):4d}")

    print(f"{len(records)} creators in the database\n")
    table("By tier (fitness relevance):", lambda r: r["tier"], records, ["core", "adjacent", "excluded"])
    print()
    table(f"By group, {'core + adjacent' if args.include_adjacent else 'core only'}:", lambda r: r["group"], chosen, ["A", "B", "R", "C"])
    print("   A both+sponsored | B both+no sponsorship seen | R link needs a person | C Instagram only")
    print()
    table("Indian evidence among the chosen:", lambda r: r["indian_level"], chosen, ["high", "medium", "unknown"])
    deep = sum(1 for r in chosen if r["ig_posts"] >= MIN_POSTS and r["yt_videos"] >= MIN_POSTS)
    print(f"\nAlready deep (>= {MIN_POSTS} posts on BOTH platforms): {deep}")
    both = [r for r in chosen if r["group"] in ("A", "B")]
    print(f"Verified on both platforms (A + B): {len(both)}   target about 100-150")
    print(f"\n{len(chosen)} creators chosen, {len(todo)} of them need a YouTube channel found.")
    print("Nothing was written anywhere." if not args.out_dir else f"Local copies written to {args.out_dir}")


if __name__ == "__main__":
    main()
