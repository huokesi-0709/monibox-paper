#!/usr/bin/env bash
set -euo pipefail

python -m benchmarks.generate_robustness \
  --input benchmarks/data/clean_dev.jsonl \
  --output benchmarks/data/robustness_dev.jsonl \
  --seed 42 \
  --max-per-case 3
