#!/usr/bin/env bash
# 21 Nov 2026: the final GAIL-R run (GAIL_R_FINAL_SMALL_CREATORS_PLAN_17NOV.md). Step 1 rebuilds the event lists on the
# complete data into *_final21nov.json (same builders, earlier files untouched). Step 2 runs GAIL-R ONCE.
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"; BACKUP="$ROOT/exports/model_backup_14nov"; Q=exports/queue_21nov.log
export PYTHONIOENCODING=utf-8 PYTHONPATH="$ROOT"
echo "$(date +%H:%M) rebuilding event lists (final21nov)" >> $Q
SPILL_TAG=final21nov "$PY" scripts/joint_video_spillover_test.py events >> $Q 2>&1
SPILL_TAG=older_final21nov SPILL_NOW=2024-11-09 "$PY" scripts/joint_video_spillover_test.py events >> $Q 2>&1
SPILL_TAG=final21nov "$PY" scripts/audience_flow_test.py build-events --rep >> $Q 2>&1
(cd scripts && "$PY" -c "
import sys; sys.argv=['x','count']
from pathlib import Path
import tag_engagement_older_period_test as t
t.EVENTS = Path('../models/tag_older_period_events_final21nov.json')
import psycopg2; t.build(psycopg2.connect(t.af.load_env()['DATABASE_URL']).cursor())") >> $Q 2>&1
for f in joint_video_events_9nov_final21nov joint_video_events_9nov_older_final21nov audience_flow_events_rep_9nov_final21nov tag_older_period_events_final21nov; do
  [ -f "models/$f.json" ] || { echo "$(date +%H:%M) MISSING models/$f.json; GAIL-R not started" >> $Q; exit 1; }
done

DATABASE_URL="$("$PY" -c "import sys; sys.path.insert(0, 'scripts/ingestion'); from orchestrator import load_env; print(load_env()['DATABASE_URL'])")"
case "$DATABASE_URL" in *\?*) SEP='&' ;; *) SEP='?' ;; esac
export DATABASE_URL="${DATABASE_URL}${SEP}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3&connect_timeout=20"
NAME=final_small_21nov; LOG="models/gail_r_${NAME}.log"
for TRY in 1 2 3; do
  echo "$(date +%H:%M) GAIL-R $NAME, try $TRY" >> $Q
  env GAIL_TREATMENT=collab GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_TAG_CONFIRMATION=1 GAIL_R_SMALL_B=1 \
      "$PY" -u scripts/train_prod_model.py > "$LOG" 2>&1
  echo "exit $?" >> "$LOG"
  [ -f models/gail_checkpoint.pt ] && ! cmp -s models/gail_checkpoint.pt "$BACKUP/gail_checkpoint.pt" && cp -p models/gail_checkpoint.pt "models/gail_checkpoint_${NAME}.pt"
  [ -f models/training_pair_ids.json ] && mv models/training_pair_ids.json "models/training_pair_ids_${NAME}.json"
  [ -f models/feature_scaler.json ] && mv models/feature_scaler.json "models/feature_scaler_${NAME}.json"
  cp -p "$BACKUP/gail_checkpoint.pt" models/gail_checkpoint.pt
  grep -q "GAIL-R spillover estimate" "$LOG" && break
  sleep 120
done
echo "$(date +%H:%M) final GAIL-R run done; app model restored" >> $Q
