#!/usr/bin/env bash
# 14 Nov 2026: after the GAIL-R update run finishes, run the two collaboration-treatment variants once each
# (GAIL_R_COLLAB_TREATMENT_PLAN_14NOV.md), keep every run's checkpoint under its own name, and restore the app's model.
cd "$(dirname "$0")/.."
BACKUP=exports/model_backup_14nov
while powershell -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"name like 'python%'\" | Where-Object { \$_.CommandLine -like '*train_prod_model*' }) { exit 0 } else { exit 1 }"; do sleep 60; done

keep_and_restore () {   # $1 = suffix
  [ -f models/gail_checkpoint.pt ] && cp -p models/gail_checkpoint.pt "models/gail_checkpoint_$1.pt"
  [ -f models/training_pair_ids.json ] && mv models/training_pair_ids.json "models/training_pair_ids_$1.json"
  [ -f models/feature_scaler.json ] && mv models/feature_scaler.json "models/feature_scaler_$1.json"
  cp -p "$BACKUP/gail_checkpoint.pt" models/gail_checkpoint.pt
}

keep_and_restore update_14nov
for T in joint_video tag; do
  echo "$(date +%H:%M) starting GAIL-R with GAIL_TREATMENT=$T"
  GAIL_TREATMENT=$T GAIL_R_SMALL_B=1 PYTHONPATH=. PYTHONIOENCODING=utf-8 venv/Scripts/python.exe -u scripts/train_prod_model.py > "models/gail_r_${T}_14nov.log" 2>&1
  echo "exit $?" >> "models/gail_r_${T}_14nov.log"
  keep_and_restore "${T}_14nov"
done
echo "$(date +%H:%M) chain done; app model restored"
