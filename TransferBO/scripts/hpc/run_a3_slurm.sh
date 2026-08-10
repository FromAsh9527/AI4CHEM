# EDBO Suzuki A3 on HPC (Slurm)
# Usage (edit account/partition/module names for your center):
#   sbatch scripts/hpc/run_a3_slurm.sh
#
# Resume-safe: --skip-existing. Sync partial results/external_edbo_suzuki_a3/*.json first.

#SBATCH -J edbo_a3
#SBATCH -p cpu                 # TODO: your partition
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=48     # TODO: match node cores; workers ≈ this
#SBATCH -t 48:00:00
#SBATCH -o logs/a3_%j.out
#SBATCH -e logs/a3_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"

# TODO: load your site's Python / conda
# module load miniconda3
# source activate transferbo

mkdir -p logs results/external_edbo_suzuki_a3

export PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:$PYTHONPATH}"

WORKERS="${WORKERS:-$SLURM_CPUS_PER_TASK}"

echo "host=$(hostname) workers=${WORKERS} start=$(date -Is)"
python scripts/run_transfer_grid.py \
  --config configs/transfer_grid_edbo_suzuki_a3.yaml \
  --skip-existing \
  --workers "${WORKERS}"
echo "done=$(date -Is)"
