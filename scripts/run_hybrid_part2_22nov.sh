#!/usr/bin/env bash
# 22 Nov 2026: waits for hybrid part 1 ("hybrid simulation done" in exports/queue_22nov.log), then runs part 2 once.
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"; Q=exports/queue_22nov.log
until grep -q "hybrid simulation done" $Q; do sleep 60; done
echo "$(date +%H:%M) hybrid part 2 (sample size) started" >> $Q
PYTHONIOENCODING=utf-8 PYTHONPATH="$ROOT" "$PY" -u scripts/gail_r_hybrid_sample_size.py --inputs models/gail_r_inputs_final_22nov.pt >> exports/gail_r_hybrid_sample_size_22nov.log 2>&1
echo "$(date +%H:%M) hybrid part 2 done (exit $?)" >> $Q
