#SBATCH -J edbo_amin_arr
#SBATCH -p cpu                 # TODO
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH -t 24:00:00
#SBATCH -a 0-19
#SBATCH -o logs/amin_arr_%A_%a.out
#SBATCH -e logs/amin_arr_%A_%a.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"
mkdir -p logs results/external_edbo_amination_min_s0

export PYTHONWARNINGS=ignore OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:$PYTHONPATH}"

python scripts/hpc/run_amination_shard.py \
  --shard-id "${SLURM_ARRAY_TASK_ID}" \
  --n-shards 20 \
  --workers "${SLURM_CPUS_PER_TASK}"
