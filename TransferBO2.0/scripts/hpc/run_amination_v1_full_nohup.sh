#!/usr/bin/env bash
# Interactive / no-scheduler full LOSO (login node: keep WORKERS modest).
#   cd ~/TransferBO2.0 && bash scripts/hpc/run_amination_v1_full_nohup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
mkdir -p logs results/amination_v1_full

if [[ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/miniconda3/etc/profile.d/conda.sh"
  conda activate base
fi

export PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

WORKERS="${WORKERS:-8}"
LOG="logs/amin_v1_full_nohup_$(date +%Y%m%d_%H%M%S).log"

echo "host=$(hostname) workers=${WORKERS} log=${LOG}"
nohup python scripts/run_loso.py \
  --config configs/amination_exp_v1_full.yaml \
  --skip-existing \
  --workers "${WORKERS}" \
  >"${LOG}" 2>&1 &
echo "pid=$!"
echo "tail -f ${LOG}"
