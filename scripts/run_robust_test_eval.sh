#!/usr/bin/env bash
set -euo pipefail

PROFILE_PATH="profiles/paper_eval.yaml"
DATA_PATH="benchmarks/data/robustness_test.jsonl"
OUTPUT_DIR="build/eval/test/robust"
PYTHON_BIN="${PYTHON_BIN:-}"
METHODS=(
  "vanilla-rag"
  "rag-guard"
  "hsc-rag-manual"
  "hsc-rag-de"
)

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/Scripts/python.exe" ]]; then
    PYTHON_BIN=".venv/Scripts/python.exe"
  else
    PYTHON_BIN="python"
  fi
fi

echo "[robust-test] profile: $PROFILE_PATH"
echo "[robust-test] data: $DATA_PATH"
echo "[robust-test] output: $OUTPUT_DIR"
echo "[robust-test] python: $PYTHON_BIN"
mkdir -p "$OUTPUT_DIR"

for method in "${METHODS[@]}"; do
  echo "[robust-test] running method: $method"
  "$PYTHON_BIN" -m benchmarks.run_eval \
    --profile-file "$PROFILE_PATH" \
    --suite robust \
    --method "$method" \
    --data "$DATA_PATH" \
    --out "$OUTPUT_DIR/${method}_predictions.jsonl" \
    --summary "$OUTPUT_DIR/${method}_summary.csv"
done

echo "[robust-test] done"
