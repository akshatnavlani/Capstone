#!/usr/bin/env bash
# 15 Nov 2026: after the GAIL-R chain and the mood scoring finish, (1) run the negative-spillover test once and
# (2) the focused GAIL-R sponsorship run once (GAIL_R_FOCUSED_SPONSORSHIP_PLAN_15NOV.md), with keepalives and retries,
# keeping the run's checkpoint under its own name and restoring the app's model.
ROOT=/c/Users/Shimona/Documents/casptone
cd "$ROOT" || exit 1
PY="$ROOT/venv/Scripts/python.exe"; BACKUP="$ROOT/exports/model_backup_14nov"
until grep -q "mood scoring done" exports/gail_r_chain_15nov.log 2>/dev/null; do sleep 60; done

echo "$(date +%H:%M) negative spillover test (run once)"
[ -f models/negative_spillover_results_14nov.json ] || PYTHONIOENCODING=utf-8 "$PY" -u scripts/negative_spillover_test.py run > exports/negative_spillover_run_15nov.log 2>&1

DATABASE_URL="$("$PY" -c "import sys; sys.path.insert(0, 'scripts/ingestion'); from orchestrator import load_env; print(load_env()['DATABASE_URL'])")"
case "$DATABASE_URL" in *\?*) SEP='&' ;; *) SEP='?' ;; esac
export DATABASE_URL="${DATABASE_URL}${SEP}keepalives=1&keepalives_idle=30&keepalives_interval=10&keepalives_count=3&connect_timeout=20"
LOG=models/gail_r_focused_15nov.log
for TRY in 1 2 3; do
  echo "$(date +%H:%M) focused GAIL-R, try $TRY"
  GAIL_TREATMENT=sponsorship GAIL_STRONG_EVENTS=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_R_SMALL_B=1 \
    PYTHONPATH="$ROOT" PYTHONIOENCODING=utf-8 "$PY" -u scripts/train_prod_model.py > "$LOG" 2>&1
  echo "exit $?" >> "$LOG"
  [ -f models/gail_checkpoint.pt ] && ! cmp -s models/gail_checkpoint.pt "$BACKUP/gail_checkpoint.pt" && cp -p models/gail_checkpoint.pt models/gail_checkpoint_focused_15nov.pt
  [ -f models/training_pair_ids.json ] && mv models/training_pair_ids.json models/training_pair_ids_focused_15nov.json
  [ -f models/feature_scaler.json ] && mv models/feature_scaler.json models/feature_scaler_focused_15nov.json
  cp -p "$BACKUP/gail_checkpoint.pt" models/gail_checkpoint.pt
  grep -q "GAIL-R spillover estimate" "$LOG" && break
  sleep 120
done
echo "$(date +%H:%M) all done; app model restored"
