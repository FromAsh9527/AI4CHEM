#SBATCH -J edbo_a3_arr
#SBATCH -p cpu                 # TODO
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8      # workers per shard
#SBATCH -t 24:00:00
#SBATCH -a 0-19                # one shard per seed 0..19
#SBATCH -o logs/a3_arr_%A_%a.out
#SBATCH -e logs/a3_arr_%A_%a.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"
# module load miniconda3 && source activate transferbo
mkdir -p logs

export PYTHONWARNINGS=ignore OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${PWD}/src${PYTHONPATH:+:$PYTHONPATH}"

python scripts/hpc/run_a3_shard.py \
  --shard-id "${SLURM_ARRAY_TASK_ID}" \
  --n-shards 20 \
  --workers "${SLURM_CPUS_PER_TASK}"
