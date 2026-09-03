# amination_v1 full LOSO — single-node Slurm
#   sbatch scripts/hpc/run_amination_v1_full_slurm.sh

#SBATCH -J tb2_amin
#SBATCH -p cpu
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH -t 24:00:00
#SBATCH -o logs/amin_v1_full_%j.out
#SBATCH -e logs/amin_v1_full_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"
mkdir -p logs results/amination_v1_full

export PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:$PYTHONPATH}"

WORKERS="${WORKERS:-$SLURM_CPUS_PER_TASK}"

echo "host=$(hostname) workers=${WORKERS} start=$(date -Is)"
python scripts/run_loso.py \
  --config configs/amination_exp_v1_full.yaml \
  --skip-existing \
  --workers "${WORKERS}"
echo "done=$(date -Is)"
