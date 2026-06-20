#!/usr/bin/env bash
set -euo pipefail

PROFILE_PATH="profiles/paper_eval.yaml"
OUTPUT_DIR="build/eval/ablation"
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

mkdir -p "$OUTPUT_DIR"
for ablation in "${ABLATIONS[@]}"; do
  python -m benchmarks.run_eval \
    --profile-file "$PROFILE_PATH" \
    --suite ablation \
    --method hsc-rag-de \
    --ablation "$ablation" \
    --data benchmarks/data/robustness_dev.jsonl \
    --out "$OUTPUT_DIR/${ablation}_predictions.jsonl" \
    --summary "$OUTPUT_DIR/${ablation}_summary.csv"
done
