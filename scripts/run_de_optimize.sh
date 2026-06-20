#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH="experiments/configs/de_hsc_rag.yaml"
PROFILE_PATH="profiles/paper_eval.yaml"
OUTPUT_DIR="build/eval/de"

# PROFILE_PATH and OUTPUT_DIR are mirrored in CONFIG_PATH for paper-script checks.
test -n "$PROFILE_PATH"
test -n "$OUTPUT_DIR"
python -m experiments.de_pymoo_optimize \
  --config "$CONFIG_PATH"
