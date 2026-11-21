#!/usr/bin/env bash
# 22 Nov 2026 (GAIL_R_HYBRID_SIMULATION_PLAN_22NOV.md): save the final run's GAIL-R inputs, then the hybrid simulation.
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"; BACKUP="$ROOT/exports/model_backup_14nov"; Q=exports/queue_22nov.log; IN=models/gail_r_inputs_final_22nov.pt
export PYTHONIOENCODING=utf-8 PYTHONPATH="$ROOT"
DATABASE_URL="$("$PY" -c "import sys; sys.path.insert(0, 'scripts/ingestion'); from orchestrator import load_env; print(load_env()['DATABASE_URL'])")"
case "$DATABASE_URL" in *\?*) SEP='&' ;; *) SEP='?' ;; esac
export DATABASE_URL="${DATABASE_URL}${SEP}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3&connect_timeout=20"
for TRY in 1 2 3; do
  [ -f $IN ] && break
  echo "$(date +%H:%M) saving GAIL-R inputs, try $TRY" >> $Q
  env GAIL_TREATMENT=collab GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_TAG_CONFIRMATION=1 \
      GAIL_SAVE_R_INPUTS=$IN "$PY" -u scripts/train_prod_model.py > models/gail_r_hybrid_inputs_22nov.log 2>&1
  [ -f models/gail_checkpoint.pt ] && ! cmp -s models/gail_checkpoint.pt "$BACKUP/gail_checkpoint.pt" && cp -p "$BACKUP/gail_checkpoint.pt" models/gail_checkpoint.pt
  rm -f models/training_pair_ids.json models/feature_scaler.json
  [ -f $IN ] || sleep 120
done
[ -f $IN ] || { echo "$(date +%H:%M) inputs not saved; simulation not started" >> $Q; exit 1; }
echo "$(date +%H:%M) hybrid simulation started" >> $Q
"$PY" -u scripts/gail_r_hybrid_sim.py --inputs $IN >> exports/gail_r_hybrid_sim_22nov.log 2>&1
echo "$(date +%H:%M) hybrid simulation done (exit $?)" >> $Q
