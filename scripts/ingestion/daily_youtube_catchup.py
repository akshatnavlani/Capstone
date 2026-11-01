"""One daily YouTube catch-up, run after the quota reset (12:30 IST): subscribers, older history, comments, labels. Each step is its own script; the run stops at the first failure.

    python daily_youtube_catchup.py [--history-budget 2500] [--comment-units 1500] [--dry-run]

WHY (29 Oct 2026): the 2-hourly Supabase job uses about 2,400 of the 10,000 daily units on the single key. This spends part of the rest on growing the data:
  1. snapshot_youtube_profiles.py        subscriber / video / view counts of every verified channel (3 units)
  2. youtube_backfill_history.py         older uploads, back to --days 1460 (skips channels that already reach the cutoff), at most --history-budget units
  3. youtube_comments_backfill.py        comments for recent long videos that have none, at most --comment-units units
  4. label_new_videos.py --since <start> the rule-based sponsorship detector on videos added by step 2 (never flips true to false, backs up every change)
Defaults keep the total near 4,000 units, leaving about 3,600 spare on the day. Writes a log line per step in models/daily_youtube_catchup.log.
"""
import argparse
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE.parent.parent / "models" / "daily_youtube_catchup.log"


def say(msg: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history-budget", type=int, default=2500)
    ap.add_argument("--comment-units", type=int, default=1500)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    since = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M+00")
    steps = [
        ("subscribers", ["snapshot_youtube_profiles.py"]),
        ("older history", ["youtube_backfill_history.py", "--days", "1460", "--quota-budget", str(args.history_budget)]),
        ("comments", ["youtube_comments_backfill.py", "--max-units", str(args.comment_units)]),
        ("labels for new videos", ["label_new_videos.py", "--since", since]),
    ]
    for name, cmd in steps:
        if args.dry_run:
            say(f"[dry run] would run: {' '.join(cmd)}")
            continue
        say(f"start: {name}")
        rc = subprocess.call([sys.executable, "-u", *cmd], cwd=HERE)
        say(f"done: {name} (exit {rc})")
        if rc != 0:
            say("stopping: a step failed; the later steps are skipped")
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
