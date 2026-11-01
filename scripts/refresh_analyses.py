"""Refresh every analysis result after new data has landed (YouTube catch-up, Instagram counts), then rebuild the Analysis tab file. READ ONLY on the database.

    python scripts/refresh_analyses.py

Runs, in order, each as its own script, and stops at the first failure: run_platform_pairs (YouTube vs Instagram within 24 h, Granger), run_ad_fatigue, run_long_lag,
run_promotion_behaviour (disclosure, sponsored response), then export_analysis_dashboard (what the Analysis tab and the API read). About 5 minutes. Not included, on purpose:
the audience graph and the GAIL training inputs (a re-export, then a retrain, is a separate decision), and the power analysis (it needs a new observations dump from a training run).
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
# run_long_lag.py at its default 1,000 shuffles ran over two hours on the 105,000-video data (30 Oct 2026); 300 shuffles finish in a fraction of that.
STEPS = [["run_platform_pairs.py"], ["run_ad_fatigue.py"], ["run_long_lag.py", "--placebo", "300"], ["run_snapshot_lag.py"], ["run_spillover_event_study.py", "--placebo", "300"], ["run_label_noise_sensitivity.py"], ["run_promotion_behaviour.py"], ["build_creator_passport.py"], ["export_analysis_dashboard.py"]]


def main() -> int:
    for script, *extra in STEPS:
        step = script
        print(f"{datetime.now():%H:%M:%S} start {step}", flush=True)
        rc = subprocess.call([sys.executable, "-u", str(HERE / script), *extra])
        print(f"{datetime.now():%H:%M:%S} done  {step} (exit {rc})", flush=True)
        if rc != 0:
            print("stopping: a step failed; the later steps were skipped")
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
