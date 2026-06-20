#!/usr/bin/env bash
# Ablação de pré-processamento da nuvem (tese): roda os 6 modelos em duas configs
#   raw    = sem projeção do solo e sem remoção ≤ 1,3 m (Z centrado cru)
#   ground = só projeção do solo (sem remoção ≤ 1,3 m)
# A config "both" (projeção do solo + remoção ≤ 1,3 m) já é a treinada por padrão.
# Logs por modelo em data/processed/06_model/runlogs/. Resumível: pula o que já tem
# model_metrics_*.json. Continua mesmo se um modelo falhar.
set -u
cd "$(dirname "$0")"
PY=../.venv/bin/python
OUT=../data/processed/06_model
LOGDIR=$OUT/runlogs
mkdir -p "$LOGDIR"

# script -> chave do model_metrics (sem sufixo de variante)
declare -A KEY=(
  [train_model.py]=""        # model_metrics{SUFFIX}.json  (gbr)
  [train_aba.py]="_aba"
  [train_rf.py]="_rf"
  [train_pointnet.py]="_pointnet"
  [train_raster_cnn.py]="_raster"
  [train_voxel_cnn.py]="_voxel"
)
MODELS=(train_model.py train_aba.py train_rf.py \
        train_pointnet.py train_raster_cnn.py train_voxel_cnn.py)

run() {  # $1=PREPROC  $2=script
  local pre="$1" s="$2" name="${2%.py}"
  local suf; case "$pre" in raw) suf="_raw";; ground) suf="_ground";; *) suf="";; esac
  local metrics="$OUT/model_metrics${KEY[$s]}${suf}.json"
  local log="$LOGDIR/${name}_${pre}.log"
  if [[ -f "$metrics" ]]; then
    echo ">>> [$(date +%H:%M:%S)] PULA $name ($pre) — já existe $(basename "$metrics")"
    return
  fi
  echo ">>> [$(date +%H:%M:%S)] PREPROC=$pre $s -> $log"
  if PREPROC="$pre" "$PY" -u "$s" >"$log" 2>&1; then
    echo "    OK  $name ($pre)"
  else
    echo "    FALHOU  $name ($pre) — ver $log"
  fi
}

for pre in raw ground; do
  for s in "${MODELS[@]}"; do
    run "$pre" "$s"
  done
done
echo ">>> [$(date +%H:%M:%S)] ablação concluída."
