#!/bin/bash
# dsub 分片提交 amination_v1 full LOSO（与 TransferBO A3/amination 同款调度）
#
# 用法（在超算 ~/TransferBO2.0 下）:
#   bash scripts/hpc/submit_amination_v1_full_dsub.sh
#   DRY_RUN=1 bash scripts/hpc/submit_amination_v1_full_dsub.sh
#
# 可调:
#   N_SHARDS=5 JOB_CPU=16 JOB_MEM_MB=32768 ACCOUNT=...

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

mkdir -p logs/dsub scripts/hpc/dsub_jobs results/amination_v1_full

echo "[INFO] root=$ROOT shards=$N_SHARDS cpu=$JOB_CPU mem_mb=$JOB_MEM_MB"
echo "[INFO] target JSON: 450 under results/amination_v1_full/"

for sid in $(seq 0 $((N_SHARDS - 1))); do
  job="scripts/hpc/dsub_jobs/amin_v1_full_shard_${sid}.sh"
  out="logs/dsub/amin_v1_full_shard_${sid}.out"
  err="logs/dsub/amin_v1_full_shard_${sid}.err"
  cat > "$job" <<EOF
#!/bin/bash
#DSUB -n tb2af${sid}
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

python scripts/hpc/run_amination_v1_full_shard.py \\
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

echo "[INFO] all submitted (or dry-run). 查进度:"
echo "  find results/amination_v1_full -name '*.json' ! -name 'loso_records.json' | wc -l"
echo "  # 目标 450"
echo "汇总:"
echo "  python scripts/run_loso.py --config configs/amination_exp_v1_full.yaml --rebuild-only"
echo "  python scripts/summarize_results.py --summary-csv results/amination_v1_full/loso_summary.csv"
