#!/usr/bin/env bash
set -euo pipefail

FORCE=0
if [[ "${1:-}" == "--force" ]]; then
  FORCE=1
elif [[ $# -gt 0 ]]; then
  echo "[final_v2_de_multiseed][ERROR] unknown argument: $1" >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-}"
PROFILE="paper_eval"
BASE_DIR="build/eval/final_v2/de_multiseed"
LOG_DIR="build/eval/final_v2/run_logs"
SEEDS=(7 21 42 2024 2026)

if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/Scripts/python.exe" ]]; then
    PYTHON_BIN=".venv/Scripts/python.exe"
  else
    PYTHON_BIN="python"
  fi
fi

mkdir -p "$BASE_DIR" "$LOG_DIR"

echo "[final_v2_de_multiseed] output: $BASE_DIR"
echo "[final_v2_de_multiseed] python: $PYTHON_BIN"

for seed in "${SEEDS[@]}"; do
  seed_dir="$BASE_DIR/seed_${seed}"
  config="$seed_dir/de_hsc_rag_seed_${seed}.yaml"
  policy="$seed_dir/policy_de_seed_${seed}.json"
  metrics="$seed_dir/de_best_metrics.json"
  trials="$seed_dir/de_trials.csv"
  curve="$seed_dir/de_curve.csv"
  work_dir="$seed_dir/work"
  log="$LOG_DIR/de_seed_${seed}.log"
  mkdir -p "$seed_dir"

  if [[ -f "$metrics" && -f "$policy" && "$FORCE" -ne 1 ]]; then
    echo "[final_v2_de_multiseed] skip existing seed=$seed"
    continue
  fi

  cat > "$config" <<EOF
seed: $seed
n_eval: 160
pop_size: 32
variant: "DE/rand/1/bin"
CR: 0.7
dither: "vector"
jitter: false
latency_budget_ms: 2000
profile: "$PROFILE"
method: "hsc-rag-de"
clean_dev_path: "benchmarks/data_v2/clean_dev.jsonl"
robustness_dev_path: "benchmarks/data_v2/robustness_dev.jsonl"
search_space_path: "scoring/search_space.json"
template_policy_path: "scoring/policy_manual.json"
output_policy_path: "$policy"
trials_path: "$trials"
best_metrics_path: "$metrics"
curve_path: "$curve"
work_dir: "$work_dir"
EOF

  start_epoch="$(date +%s)"
  start_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "[final_v2_de_multiseed] start seed=$seed at $start_iso"
  "$PYTHON_BIN" -m experiments.de_pymoo_optimize --config "$config" 2>&1 | tee "$log"
  end_epoch="$(date +%s)"
  end_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  elapsed="$((end_epoch - start_epoch))"
  echo "[final_v2_de_multiseed] done seed=$seed at $end_iso elapsed=${elapsed}s"
done

"$PYTHON_BIN" -m experiments.export_final_v2_statistics --only-de-multiseed

echo "[final_v2_de_multiseed] done"
