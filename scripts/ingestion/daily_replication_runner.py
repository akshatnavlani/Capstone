"""Runs the replication comment fetch once a day after the YouTube quota resets (13:30 IST), until nothing is left (10 Nov 2026).

Same two runs as exports/replication_fetch_10nov.cmd: event videos, then placebo videos, 1,750 units each (3,500 a day,
leaving room for the GitHub timers on the shared 10,000-unit key). Stops by itself when both lists are done.

    python daily_replication_runner.py            # first run tomorrow 13:40 (today's run was started by hand)
Runs in a terminal tab; closing the tab or restarting the laptop stops it.
"""
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LISTS = [("events", ROOT / "models" / "audience_flow_videos_rep_9nov.txt"),
         ("placebo", ROOT / "models" / "audience_flow_placebo_videos_rep_9nov.txt")]


def run_once() -> int:
    """Returns how many videos were still waiting across both lists."""
    waiting = 0
    for name, path in LISTS:
        log = ROOT / "exports" / f"rep_fetch_{name}_{datetime.now():%d%b}.log".lower()
        with open(log, "w", encoding="utf-8") as fh:
            subprocess.run([sys.executable, "-u", "youtube_comments_backfill.py", "--video-ids-file", str(path),
                            "--pages", "3", "--max-units", "1750"], cwd=HERE, stdout=fh, stderr=subprocess.STDOUT)
        text = log.read_text(encoding="utf-8")
        m = re.search(r"(\d+) videos waiting", text)
        n = int(m.group(1)) if m else -1
        waiting += max(n, 0)
        print(f"{datetime.now():%d %b %H:%M} {name}: {n} were waiting; last line: {text.strip().splitlines()[-1:]}", flush=True)
    return waiting


prev = None
while True:
    now = datetime.now()
    nxt = now.replace(hour=13, minute=40, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    print(f"next fetch {nxt:%d %b %H:%M}", flush=True)
    time.sleep((nxt - now).total_seconds())
    left = run_once()
    if left <= 20 or left == prev:   # done, or only videos YouTube returns no comments for (they never leave the list)
        print(f"{left} left; stopping", flush=True)
        break
    prev = left
