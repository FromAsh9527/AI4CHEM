#!/bin/bash
# 按 DFT 指南同款：dsub 分片提交 A3（多中心调度）
#
# 用法（在超算 ~/TransferBO 下）:
#   bash scripts/hpc/submit_a3_dsub.sh
#
# 可调环境变量:
#   N_SHARDS=20      # 分片数（默认 20=每种 seed 一片）
#   JOB_CPU=32       # 每作业申请核数 = workers
#   JOB_MEM_MB=65536 # 内存 MB（约 64G）
#   DRY_RUN=1        # 只生成脚本不提交

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

N_SHARDS="${N_SHARDS:-20}"
JOB_CPU="${JOB_CPU:-32}"
JOB_MEM_MB="${JOB_MEM_MB:-65536}"
JOB_R_EXTRA=";mem=${JOB_MEM_MB}"
ACCOUNT="${ACCOUNT:-root.jincjjszxyxgsiAT79}"
DRY_RUN="${DRY_RUN:-0}"

CONDA_SH="${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"
if [[ ! -f "$CONDA_SH" ]]; then
  echo "[ERROR] conda not found: $CONDA_SH"
  exit 1
fi

mkdir -p logs/dsub scripts/hpc/dsub_jobs

echo "[INFO] root=$ROOT shards=$N_SHARDS cpu=$JOB_CPU mem_mb=$JOB_MEM_MB"
echo "[INFO] tip: 提交前建议先停掉 cli 上的 nohup，避免与分片抢写同一 JSON"
echo "       pkill -f 'run_transfer_grid.py.*edbo_suzuki_a3' || true"

for sid in $(seq 0 $((N_SHARDS - 1))); do
  job="scripts/hpc/dsub_jobs/a3_shard_${sid}.sh"
  out="logs/dsub/a3_shard_${sid}.out"
  err="logs/dsub/a3_shard_${sid}.err"
  cat > "$job" <<EOF
#!/bin/bash
#DSUB -n a3s${sid}
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

python scripts/hpc/run_a3_shard.py \\
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
echo "  ls results/external_edbo_suzuki_a3/*.json | wc -l"
echo "  # 目标 6720"
