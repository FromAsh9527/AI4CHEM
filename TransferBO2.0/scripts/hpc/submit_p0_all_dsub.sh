#!/bin/bash
# Submit both P0 tracks: amination sanity (60) + Suzuki full (360) = 420 jobs
#
#   bash scripts/hpc/submit_p0_all_dsub.sh
#   DRY_RUN=1 bash scripts/hpc/submit_p0_all_dsub.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CONDA_SH="${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"
if [[ -f "$CONDA_SH" ]]; then
  # shellcheck disable=SC1090
  source "$CONDA_SH"
  conda activate base 2>/dev/null || true
fi
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

echo "[INFO] P0 dry-run check"
python scripts/run_loso.py --config configs/amination_p0_shared_init_sanity.yaml --dry-run | tail -3
python scripts/run_loso.py --config configs/suzuki_p0_shared_init_hpc.yaml --dry-run | tail -3

echo "[INFO] submitting amination sanity (60 jobs)..."
bash scripts/hpc/submit_p0_amination_sanity_dsub.sh

echo "[INFO] submitting Suzuki full (360 jobs)..."
bash scripts/hpc/submit_p0_suzuki_dsub.sh

echo "[INFO] all P0 shards submitted (10 dsub jobs total if N_SHARDS=5)"
echo "  find results/amination_p0_shared_init_sanity -name '*.json' ! -name 'loso_records.json' | wc -l  # 60"
echo "  find results/suzuki_p0_shared_init -name '*.json' ! -name 'loso_records.json' | wc -l           # 360"
