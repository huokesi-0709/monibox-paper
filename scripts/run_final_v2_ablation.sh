#!/usr/bin/env bash
set -euo pipefail

FORCE=0
if [[ "${1:-}" == "--force" ]]; then
  FORCE=1
elif [[ $# -gt 0 ]]; then
  echo "[final_v2_ablation][ERROR] unknown argument: $1" >&2
  exit 2
fi

PROFILE_PATH="profiles/paper_eval.yaml"
DATA_PATH="benchmarks/data_v2/robustness_test.jsonl"
OUTPUT_DIR="build/eval/final_v2/ablation"
LOG_DIR="build/eval/final_v2/run_logs"
FINAL_DE_POLICY="${FINAL_DE_POLICY:-build/eval/final_v2/de_multiseed/seed_42/policy_de_seed_42.json}"
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

mkdir -p "$OUTPUT_DIR" "$LOG_DIR"

echo "[final_v2_ablation] profile: $PROFILE_PATH"
echo "[final_v2_ablation] data: $DATA_PATH"
echo "[final_v2_ablation] output: $OUTPUT_DIR"
echo "[final_v2_ablation] python: $PYTHON_BIN"

for ablation in "${ABLATIONS[@]}"; do
  predictions="$OUTPUT_DIR/${ablation}_predictions.jsonl"
  summary="$OUTPUT_DIR/${ablation}_summary.json"
  log="$LOG_DIR/ablation_${ablation}.log"
  if [[ -f "$summary" && "$FORCE" -ne 1 ]]; then
    echo "[final_v2_ablation] skip existing summary: $summary"
    continue
  fi

  start_epoch="$(date +%s)"
  start_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[final_v2_ablation] start ablation=$ablation at $start_iso"
  policy_args=()
  if [[ "$ablation" != "without_de_optimization" && -f "$FINAL_DE_POLICY" ]]; then
    policy_args=(--policy "$FINAL_DE_POLICY")
    echo "[final_v2_ablation] ablation=$ablation policy=$FINAL_DE_POLICY"
  fi
  "$PYTHON_BIN" -m benchmarks.run_eval \
    --profile-file "$PROFILE_PATH" \
    --suite ablation \
    --method hsc-rag-de \
    --ablation "$ablation" \
    "${policy_args[@]}" \
    --data "$DATA_PATH" \
    --out "$predictions" \
    --summary "$summary" 2>&1 | tee "$log"
  end_epoch="$(date +%s)"
  end_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  elapsed="$((end_epoch - start_epoch))"
  echo "[final_v2_ablation] done ablation=$ablation at $end_iso elapsed=${elapsed}s"
done

echo "[final_v2_ablation] done"
