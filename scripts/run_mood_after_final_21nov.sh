#!/usr/bin/env bash
# 21 Nov 2026: waits for the final GAIL-R run (exports/queue_21nov.log "final GAIL-R run done"), then resumes the mood
# scoring of NEGATIVE_SPILLOVER_PLAN_14NOV.md and runs the test ONCE. Not in parallel with GAIL-R (16 Nov resource crash).
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"; Q=exports/queue_21nov.log
# 21 Nov 20:09: started now, alongside GAIL-R (5.1 GB RAM free, 10 GB commit headroom checked)
for TRY in 1 2 3 4 5; do
  echo "$(date +%H:%M) mood scoring, try $TRY (resumes from saved videos)" >> $Q
  PYTHONIOENCODING=utf-8 "$PY" -u scripts/negative_spillover_test.py score >> exports/negative_spillover_score_14nov.log 2>&1 && break
  sleep 120
done
echo "$(date +%H:%M) negative spillover test (once)" >> $Q
[ -f models/negative_spillover_results_14nov.json ] || PYTHONIOENCODING=utf-8 "$PY" -u scripts/negative_spillover_test.py run > exports/negative_spillover_run_21nov.log 2>&1
echo "$(date +%H:%M) negative spillover done" >> $Q
