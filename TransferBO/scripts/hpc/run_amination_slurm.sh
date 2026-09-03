# EDBO amination min S0 — single-node Slurm
#   sbatch scripts/hpc/run_amination_slurm.sh

#SBATCH -J edbo_amin
#SBATCH -p cpu
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48
#SBATCH -t 48:00:00
#SBATCH -o logs/amin_%j.out
#SBATCH -e logs/amin_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"
mkdir -p logs results/external_edbo_amination_min_s0

export PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:$PYTHONPATH}"

WORKERS="${WORKERS:-$SLURM_CPUS_PER_TASK}"

echo "host=$(hostname) workers=${WORKERS} start=$(date -Is)"
python scripts/run_transfer_grid.py \
  --config configs/transfer_grid_edbo_amination_min_s0.yaml \
  --skip-existing \
  --workers "${WORKERS}"
echo "done=$(date -Is)"
