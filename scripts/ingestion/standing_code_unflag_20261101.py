"""One-off (1 Nov 2026): stop counting STANDING affiliate codes as sponsored posts. Backs up first, undoable.

    python standing_code_unflag_20261101.py               # report only (changes nothing)
    python standing_code_unflag_20261101.py --apply       # unflag them
    python standing_code_unflag_20261101.py --undo        # put the backed-up values back

WHY. Some creators paste the same brand + promo-code block under every video (Sam Sulek: Gymshark code SAM10 on about half of his videos; Ankit Yadav: a list of supplement codes). The label rules read
'brand + code in the description' as a sponsored post, so every such video was counted as a sponsorship event. A standing deal is not a new sponsored post.

RULE (deliberately narrow). A video is un-flagged only when ALL of these hold:
  * its evidence is a weak description tier (brand_and_code or brand_mention): never an official label, spoken sponsor, disclosure tag or creator comment, which say 'this video is an ad';
  * every brand it matched was matched by 'name+code' in the description, and its TITLE names none of them (a brand named in the title is a per-video choice and is kept);
  * EITHER for every one of those brands, at least STANDING_SHARE of the creator's videos within +/-WINDOW_DAYS also carry that brand by name+code (and that window holds at least MIN_WINDOW videos),
    OR the video lists at least MIN_LIST_BRANDS different brands with codes: a list of discount codes, not one sponsored post.
A one-off sponsored video, or a short campaign, shows the brand in a few videos only, so it stays. The creator's own sponsored videos with a real label stay too.
Also removes the videos' rows from sponsorship_event_scores. The events view (creator_sponsorship_events) follows youtube_videos on its own.
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import get_connection  # noqa: E402

WINDOW_DAYS = 30
MIN_WINDOW = 6
STANDING_SHARE = 0.5
MIN_LIST_BRANDS = 3
WEAK = ("brand_and_code", "brand_mention")
MATCH = re.compile(r"^brand:(.+)\((name\+code|title\+code|name|title)\)$")


def parse(raw) -> list[tuple[str, str]]:
    """[(brand, kind)] from sponsorship_raw_matches; 'comment:' matches (creator comments) are returned with kind 'comment'."""
    out = []
    for m in raw or []:
        if m.startswith("comment:"):
            out.append((m, "comment"))
            continue
        g = MATCH.match(m)
        out.append((g.group(1), g.group(2)) if g else (m, "other"))
    return out


def find_standing(videos: list[dict]) -> set[str]:
    """videos: one creator's videos {id, t (days), sponsored, evidence, matches}. Returns the ids to un-flag."""
    videos = sorted(videos, key=lambda v: v["t"])
    desc_brands = [{b for b, k in parse(v["matches"]) if k == "name+code"} if v["sponsored"] and v["evidence"] in WEAK else set() for v in videos]
    out = set()
    lo = hi = 0
    for i, v in enumerate(videos):
        if not (v["sponsored"] and v["evidence"] in WEAK):
            continue
        kinds = parse(v["matches"])
        if not kinds or any(k != "name+code" for _, k in kinds):
            continue
        title = (v.get("title") or "").lower()
        if any(re.search(r"(?<!\w)" + re.escape(b.lower()) + r"(?!\w)", title) for b, _ in kinds):
            continue
        while videos[lo]["t"] < v["t"] - WINDOW_DAYS:
            lo += 1
        while hi < len(videos) and videos[hi]["t"] <= v["t"] + WINDOW_DAYS:
            hi += 1
        if len({b for b, _ in kinds}) >= MIN_LIST_BRANDS:
            out.add(v["id"])
            continue
        n = hi - lo
        if n < MIN_WINDOW:
            continue
        if all(sum(b in desc_brands[j] for j in range(lo, hi)) / n >= STANDING_SHARE for b, _ in kinds):
            out.add(v["id"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--undo", action="store_true")
    args = ap.parse_args()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""create table if not exists standing_code_backup_20261101 (video_id text primary key, old_is_sponsored boolean, old_evidence text, old_raw_matches jsonb, old_brand_id uuid,
                   backed_up_at timestamptz default now())""")
    cur.execute("""create table if not exists standing_code_scores_backup_20261101 (content_id text, platform text, p_ad double precision, model_version text, scored_at timestamptz,
                   primary key (content_id, platform))""")
    if args.undo:
        cur.execute("""update youtube_videos v set is_sponsored = b.old_is_sponsored, sponsorship_evidence = b.old_evidence, sponsorship_raw_matches = b.old_raw_matches, brand_id = b.old_brand_id
                       from standing_code_backup_20261101 b where b.video_id = v.video_id""")
        n = cur.rowcount
        cur.execute("""insert into sponsorship_event_scores (content_id, platform, p_ad, model_version, scored_at)
                       select content_id, platform, p_ad, model_version, scored_at from standing_code_scores_backup_20261101 on conflict do nothing""")
        conn.commit()
        print(f"undone: {n} videos restored")
        return 0

    cur.execute("""select v.creator_id::text, cr.name, v.video_id, extract(epoch from v.published_at)/86400.0, coalesce(v.is_sponsored, false), v.sponsorship_evidence, v.sponsorship_raw_matches, v.title
                   from youtube_videos v join creators cr on cr.creator_id = v.creator_id where v.published_at is not null""")
    per, names = defaultdict(list), {}
    for cid, name, vid, t, sp, ev, raw, title in cur.fetchall():
        per[cid].append({"id": vid, "t": float(t), "sponsored": sp, "evidence": ev, "matches": raw, "title": title})
        names[cid] = name
    chosen, by_creator = set(), {}
    for cid, vs in per.items():
        s = find_standing(vs)
        if s:
            chosen |= s
            by_creator[cid] = (len(s), sum(v["sponsored"] for v in vs), len(vs))
    print(f"standing-code videos found: {len(chosen)} in {len(by_creator)} creators")
    for cid, (n, spons, tot) in sorted(by_creator.items(), key=lambda kv: -kv[1][0])[:25]:
        print(f"  {names[cid][:34]:34s} unflag {n:4d} of {spons:4d} sponsored ({tot} videos)")
    if not args.apply:
        print("report only; nothing changed. Run with --apply to unflag.")
        return 0
    ids = sorted(chosen)
    cur.execute("""insert into standing_code_backup_20261101 (video_id, old_is_sponsored, old_evidence, old_raw_matches, old_brand_id)
                   select video_id, is_sponsored, sponsorship_evidence, sponsorship_raw_matches, brand_id from youtube_videos where video_id = any(%s) on conflict do nothing""", (ids,))
    cur.execute("""insert into standing_code_scores_backup_20261101 (content_id, platform, p_ad, model_version, scored_at)
                   select content_id, platform, p_ad, model_version, scored_at from sponsorship_event_scores where platform = 'youtube' and content_id = any(%s) on conflict do nothing""", (ids,))
    cur.execute("update youtube_videos set is_sponsored = false, sponsorship_evidence = null where video_id = any(%s) and is_sponsored is true", (ids,))
    changed = cur.rowcount
    cur.execute("delete from sponsorship_event_scores where platform = 'youtube' and content_id = any(%s)", (ids,))
    conn.commit()
    print(f"videos unflagged: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
