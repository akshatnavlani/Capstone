"""Daily older-history fetch for all in-scope channels, after the 13:30 IST quota reset (12 Nov 2026).

Each day at 13:40: first the 2022-2024 window (--days 1470; needed by TAG_ENGAGEMENT_OLDER_PERIOD_PLAN_12NOV.md), then the
whole history (--days 6000) with whatever is left of the day's budget. At most 4,500 units a day (the YouTube key is shared
with the 2-hourly timers and the subscriber readings). Stops after a day that adds no videos, or on 20 Nov 2026.

    python history_backfill_runner.py            # in a terminal tab; closing it or restarting the laptop stops it
    python history_backfill_runner.py --now      # also run once immediately
"""
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGS = HERE.parents[1] / "exports"
DAILY, END = 4500, datetime(2026, 11, 20, 23, 0)


def fetch(days: int, budget: int) -> tuple[int, int]:
    log = LOGS / f"history_backfill_{datetime.now():%d%b}_{days}d.log".lower()
    with open(log, "a", encoding="utf-8") as fh:
        subprocess.run([sys.executable, "-u", "youtube_backfill_history.py", "--in-scope", "--days", str(days), "--max-new-per-creator", "5000",
                        "--quota-budget", str(budget)], cwd=HERE, stdout=fh, stderr=subprocess.STDOUT)
    m = re.findall(r"done: (\d+) videos added, (\d+) quota units used", log.read_text(encoding="utf-8"))
    added, used = (int(m[-1][0]), int(m[-1][1])) if m else (0, budget)
    print(f"{datetime.now():%d %b %H:%M} --days {days}: {added} videos added, {used} units", flush=True)
    return added, used


def day_run() -> int:
    """The script stops at its first error (e.g. a network timeout); retry with what is left, up to 6 tries per stage."""
    added = used = 0
    for days in (1470, 6000):
        for _try in range(6):
            left = DAILY - used
            if left < 50:
                return added
            a, u = fetch(days, left)
            added, used = added + a, used + u
            if u < left - 50 and a == 0:   # finished this stage (nothing left to add) or failed straight away
                break
    return added


if "--now" in sys.argv:
    day_run()
while datetime.now() < END:
    now = datetime.now()
    nxt = now.replace(hour=13, minute=40, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    print(f"next fetch {nxt:%d %b %H:%M}", flush=True)
    time.sleep((nxt - now).total_seconds())
    if day_run() == 0:
        print("nothing left to add; stopping", flush=True)
        break
