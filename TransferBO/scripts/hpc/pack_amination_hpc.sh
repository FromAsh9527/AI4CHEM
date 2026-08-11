#!/usr/bin/env bash
# 在本机 TransferBO 根目录打包上传用 tarball
#   bash scripts/hpc/pack_amination_hpc.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT="${1:-transferbo_amination_hpc.tgz}"

tar -czf "$OUT" \
  configs/transfer_grid_edbo_amination_min_s0.yaml \
  configs/protocol.yaml \
  src \
  scripts/run_transfer_grid.py \
  scripts/run_experiment.py \
  scripts/summarize_amination_min_s0.py \
  scripts/hpc \
  pyproject.toml \
  requirements.txt \
  data/processed/edbo_amination_plates.csv \
  data/descriptors/edbo_amination_condition_dft.csv

echo "[OK] wrote $OUT"
ls -lh "$OUT"
echo "scp $OUT user@hpc:~/"
