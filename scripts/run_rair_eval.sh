#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="build/rair_eval"
MANUAL_POLICY="scoring/routing_policy_manual.yaml"

mkdir -p "$OUT_DIR"

run_eval() {
  local dataset_name="$1"
  local data_path="$2"
  local method_label="$3"
  local method="$4"
  local policy_path="${5:-}"

  local out_path="$OUT_DIR/${dataset_name}_${method_label}_predictions.jsonl"
  local summary_path="$OUT_DIR/${dataset_name}_${method_label}_summary.json"

  echo "[rair-eval] dataset=${dataset_name} method=${method_label}"
  if [[ -n "$policy_path" ]]; then
    uv run python -m benchmarks.rair_rag.run_routing_eval \
      --data "$data_path" \
      --method "$method" \
      --policy "$policy_path" \
      --out "$out_path" \
      --summary "$summary_path"
  else
    uv run python -m benchmarks.rair_rag.run_routing_eval \
      --data "$data_path" \
      --method "$method" \
      --out "$out_path" \
      --summary "$summary_path"
  fi
}

run_dataset() {
  local dataset_name="$1"
  local data_path="$2"

  run_eval "$dataset_name" "$data_path" "keyword-baseline" "keyword-baseline"
  run_eval "$dataset_name" "$data_path" "bert-multilabel" "bert-multilabel"
  run_eval "$dataset_name" "$data_path" "no-negation" "no-negation"
  run_eval "$dataset_name" "$data_path" "single-intent" "single-intent"
  run_eval "$dataset_name" "$data_path" "risk-router" "risk-router" "$MANUAL_POLICY"
}

run_dataset "rair_test" "benchmarks/rair_rag/data/test/rair_test.jsonl"
run_dataset "rair_test_negation" "benchmarks/rair_rag/data/test/rair_test_negation.jsonl"
run_dataset "rair_test_multi_intent" "benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl"
run_dataset "rair_test_multi_intent_negation" "benchmarks/rair_rag/data/test/rair_test_multi_intent_negation.jsonl"

echo "[rair-eval] done: $OUT_DIR"
