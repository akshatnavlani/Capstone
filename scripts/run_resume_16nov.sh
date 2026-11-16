#!/usr/bin/env bash
# 16 Nov 2026 evening: resumes the 16 Nov queue after it stopped at 17:25 (out of process resources). Same jobs and
# settings; order changed only so the GAIL-R runs are not stuck behind ~16 h of mood scoring.
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"; BACKUP="$ROOT/exports/model_backup_14nov"; Q=exports/queue_16nov.log
DATABASE_URL="$("$PY" -c "import sys; sys.path.insert(0, 'scripts/ingestion'); from orchestrator import load_env; print(load_env()['DATABASE_URL'])")"
case "$DATABASE_URL" in *\?*) SEP='&' ;; *) SEP='?' ;; esac
export DATABASE_URL="${DATABASE_URL}${SEP}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3&connect_timeout=20"

gail () {   # $1 = name, rest = env assignments
  NAME=$1; shift; LOG="models/gail_r_${NAME}.log"
  grep -q "GAIL-R spillover estimate" "$LOG" 2>/dev/null && grep -q "^exit 0" "$LOG" && return   # already done
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

echo "$(date +%H:%M) resumed (scripts/run_resume_16nov.sh)" >> $Q
gail focused_sponsorship_16nov GAIL_TREATMENT=sponsorship GAIL_STRONG_EVENTS=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_R_SMALL_B=1
gail featured_tag_16nov GAIL_TREATMENT=tag GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_TAG_CONFIRMATION=1 GAIL_R_SMALL_B=1
gail pooled_collab_16nov GAIL_TREATMENT=collab GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_TAG_CONFIRMATION=1 GAIL_R_SMALL_B=1
for TRY in 1 2 3 4 5; do
  echo "$(date +%H:%M) mood scoring, try $TRY (resumes from saved videos)" >> $Q
  PYTHONIOENCODING=utf-8 "$PY" -u scripts/negative_spillover_test.py score >> exports/negative_spillover_score_14nov.log 2>&1 && break
  sleep 120
done
echo "$(date +%H:%M) negative spillover test (once)" >> $Q
[ -f models/negative_spillover_results_14nov.json ] || PYTHONIOENCODING=utf-8 "$PY" -u scripts/negative_spillover_test.py run > exports/negative_spillover_run_16nov.log 2>&1
echo "$(date +%H:%M) queue done; app model restored" >> $Q
