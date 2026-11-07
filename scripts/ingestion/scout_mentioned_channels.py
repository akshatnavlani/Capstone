"""Look up the YouTube channels that our sponsoring creators mention but we do not hold. 6 Nov 2026.

    python scout_mentioned_channels.py [--limit N]

WHY. models/collab_funnel_missing.csv (scripts/audit_collab_funnel.py) lists 1,588 YouTube handles mentioned
by a creator who has a dated sponsorship. Each one we add with its history can become a measured neighbour.
Before adding any, we need to know WHO each handle is (a fitness creator, a brand, a film star, a stray
@word), so the fitness/health shortlist is chosen on identity alone, never on engagement after an event.

WHAT IT DOES. One channels?forHandle call per handle (1 quota unit), saving title, description, country,
subscriber and video counts to models/mentioned_channels_6nov.json. Resumable: handles already in the file
are skipped. READ-ONLY on the database; writes only the JSON file.
"""
import argparse
import csv
import json
import os
import time
import urllib.error

from orchestrator import log, youtube_api_get

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MISSING = os.path.join(ROOT, "models", "collab_funnel_missing.csv")
OUT = os.path.join(ROOT, "models", "mentioned_channels_6nov.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2000, help="most handles to look up this run (= quota units)")
    args = ap.parse_args()
    with open(MISSING, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if "yt_mention" in r["sources"] and int(r["sponsored_A"]) > 0]
    done = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    todo = [r for r in rows if r["handle"].lstrip("@").lower() not in done][: args.limit]
    log.info("%d candidate handles, %d already looked up, %d to look up now", len(rows), len(done), len(todo))
    for i, r in enumerate(todo, 1):
        h = r["handle"].lstrip("@").lower()
        for attempt in range(4):  # a dropped connection (WinError 10054) stopped the 6 Nov run at 1,305
            try:
                items = youtube_api_get("channels", forHandle="@" + h, part="snippet,statistics").get("items", [])
                break
            except urllib.error.URLError as e:
                log.warning("@%s: %s; retry %d", h, e, attempt + 1)
                time.sleep(5 * (attempt + 1))
        else:
            json.dump(done, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            raise SystemExit("network kept failing; progress saved, re-run to continue")
        rec = {"sponsored_A": int(r["sponsored_A"]), "mentioned_by": int(r["mentioned_by"]), "example_A": r["example_A"]}
        if items:
            ch = items[0]
            rec.update(channel_id=ch["id"], title=ch["snippet"].get("title"), description=(ch["snippet"].get("description") or "")[:600],
                       country=ch["snippet"].get("country"), subscribers=int(ch["statistics"].get("subscriberCount") or 0),
                       videos=int(ch["statistics"].get("videoCount") or 0))
        done[h] = rec
        if i % 50 == 0 or i == len(todo):
            json.dump(done, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            log.info("%d/%d looked up", i, len(todo))
    found = sum(1 for v in done.values() if v.get("channel_id"))
    log.info("done: %d handles looked up in total, %d have a channel", len(done), found)


if __name__ == "__main__":
    main()
