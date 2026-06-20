#!/usr/bin/env bash
set -euo pipefail

PROFILE_PATH="profiles/paper_eval.yaml"
EVAL_DIR="build/eval"
OUT_DIR="build/eval/tables"

# PROFILE_PATH is kept explicit so all paper scripts name the reproducible profile.
test -n "$PROFILE_PATH"
mkdir -p "$OUT_DIR"
python -m experiments.export_tables \
  --eval-dir "$EVAL_DIR" \
  --out-dir "$OUT_DIR"
