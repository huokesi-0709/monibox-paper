#!/usr/bin/env bash
set -euo pipefail

PROFILE_PATH="profiles/paper_eval.yaml"
OUTPUT_DIR="build/eval/clean"
METHODS=(
  "rule-only"
  "vanilla-rag"
  "rag-guard"
  "hsc-rag-manual"
  "hsc-rag-de"
)

mkdir -p "$OUTPUT_DIR"
for method in "${METHODS[@]}"; do
  python -m benchmarks.run_eval \
    --profile-file "$PROFILE_PATH" \
    --suite clean \
    --method "$method" \
    --data benchmarks/data/clean_dev.jsonl \
    --out "$OUTPUT_DIR/${method}_predictions.jsonl" \
    --summary "$OUTPUT_DIR/${method}_summary.csv"
done
