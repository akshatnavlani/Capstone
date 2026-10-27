"""One-off (27 Oct 2026, Shimona said yes): mark two posts that only LOOK sponsored as not sponsored. Backs up first; records the decision in sponsorship_review.

    python unflag_two_posts_20261027.py            # applies it
    python unflag_two_posts_20261027.py --undo     # puts the backed-up values back

  youtube pcxTYVgflpc  Sanjay Duseja: the description says "(Not a paid promotion, just something I personally use and like.)"
  youtube tUkIMp4SMnE  Tanmay Bhat: title "Kohli's Best Paid Promotion", a joke video with no brand

The decision is also written to sponsorship_review (verdict not_sponsored, reviewer 'Shimona (said yes to Claude's recommendation 27 Oct; not checked one by one)') so a later label pass
can be told to leave them alone, and the two rows are removed from sponsorship_event_scores (they are no longer events). Nothing else changes.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import get_connection  # noqa: E402

IDS = [("pcxTYVgflpc", "Sanjay Duseja: says 'Not a paid promotion'"), ("tUkIMp4SMnE", "Tanmay Bhat: joke title 'Kohli's Best Paid Promotion'")]
REVIEWER = "Shimona (said yes to Claude's recommendation 27 Oct; not checked one by one)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--undo", action="store_true")
    args = ap.parse_args()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""create table if not exists sponsor_flip_backup_20261027 (video_id text primary key, old_is_sponsored boolean, old_evidence text, old_raw_matches jsonb, old_brand_id uuid,
                   backed_up_at timestamptz default now())""")
    ids = [i for i, _ in IDS]
    if args.undo:
        cur.execute("""update youtube_videos v set is_sponsored = b.old_is_sponsored, sponsorship_evidence = b.old_evidence, sponsorship_raw_matches = b.old_raw_matches, brand_id = b.old_brand_id
                       from sponsor_flip_backup_20261027 b where b.video_id = v.video_id""")
        cur.execute("delete from sponsorship_review where platform = 'youtube' and content_id = any(%s) and reviewer = %s", (ids, REVIEWER))
        conn.commit()
        print("undone")
        return 0
    cur.execute("""insert into sponsor_flip_backup_20261027 (video_id, old_is_sponsored, old_evidence, old_raw_matches, old_brand_id)
                   select video_id, is_sponsored, sponsorship_evidence, sponsorship_raw_matches, brand_id from youtube_videos where video_id = any(%s) on conflict do nothing""", (ids,))
    cur.execute("update youtube_videos set is_sponsored = false, sponsorship_evidence = null where video_id = any(%s) and is_sponsored is true", (ids,))
    changed = cur.rowcount
    for vid, why in IDS:
        cur.execute("""insert into sponsorship_review (batch, position, sample_kind, platform, content_id, creator_id, creator_name, title, snippet, evidence, detected_sponsored, link, verdict, reviewer, reviewed_at)
                       select 12, %s, 'flagged', 'youtube', v.video_id, v.creator_id, c.name, v.title, %s, v.sponsorship_raw_matches, true, 'https://www.youtube.com/watch?v=' || v.video_id, 'not_sponsored', %s, now()
                         from youtube_videos v left join creators c on c.creator_id = v.creator_id where v.video_id = %s
                       on conflict (platform, content_id) do update set verdict = 'not_sponsored', reviewer = excluded.reviewer, reviewed_at = now()""",
                    (IDS.index((vid, why)) + 1, why, REVIEWER, vid))
    cur.execute("delete from sponsorship_event_scores where platform = 'youtube' and content_id = any(%s)", (ids,))
    conn.commit()
    cur.execute("select count(*) from creator_sponsorship_events where content_id = any(%s)", (ids,))
    print(f"videos unflagged: {changed}; still events afterwards: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
