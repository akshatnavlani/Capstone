"""Laptop backup for the 30-minute subscriber timer (10 Nov 2026).

GitHub started .github/workflows/snapshot_subscribers.yml only 4 times in 19 hours on 9-10 Nov (gaps up to 5.5 h);
the forward spillover tests need a reading within 3 h. This loop runs snapshot_youtube_profiles.py every 30 minutes
until --until (about 9 units a run, ~430 a day). Extra readings from both sources are harmless.

    python subscriber_loop.py --until 2026-12-01
Stops by itself at --until; it does not survive a restart or shutdown (start it again then).
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("--until", default="2026-12-01")
ap.add_argument("--every-min", type=float, default=30)
args = ap.parse_args()
end = datetime.fromisoformat(args.until)
while datetime.now() < end:
    t0 = time.time()
    r = subprocess.run([sys.executable, str(HERE / "snapshot_youtube_profiles.py")], cwd=HERE, capture_output=True, text=True)
    print(f"{datetime.now():%d %b %H:%M} exit {r.returncode}: {(r.stdout or r.stderr).strip().splitlines()[-1:]}", flush=True)
    time.sleep(max(60, args.every_min * 60 - (time.time() - t0)))
