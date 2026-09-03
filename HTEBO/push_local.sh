#!/usr/bin/env bash
# 在本机 AI4CHEM 仓库根目录执行: bash HTEBO/push_local.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "=== AI4CHEM 本机 push HTEBO ==="
echo "当前目录: $ROOT"
git status -sb
echo
echo "将添加 HTEBO/ 下所有未忽略文件..."
git add HTEBO/
git status -sb
echo
MSG="${1:-HTEBO: 同步本机开题与材料}"
if git diff --cached --quiet; then
  echo "没有新改动需要提交，尝试直接 push..."
else
  git commit -m "$MSG"
fi
BR="$(git branch --show-current)"
echo
echo "推送到 origin/$BR ..."
git push -u origin "$BR"
echo "完成。"
