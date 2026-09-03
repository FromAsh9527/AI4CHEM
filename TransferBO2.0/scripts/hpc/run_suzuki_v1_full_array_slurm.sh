#SBATCH -J tb2_suz_arr
#SBATCH -p cpu
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH -t 12:00:00
#SBATCH -a 0-4
#SBATCH -o logs/suz_v1_full_arr_%A_%a.out
#SBATCH -e logs/suz_v1_full_arr_%A_%a.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"
mkdir -p logs results/suzuki_v1_full

export PYTHONWARNINGS=ignore OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:$PYTHONPATH}"

python scripts/hpc/run_suzuki_v1_full_shard.py \
  --shard-id "${SLURM_ARRAY_TASK_ID}" \
  --n-shards 5 \
  --workers "${SLURM_CPUS_PER_TASK}"
