"""Show what was actually said around each spoken-sponsor hit, so a person (or Claude, with Shimona's yes) can judge it. READ ONLY.

    python spoken_context.py                       # hits of spoken_scan that have no verdict yet
    python spoken_context.py --videos ID1 ID2      # specific videos (for example the 17 hits of 24 Oct that carry only a bare Hindi word)
    python spoken_context.py --out hits.json

Fetches the captions again (same rules as spoken_scan.py: 20 s between requests, stops at the first block; do NOT run it while spoken_scan.py is running, they share the
IP and YouTube blocks after 10-20 requests), finds the evidence phrase and prints about 180 characters either side. Writes nothing to the database.
"""
import argparse
import json
import re
import sys
import time

from spoken_scan import GAP_SECONDS, scan_one  # noqa: F401  (scan_one's API object is created below)


def transcript_text(api, video_id: str, languages=("hi", "en")) -> str | None:
    listing = api.list(video_id)
    try:
        transcript = listing.find_transcript(list(languages))
    except Exception:
        transcript = next(iter(listing), None)
    if transcript is None:
        return None
    return " ".join(s.text for s in transcript.fetch())


def phrases(evidence: list[str]) -> list[str]:
    out = []
    for e in evidence:
        m = re.match(r"spoken:disclosure:(.+)$", e)
        if m:
            out.append(m.group(1))
        m = re.match(r"spoken:brand:(.+?)\(", e)
        if m:
            out.append(m.group(1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--videos", nargs="*")
    ap.add_argument("--out")
    args = ap.parse_args()
    from db_retry import connect_with_retry
    from orchestrator import get_connection
    from youtube_transcript_api import YouTubeTranscriptApi

    conn = connect_with_retry(get_connection)
    with conn.cursor() as cur:
        if args.videos:
            cur.execute("select s.video_id, s.evidence, v.title, c.name from spoken_scan s join youtube_videos v on v.video_id = s.video_id left join creators c on c.creator_id = v.creator_id where s.video_id = any(%s)", (args.videos,))
        else:
            cur.execute("select s.video_id, s.evidence, v.title, c.name from spoken_scan s join youtube_videos v on v.video_id = s.video_id left join creators c on c.creator_id = v.creator_id "
                        "where jsonb_array_length(s.evidence) > 0 and s.verdict is null order by s.scanned_at")
        rows = cur.fetchall()
    api, out = YouTubeTranscriptApi(), []
    for vid, evidence, title, name in rows:
        try:
            text = transcript_text(api, vid)
        except Exception as e:  # a block or a missing transcript: stop here, a re-run continues
            print(f"stopped at {vid}: {type(e).__name__}")
            break
        snippets = []
        for ph in phrases(evidence):
            for m in list(re.finditer(re.escape(ph), text or "", re.I))[:3]:
                snippets.append((text[max(m.start() - 180, 0): m.end() + 180]).replace("\n", " "))
        out.append({"video_id": vid, "creator": name, "title": title, "evidence": evidence, "context": snippets})
        print(f"\n== {name} | {title}\n   https://www.youtube.com/watch?v={vid}  {evidence}")
        for s in snippets:
            print("   ...", s, "...")
        time.sleep(GAP_SECONDS)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
