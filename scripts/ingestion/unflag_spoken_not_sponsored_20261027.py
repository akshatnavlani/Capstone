"""One-off (27 Oct 2026): mark the 17 spoken-scan labels that only carry a bare Hindi/English word (sponsor, promotion) as NOT sponsored. Backs up first. NEEDS Shimona's yes.

    python unflag_spoken_not_sponsored_20261027.py            # applies it
    python unflag_spoken_not_sponsored_20261027.py --undo     # puts the backed-up values back

The captions of all 17 were read in context on 27 Oct (scripts/ingestion/spoken_context.py): in every video the word is a denial ("not sponsored", "not a paid promotion"), a remark about sponsors
in general or in the past, or means something else (self-promotion, promotional shoot). The 28 labels where the creator says a brand and a code aloud are NOT touched.
Also: spoken_scan.verdict becomes 'no', the rows are recorded in sponsorship_review (not_sponsored), and the events are removed from sponsorship_event_scores.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import get_connection  # noqa: E402

IDS = ['GVuN6WpF1XY', 'PaaOTbsRCT8', 'XvfQjjIsg4o', 'F9ntAE9xo38', 'Oy8Dla0s60s', 'b42TyjKRvbs', 'gdZS78eogqY', 'JkhbYC4ZyCw', 'jyurKN_XPY8', 'Yhs2Sjv_FX8', 'ReP5JYFH3u4', 'KTt60TobfQE', 'hLujiPT5bro', 'gyR7ZvDAEgk', 'zVvK86IsJPQ', 'tJwO1VhBPTg', 'ZvIg68nbiKA']
REVIEWER = "Shimona (said yes to Claude's reading of the captions 27 Oct; not checked one by one)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--undo", action="store_true")
    args = ap.parse_args()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""create table if not exists sponsor_flip_backup_20261027 (video_id text primary key, old_is_sponsored boolean, old_evidence text, old_raw_matches jsonb, old_brand_id uuid,
                   backed_up_at timestamptz default now())""")
    if args.undo:
        cur.execute("""update youtube_videos v set is_sponsored = b.old_is_sponsored, sponsorship_evidence = b.old_evidence, sponsorship_raw_matches = b.old_raw_matches, brand_id = b.old_brand_id
                       from sponsor_flip_backup_20261027 b where b.video_id = v.video_id and v.video_id = any(%s)""", (IDS,))
        cur.execute("update spoken_scan set verdict = 'yes' where video_id = any(%s)", (IDS,))
        cur.execute("delete from sponsorship_review where platform = 'youtube' and content_id = any(%s) and reviewer = %s", (IDS, REVIEWER))
        conn.commit()
        print("undone")
        return 0
    cur.execute("""insert into sponsor_flip_backup_20261027 (video_id, old_is_sponsored, old_evidence, old_raw_matches, old_brand_id)
                   select video_id, is_sponsored, sponsorship_evidence, sponsorship_raw_matches, brand_id from youtube_videos where video_id = any(%s) on conflict do nothing""", (IDS,))
    cur.execute("update youtube_videos set is_sponsored = false, sponsorship_evidence = null where video_id = any(%s) and is_sponsored is true", (IDS,))
    changed = cur.rowcount
    cur.execute("update spoken_scan set verdict = 'no', reviewer = %s, reviewed_at = now() where video_id = any(%s)", (REVIEWER, IDS))
    cur.execute("""insert into sponsorship_review (batch, position, sample_kind, platform, content_id, creator_id, creator_name, title, snippet, evidence, detected_sponsored, link, verdict, reviewer, reviewed_at)
                   select 13, row_number() over (order by v.video_id), 'flagged', 'youtube', v.video_id, v.creator_id, c.name, v.title, 'spoken hit read in context: not a sponsorship', v.sponsorship_raw_matches, true,
                          'https://www.youtube.com/watch?v=' || v.video_id, 'not_sponsored', %s, now()
                     from youtube_videos v left join creators c on c.creator_id = v.creator_id where v.video_id = any(%s)
                   on conflict (platform, content_id) do update set verdict = 'not_sponsored', reviewer = excluded.reviewer, reviewed_at = now()""", (REVIEWER, IDS))
    cur.execute("delete from sponsorship_event_scores where platform = 'youtube' and content_id = any(%s)", (IDS,))
    conn.commit()
    cur.execute("select count(*) from creator_sponsorship_events where content_id = any(%s)", (IDS,))
    print(f"videos unflagged: {changed}; still events afterwards: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
