#!/usr/bin/env bash
set -euo pipefail

PROFILE_PATH="profiles/paper_eval.yaml"
OUTPUT_DIR="build/eval/ablation"

mkdir -p "$OUTPUT_DIR"
python -m benchmarks.run_eval \
  --profile-file "$PROFILE_PATH" \
  --suite ablation \
  --output-dir "$OUTPUT_DIR"
