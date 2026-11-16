#!/usr/bin/env bash
# 16 Nov 2026: waits for scripts/run_after_queue_16nov.sh ("featured tag run done"), then ONE GAIL-R job:
# tags + joint videos pooled, featured creator, 7 days (GAIL_R_POOLED_COLLAB_PLAN_16NOV.md).
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"; BACKUP="$ROOT/exports/model_backup_14nov"; Q=exports/queue_16nov.log
until grep -q "featured tag run done" $Q; do sleep 60; done
DATABASE_URL="$("$PY" -c "import sys; sys.path.insert(0, 'scripts/ingestion'); from orchestrator import load_env; print(load_env()['DATABASE_URL'])")"
case "$DATABASE_URL" in *\?*) SEP='&' ;; *) SEP='?' ;; esac
export DATABASE_URL="${DATABASE_URL}${SEP}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3&connect_timeout=20"

NAME=pooled_collab_16nov; LOG="models/gail_r_${NAME}.log"
for TRY in 1 2 3; do
  echo "$(date +%H:%M) GAIL-R $NAME, try $TRY" >> $Q
  env GAIL_TREATMENT=collab GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_TAG_CONFIRMATION=1 GAIL_R_SMALL_B=1 \
      PYTHONPATH="$ROOT" PYTHONIOENCODING=utf-8 "$PY" -u scripts/train_prod_model.py > "$LOG" 2>&1
  echo "exit $?" >> "$LOG"
  [ -f models/gail_checkpoint.pt ] && ! cmp -s models/gail_checkpoint.pt "$BACKUP/gail_checkpoint.pt" && cp -p models/gail_checkpoint.pt "models/gail_checkpoint_${NAME}.pt"
  [ -f models/training_pair_ids.json ] && mv models/training_pair_ids.json "models/training_pair_ids_${NAME}.json"
  [ -f models/feature_scaler.json ] && mv models/feature_scaler.json "models/feature_scaler_${NAME}.json"
  cp -p "$BACKUP/gail_checkpoint.pt" models/gail_checkpoint.pt
  grep -q "GAIL-R spillover estimate" "$LOG" && break
  sleep 120
done
echo "$(date +%H:%M) pooled collab run done; app model restored" >> $Q
