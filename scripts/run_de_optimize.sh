#!/usr/bin/env bash
set -euo pipefail

PROFILE_PATH="profiles/paper_eval.yaml"
OUTPUT_DIR="build/eval/de"

mkdir -p "$OUTPUT_DIR"
python -m experiments.de_pymoo_optimize \
  --profile-file "$PROFILE_PATH" \
  --output-dir "$OUTPUT_DIR"
