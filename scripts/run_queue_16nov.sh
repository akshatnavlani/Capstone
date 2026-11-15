#!/usr/bin/env bash
# 16 Nov 2026 night queue, one job at a time (plans: GAIL_R_FEATURED_JOINT_VIDEO_PLAN_15NOV.md,
# GAIL_R_COLLAB_TREATMENT_PLAN_14NOV.md (+ note 16 Nov), NEGATIVE_SPILLOVER_PLAN_14NOV.md, GAIL_R_FOCUSED_SPONSORSHIP_PLAN_15NOV.md).
# Each GAIL-R run: keepalive connection, up to 3 tries if it dies before printing an estimate, checkpoint kept under its
# own name, app model restored.
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"; BACKUP="$ROOT/exports/model_backup_14nov"; Q=exports/queue_16nov.log
DATABASE_URL="$("$PY" -c "import sys; sys.path.insert(0, 'scripts/ingestion'); from orchestrator import load_env; print(load_env()['DATABASE_URL'])")"
case "$DATABASE_URL" in *\?*) SEP='&' ;; *) SEP='?' ;; esac
export DATABASE_URL="${DATABASE_URL}${SEP}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3&connect_timeout=20"

gail () {   # $1 = name, rest = env assignments
  NAME=$1; shift; LOG="models/gail_r_${NAME}.log"
  for TRY in 1 2 3; do
    echo "$(date +%H:%M) GAIL-R $NAME, try $TRY" >> $Q
    env "$@" PYTHONPATH="$ROOT" PYTHONIOENCODING=utf-8 "$PY" -u scripts/train_prod_model.py > "$LOG" 2>&1
    echo "exit $?" >> "$LOG"
    [ -f models/gail_checkpoint.pt ] && ! cmp -s models/gail_checkpoint.pt "$BACKUP/gail_checkpoint.pt" && cp -p models/gail_checkpoint.pt "models/gail_checkpoint_${NAME}.pt"
    [ -f models/training_pair_ids.json ] && mv models/training_pair_ids.json "models/training_pair_ids_${NAME}.json"
    [ -f models/feature_scaler.json ] && mv models/feature_scaler.json "models/feature_scaler_${NAME}.json"
    cp -p "$BACKUP/gail_checkpoint.pt" models/gail_checkpoint.pt
    grep -q "GAIL-R spillover estimate" "$LOG" && return
    sleep 120
  done
}

gail featured_jv_16nov GAIL_TREATMENT=joint_video GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=14 GAIL_BASELINE_DAYS=30 GAIL_R_SMALL_B=1
gail joint_video_fixed_16nov GAIL_TREATMENT=joint_video GAIL_R_SMALL_B=1
gail tag_fixed_16nov GAIL_TREATMENT=tag GAIL_R_SMALL_B=1
for TRY in 1 2 3 4 5; do
  echo "$(date +%H:%M) mood scoring, try $TRY" >> $Q
  PYTHONIOENCODING=utf-8 "$PY" -u scripts/negative_spillover_test.py score >> exports/negative_spillover_score_14nov.log 2>&1 && break
  sleep 120
done
echo "$(date +%H:%M) negative spillover test (once)" >> $Q
[ -f models/negative_spillover_results_14nov.json ] || PYTHONIOENCODING=utf-8 "$PY" -u scripts/negative_spillover_test.py run > exports/negative_spillover_run_16nov.log 2>&1
gail focused_sponsorship_16nov GAIL_TREATMENT=sponsorship GAIL_STRONG_EVENTS=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_R_SMALL_B=1
echo "$(date +%H:%M) queue done; app model restored" >> $Q
