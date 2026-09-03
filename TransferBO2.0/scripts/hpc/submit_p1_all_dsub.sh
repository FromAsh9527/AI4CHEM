#!/bin/bash
# Submit both P1 BO tracks: amination (675) + Suzuki (360) = 1035 jobs
#
#   bash scripts/hpc/submit_p1_all_dsub.sh
#   DRY_RUN=1 bash scripts/hpc/submit_p1_all_dsub.sh

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

echo "[INFO] P1 BO dry-run check"
python scripts/run_source_subset_loso.py --config configs/amination_p1_source_robustness_hpc.yaml --dry-run | tail -3
python scripts/run_source_subset_loso.py --config configs/suzuki_p1_source_robustness_hpc.yaml --dry-run | tail -3

echo "[INFO] submitting amination P1 BO (675 jobs)..."
bash scripts/hpc/submit_p1_amination_dsub.sh

echo "[INFO] submitting Suzuki P1 BO (360 jobs)..."
bash scripts/hpc/submit_p1_suzuki_dsub.sh

echo "[INFO] all P1 BO shards submitted (10 dsub jobs total if N_SHARDS=5)"
echo "  find results/p1p2_source_robustness/amination -name '*__seed*.json' | wc -l  # 675"
echo "  find results/p1p2_source_robustness/suzuki -name '*__seed*.json' | wc -l     # 360"
