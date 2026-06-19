#!/usr/bin/env bash
set -euo pipefail

PROFILE_PATH="profiles/paper_eval.yaml"
OUTPUT_DIR="build/eval/clean"

mkdir -p "$OUTPUT_DIR"
python -m benchmarks.run_eval \
  --profile-file "$PROFILE_PATH" \
  --suite clean \
  --output-dir "$OUTPUT_DIR"
