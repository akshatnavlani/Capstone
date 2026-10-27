"""Turn approved spoken-sponsor hits into sponsorship labels (evidence type 'spoken'). Never flips true -> false; backs up each changed row.

    python apply_spoken_verdicts.py --videos ID1 ID2 ... --reviewer "Shimona (said yes to Claude's reading, 27 Oct)"
    python apply_spoken_verdicts.py --from-verdict yes            # every spoken_scan row whose verdict is 'yes' (the 24 Oct way)

A hit is only a candidate until a person approves it. --videos writes the approval into spoken_scan.verdict ('yes') with the reviewer text, then labels the video:
is_sponsored = true, sponsorship_evidence = 'spoken', and the brand when exactly one brand was heard. Safe to re-run (rows already sponsored are skipped).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import get_connection  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", nargs="*")
    ap.add_argument("--reviewer", default="Shimona")
    ap.add_argument("--from-verdict")
    args = ap.parse_args()
    if not args.videos and not args.from_verdict:
        ap.error("give --videos or --from-verdict")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""create table if not exists youtube_videos_sponsor_backup_20261012 (video_id text primary key, old_is_sponsored boolean,
                   old_raw jsonb, old_brand_id uuid, backed_up_at timestamptz default now())""")
    if args.videos:
        cur.execute("update spoken_scan set verdict = 'yes', reviewer = %s, reviewed_at = now() where video_id = any(%s) and jsonb_array_length(evidence) > 0", (args.reviewer, args.videos))
        print("approved in spoken_scan:", cur.rowcount)
    cur.execute("select lower(name), brand_id from brands")
    by_name = dict(cur.fetchall())
    cur.execute("select verification_id, creator_id from creator_verification where creator_id is not null")
    ver = {c: v for v, c in cur.fetchall()}
    where, params = ("s.video_id = any(%s)", (args.videos,)) if args.videos else ("s.verdict = %s", (args.from_verdict,))
    cur.execute(f"select s.video_id, s.evidence, v.creator_id, v.is_sponsored from spoken_scan s join youtube_videos v on v.video_id = s.video_id where {where}", params)
    labelled = already = links = 0
    for vid, evidence, cid, is_sp in cur.fetchall():
        brands = sorted({m.group(1) for e in evidence for m in [re.match(r"spoken:brand:(.+?)\(", e)] if m})
        ids = [by_name[b.lower()] for b in brands if b.lower() in by_name]
        if is_sp:
            already += 1
        else:
            cur.execute("insert into youtube_videos_sponsor_backup_20261012 (video_id, old_is_sponsored, old_raw, old_brand_id) select video_id, is_sponsored, sponsorship_raw_matches, brand_id from youtube_videos where video_id = %s on conflict do nothing", (vid,))
            cur.execute("""update youtube_videos set is_sponsored = true, sponsorship_raw_matches = %s::jsonb, sponsorship_evidence = 'spoken', brand_id = coalesce(%s, brand_id)
                           where video_id = %s and is_sponsored is not true""", (json.dumps(evidence + [f"review:yes({args.reviewer})"]), ids[0] if len(ids) == 1 else None, vid))
            labelled += cur.rowcount
        if ver.get(cid):
            for b, bid in zip(brands, ids):
                cur.execute("""insert into creator_brand_links (verification_id, creator_id, brand_id, platform, evidence, source)
                               values (%s, %s, %s, 'youtube', %s, 'spoken sponsor, approved') on conflict (verification_id, brand_id) do nothing""", (ver[cid], cid, bid, f"{b}: heard in the captions, approved by {args.reviewer}"))
                links += cur.rowcount
    conn.commit()
    print(f"newly labelled: {labelled} | already sponsored: {already} | new creator-brand links: {links}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
