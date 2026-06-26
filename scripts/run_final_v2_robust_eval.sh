#!/usr/bin/env bash
set -euo pipefail

FORCE=0
if [[ "${1:-}" == "--force" ]]; then
  FORCE=1
elif [[ $# -gt 0 ]]; then
  echo "[final_v2_robust][ERROR] unknown argument: $1" >&2
  exit 2
fi

PROFILE_PATH="profiles/paper_eval.yaml"
DATA_PATH="benchmarks/data_v2/robustness_test.jsonl"
OUTPUT_DIR="build/eval/final_v2/robust"
LOG_DIR="build/eval/final_v2/run_logs"
FINAL_DE_POLICY="${FINAL_DE_POLICY:-build/eval/final_v2/de_multiseed/seed_42/policy_de_seed_42.json}"
PYTHON_BIN="${PYTHON_BIN:-}"
METHODS=(
  "vanilla-rag"
  "rag-guard"
  "hsc-rag-manual"
  "hsc-rag-de"
)

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/Scripts/python.exe" ]]; then
    PYTHON_BIN=".venv/Scripts/python.exe"
  else
    PYTHON_BIN="python"
  fi
fi

mkdir -p "$OUTPUT_DIR" "$LOG_DIR"

echo "[final_v2_robust] profile: $PROFILE_PATH"
echo "[final_v2_robust] data: $DATA_PATH"
echo "[final_v2_robust] output: $OUTPUT_DIR"
echo "[final_v2_robust] python: $PYTHON_BIN"

for method in "${METHODS[@]}"; do
  predictions="$OUTPUT_DIR/${method}_predictions.jsonl"
  summary="$OUTPUT_DIR/${method}_summary.json"
  log="$LOG_DIR/robust_${method}.log"
  if [[ -f "$summary" && "$FORCE" -ne 1 ]]; then
    echo "[final_v2_robust] skip existing summary: $summary"
    continue
  fi

  start_epoch="$(date +%s)"
  start_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[final_v2_robust] start method=$method at $start_iso"
  policy_args=()
  if [[ "$method" == "hsc-rag-de" && -f "$FINAL_DE_POLICY" ]]; then
    policy_args=(--policy "$FINAL_DE_POLICY")
    echo "[final_v2_robust] method=$method policy=$FINAL_DE_POLICY"
  fi
  "$PYTHON_BIN" -m benchmarks.run_eval \
    --profile-file "$PROFILE_PATH" \
    --suite robust \
    --method "$method" \
    "${policy_args[@]}" \
    --data "$DATA_PATH" \
    --out "$predictions" \
    --summary "$summary" 2>&1 | tee "$log"
  end_epoch="$(date +%s)"
  end_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  elapsed="$((end_epoch - start_epoch))"
  echo "[final_v2_robust] done method=$method at $end_iso elapsed=${elapsed}s"
done

echo "[final_v2_robust] done"
