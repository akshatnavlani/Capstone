#!/usr/bin/env bash
# 14 Nov 2026: run the GAIL-R update (sponsorship) and the two collaboration-treatment variants once each
# (GAIL_R_UPDATE_PLAN_14NOV.md, GAIL_R_COLLAB_TREATMENT_PLAN_14NOV.md). A run that dies before printing any estimate
# (e.g. the internet drops) is retried up to 3 times; a run that printed an estimate is never repeated. Every run's
# checkpoint is kept under its own name and the app's model is restored after each run.
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"
BACKUP="$ROOT/exports/model_backup_14nov"
# 15 Nov 2026: a silently dropped connection hung the 11:09 run for over an hour (client waiting, server idle). TCP
# keepalives make a dead connection fail within about a minute, so the script's reconnecting cursor carries on.
# The address is read from .env into the environment only (never printed).
DATABASE_URL="$("$PY" -c "import sys; sys.path.insert(0, 'scripts/ingestion'); from orchestrator import load_env; print(load_env()['DATABASE_URL'])")"
case "$DATABASE_URL" in *\?*) SEP='&' ;; *) SEP='?' ;; esac
export DATABASE_URL="${DATABASE_URL}${SEP}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3&connect_timeout=20"

keep_and_restore () {   # $1 = suffix
  [ -f models/gail_checkpoint.pt ] && ! cmp -s models/gail_checkpoint.pt "$BACKUP/gail_checkpoint.pt" && cp -p models/gail_checkpoint.pt "models/gail_checkpoint_$1.pt"
  [ -f models/training_pair_ids.json ] && mv models/training_pair_ids.json "models/training_pair_ids_$1.json"
  [ -f models/feature_scaler.json ] && mv models/feature_scaler.json "models/feature_scaler_$1.json"
  cp -p "$BACKUP/gail_checkpoint.pt" models/gail_checkpoint.pt
}

for T in sponsorship joint_video tag; do
  NAME=$T; [ "$T" = sponsorship ] && NAME=update
  LOG="models/gail_r_${NAME}_14nov.log"
  SMALL=1; [ "$T" = sponsorship ] && SMALL=0
  for TRY in 1 2 3; do
    echo "$(date +%H:%M) GAIL-R $T, try $TRY"
    GAIL_TREATMENT=$T GAIL_R_SMALL_B=$SMALL PYTHONPATH="$ROOT" PYTHONIOENCODING=utf-8 "$PY" -u scripts/train_prod_model.py > "$LOG" 2>&1
    echo "exit $?" >> "$LOG"
    keep_and_restore "${NAME}_14nov"
    grep -q "GAIL-R spillover estimate" "$LOG" && break
    sleep 120
  done
done
echo "$(date +%H:%M) chain done; app model restored"
