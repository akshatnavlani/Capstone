"""Instagram handles from the links section of each creator's own YouTube About page (11 Nov 2026). READ ONLY on the database.

For in-scope creators still without an Instagram handle (and not already found in their descriptions), read
youtube.com/channel/<id>/about once (1 s apart) and collect full instagram.com/<handle> link targets. Exactly one distinct
handle -> taken; more than one -> listed as ambiguous, not taken. Writes models/ig_handles_about_11nov.json.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ingestion"))
from joint_video_spillover_test import load  # noqa: E402
from orchestrator import load_env  # noqa: E402

TARGET = re.compile(r"instagram\.com%2F([A-Za-z0-9_.]{3,30})(?![A-Za-z0-9_.])")
NOT_HANDLE = {"p", "reel", "reels", "stories", "explore", "accounts", "tv", "direct"}


def main() -> int:
    cur = psycopg2.connect(load_env()["DATABASE_URL"]).cursor()
    scope, *_ = load(cur)
    done = set(json.load(open(ROOT / "models" / "ig_handles_from_links_11nov.json", encoding="utf-8"))["found"])
    cur.execute("select c.creator_id::text, c.name, ch.channel_id from creators c join youtube_channels ch using(creator_id) where c.instagram_handle is null")
    todo = [(c, n, ch) for c, n, ch in cur.fetchall() if c in scope and c not in done]
    found, ambiguous, none, failed = {}, {}, [], []
    for i, (c, n, ch) in enumerate(todo):
        try:
            req = urllib.request.Request(f"https://www.youtube.com/channel/{ch}/about", headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"})
            html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        except Exception as e:   # noqa: BLE001
            failed.append(n)
            print(f"  {n}: {type(e).__name__}", flush=True)
            continue
        hs = sorted({h.lower().rstrip(".") for h in TARGET.findall(html)} - NOT_HANDLE)
        if len(hs) == 1:
            found[c] = {"name": n, "instagram_handle": hs[0], "source": "YouTube About page link"}
        elif hs:
            ambiguous[n] = hs
        else:
            none.append(n)
        time.sleep(1)
    out = ROOT / "models" / "ig_handles_about_11nov.json"
    out.write_text(json.dumps({"rule": __doc__.split("\n\n")[1], "found": found, "ambiguous_not_taken": ambiguous, "no_instagram_link": none,
                               "failed": failed}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(todo)} read: {len(found)} one handle, {len(ambiguous)} ambiguous, {len(none)} no link, {len(failed)} failed -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
