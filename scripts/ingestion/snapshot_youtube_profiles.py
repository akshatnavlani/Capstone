"""Record today's subscriber, video and view counts for every verified YouTube channel (profile_snapshots). Costs 1 quota unit per 50 channels (3 for the 150).

    python snapshot_youtube_profiles.py [--dry-run]

WHY (29 Oct 2026): profile_snapshots holds YouTube counts for only 4 days (11-15 Oct). Subscriber growth per creator needs a reading every day; run it once a day.
"""
import argparse
import sys

from orchestrator import ENV, get_connection, record_profile_snapshot, youtube_api_get

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = get_connection()
    cur = conn.cursor()
    # Verified channels plus every other held channel (7 Nov 2026): the collaboration study needs subscriber counts for
    # every creator who can be tagged, including the 130 collaborators added on 6-7 Nov. About 8 quota units a run.
    cur.execute("""select creator_id::text, yt_channel_id from creator_verification
                    where creator_id is not null and link_level in ('confirmed','probable') and yt_channel_id is not null
                   union
                   select creator_id::text, channel_id from youtube_channels
                    where creator_id is not null and channel_id like 'UC%%'""")
    rows = cur.fetchall()
    owner = {ch: cid for cid, ch in rows}
    saved = 0
    ids = list(owner)
    for i in range(0, len(ids), 50):
        r = youtube_api_get("channels", id=",".join(ids[i:i + 50]), part="statistics", maxResults=50)
        for it in r.get("items", []):
            st = it.get("statistics", {})
            if st.get("hiddenSubscriberCount") or "subscriberCount" not in st:
                continue
            if not args.dry_run:
                record_profile_snapshot(cur, "youtube", it["id"], owner[it["id"]], int(st["subscriberCount"]), int(st.get("videoCount", 0)), int(st.get("viewCount", 0)))
            saved += 1
    conn.commit()
    print(f"{'would save' if args.dry_run else 'saved'} {saved} of {len(ids)} channels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
