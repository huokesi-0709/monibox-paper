#!/usr/bin/env bash
set -euo pipefail

PROFILE_PATH="profiles/paper_eval.yaml"
DATA_PATH="benchmarks/data/robustness_test.jsonl"
OUTPUT_DIR="build/eval/test/ablation"
PYTHON_BIN="${PYTHON_BIN:-}"
ABLATIONS=(
  "without_input_normalization"
  "without_multi_intent"
  "without_negation"
  "without_protocol_gate"
  "without_safety_rerank"
  "without_low_evidence"
  "without_guard"
  "without_de_optimization"
)

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/Scripts/python.exe" ]]; then
    PYTHON_BIN=".venv/Scripts/python.exe"
  else
    PYTHON_BIN="python"
  fi
fi

echo "[test-ablation] profile: $PROFILE_PATH"
echo "[test-ablation] data: $DATA_PATH"
echo "[test-ablation] output: $OUTPUT_DIR"
echo "[test-ablation] python: $PYTHON_BIN"
mkdir -p "$OUTPUT_DIR"

for ablation in "${ABLATIONS[@]}"; do
  echo "[test-ablation] running ablation: $ablation"
  "$PYTHON_BIN" -m benchmarks.run_eval \
    --profile-file "$PROFILE_PATH" \
    --suite ablation \
    --method hsc-rag-de \
    --ablation "$ablation" \
    --data "$DATA_PATH" \
    --out "$OUTPUT_DIR/${ablation}_predictions.jsonl" \
    --summary "$OUTPUT_DIR/${ablation}_summary.csv"
done

echo "[test-ablation] done"
