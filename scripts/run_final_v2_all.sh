#!/usr/bin/env bash
set -euo pipefail

FORCE_ARG=""
if [[ "${1:-}" == "--force" ]]; then
  FORCE_ARG="--force"
elif [[ $# -gt 0 ]]; then
  echo "[final_v2_all][ERROR] unknown argument: $1" >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/Scripts/python.exe" ]]; then
    PYTHON_BIN=".venv/Scripts/python.exe"
  else
    PYTHON_BIN="python"
  fi
fi

mkdir -p "build/eval/final_v2/run_logs"

echo "[final_v2_all] step 1/9 audit dataset"
"$PYTHON_BIN" -m benchmarks.audit_dataset_v2

echo "[final_v2_all] step 2/9 DE multiseed"
bash scripts/run_final_v2_de_multiseed.sh $FORCE_ARG

echo "[final_v2_all] step 3/9 clean test eval"
bash scripts/run_final_v2_clean_eval.sh $FORCE_ARG

echo "[final_v2_all] step 4/9 robust test eval"
bash scripts/run_final_v2_robust_eval.sh $FORCE_ARG

echo "[final_v2_all] step 5/9 ablation eval"
bash scripts/run_final_v2_ablation.sh $FORCE_ARG

echo "[final_v2_all] step 6/9 export statistics"
"$PYTHON_BIN" -m experiments.export_final_v2_statistics

echo "[final_v2_all] step 7/9 export tables"
"$PYTHON_BIN" -m experiments.export_final_v2_tables

echo "[final_v2_all] step 8/9 export cases"
"$PYTHON_BIN" -m experiments.export_final_v2_cases

echo "[final_v2_all] step 9/9 export manifest"
"$PYTHON_BIN" -m experiments.export_final_v2_manifest

echo "[final_v2_all] done: build/eval/final_v2/final_run_manifest.json"
