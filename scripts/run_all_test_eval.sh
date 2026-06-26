#!/usr/bin/env bash
set -euo pipefail

EVAL_DIR="build/eval/test"
TABLE_DIR="$EVAL_DIR/tables"
CASE_DIR="$EVAL_DIR/cases"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/Scripts/python.exe" ]]; then
    PYTHON_BIN=".venv/Scripts/python.exe"
  else
    PYTHON_BIN="python"
  fi
fi

export PYTHON_BIN
echo "[all-test] python: $PYTHON_BIN"

echo "[all-test] step 1/6: dataset audit"
"$PYTHON_BIN" -m benchmarks.audit_dataset

echo "[all-test] step 2/6: clean test evaluation"
bash scripts/run_clean_test_eval.sh

echo "[all-test] step 3/6: robust test evaluation"
bash scripts/run_robust_test_eval.sh

echo "[all-test] step 4/6: test ablation"
bash scripts/run_test_ablation.sh

echo "[all-test] step 5/6: export paper tables"
if [[ -f "experiments/export_paper_tables.py" ]]; then
  "$PYTHON_BIN" -m experiments.export_paper_tables --eval-dir "$EVAL_DIR" --out-dir "$TABLE_DIR"
else
  echo "[all-test] TODO: experiments/export_paper_tables.py not found; table export will be added in a later task."
fi

echo "[all-test] step 6/6: export selected cases"
if [[ -f "experiments/export_selected_cases.py" ]]; then
  "$PYTHON_BIN" -m experiments.export_selected_cases --eval-dir "$EVAL_DIR" --out-dir "$CASE_DIR"
else
  echo "[all-test] TODO: experiments/export_selected_cases.py not found; case export will be added in a later task."
fi

echo "[all-test] done"
