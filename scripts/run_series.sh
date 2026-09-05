#!/usr/bin/env bash
# run_series.sh —— 按顺序跑多组实验(每组一个变量),每组跑完立刻 analyze。
# 用法:nohup scripts/run_series.sh > runs/series.log 2>&1 &
# 改下面的 SERIES 数组即可。每行:<outdir名>|<tag>|<run_eval 参数...>
set -u
cd "$(dirname "$0")/.."

SERIES=(
  "exp_toolshim_qwen3-14b|toolshim mistral-nemo, model qwen3:14b-16k|--model qwen3:14b-16k --env GOOSE_TOOLSHIM=true --env GOOSE_TOOLSHIM_OLLAMA_MODEL=mistral-nemo --timeout 900"
  "exp_qwen2.5-coder-14b|model=qwen2.5-coder:14b-16k|--model qwen2.5-coder:14b-16k"
  "exp_qwen3-8b-32k|model=qwen3:8b-32k control|--model qwen3:8b-32k"
)

for entry in "${SERIES[@]}"; do
  IFS='|' read -r name tag extra <<<"$entry"
  echo "################ $(date '+%F %T')  START $name  ($tag)"
  # shellcheck disable=SC2086
  python3 scripts/run_eval.py --repeat 3 --tag "$tag" --outdir "runs/$name" $extra
  echo "################ $(date '+%F %T')  DONE  $name"
  python3 scripts/analyze.py "runs/$name" --verbose > "runs/$name/_analysis.txt" 2>&1
  tail -n +1 "runs/$name/_analysis.txt" | grep -E "指标 1|指标 2|主瓶颈|环[0-9] " || true
  ollama stop "$(python3 -c "import json;print(json.load(open('runs/$name/_meta.json'))['model'])")" 2>/dev/null || true
done
echo "################ $(date '+%F %T')  ALL DONE"
