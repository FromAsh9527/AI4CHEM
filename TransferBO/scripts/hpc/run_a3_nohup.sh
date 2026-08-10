#!/usr/bin/env bash
# Interactive / no-scheduler A3 run (this site has no sbatch/qsub).
# Usage (after offline conda install):
#   source $HOME/miniconda3/etc/profile.d/conda.sh && conda activate base
#   cd ~/TransferBO && bash scripts/hpc/run_a3_nohup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
mkdir -p logs results/external_edbo_suzuki_a3

# Prefer home miniconda if present
if [[ -f "${HOME}/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/miniconda3/etc/profile.d/conda.sh"
  conda activate base
fi

export PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

# Cap workers to avoid thrashing login/desktop nodes; override: WORKERS=16 bash ...
WORKERS="${WORKERS:-8}"
LOG="logs/a3_nohup_$(date +%Y%m%d_%H%M%S).log"

echo "host=$(hostname) workers=${WORKERS} log=${LOG}"
nohup python scripts/run_transfer_grid.py \
  --config configs/transfer_grid_edbo_suzuki_a3.yaml \
  --skip-existing \
  --workers "${WORKERS}" \
  >"${LOG}" 2>&1 &
echo "pid=$!"
echo "tail -f ${LOG}"
