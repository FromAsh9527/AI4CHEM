#!/bin/bash
# dsub shards for suzuki_v1 full LOSO (360 jobs)
#
#   bash scripts/hpc/submit_suzuki_v1_full_dsub.sh
#   DRY_RUN=1 bash scripts/hpc/submit_suzuki_v1_full_dsub.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

N_SHARDS="${N_SHARDS:-5}"
JOB_CPU="${JOB_CPU:-16}"
JOB_MEM_MB="${JOB_MEM_MB:-32768}"
JOB_R_EXTRA=";mem=${JOB_MEM_MB}"
ACCOUNT="${ACCOUNT:-root.jincjjszxyxgsiAT79}"
DRY_RUN="${DRY_RUN:-0}"

CONDA_SH="${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"
if [[ ! -f "$CONDA_SH" ]]; then
  echo "[ERROR] conda not found: $CONDA_SH"
  exit 1
fi

mkdir -p logs/dsub scripts/hpc/dsub_jobs results/suzuki_v1_full

echo "[INFO] root=$ROOT shards=$N_SHARDS cpu=$JOB_CPU mem_mb=$JOB_MEM_MB"
echo "[INFO] target JSON: 360 under results/suzuki_v1_full/"

for sid in $(seq 0 $((N_SHARDS - 1))); do
  job="scripts/hpc/dsub_jobs/suz_v1_full_shard_${sid}.sh"
  out="logs/dsub/suz_v1_full_shard_${sid}.out"
  err="logs/dsub/suz_v1_full_shard_${sid}.err"
  cat > "$job" <<EOF
#!/bin/bash
#DSUB -n tb2sf${sid}
#DSUB -N 1
#DSUB -A ${ACCOUNT}
#DSUB -R cpu=${JOB_CPU}${JOB_R_EXTRA}
#DSUB -oo ${ROOT}/${out}
#DSUB -eo ${ROOT}/${err}

set -euo pipefail
echo "[INFO] host=\$(hostname) date=\$(date) shard=${sid}/${N_SHARDS}"
cd "${ROOT}"
source "${CONDA_SH}"
conda activate base
export PYTHONWARNINGS=ignore
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="${ROOT}/src\${PYTHONPATH:+:\$PYTHONPATH}"

python scripts/hpc/run_suzuki_v1_full_shard.py \\
  --shard-id ${sid} \\
  --n-shards ${N_SHARDS} \\
  --workers ${JOB_CPU}

echo "[INFO] done date=\$(date)"
EOF
  chmod 755 "$job"

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "[DRY] would: dsub -s $job"
  else
    echo "[SUBMIT] shard $sid"
    dsub -s "$job"
  fi
done

echo "[INFO] progress:"
echo "  find results/suzuki_v1_full -name '*.json' ! -name 'loso_records.json' | wc -l"
echo "  # target 360"
