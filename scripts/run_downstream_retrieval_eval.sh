#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/bin:/bin:$PATH"

OUT_DIR="build/downstream_eval/retrieval"
RAG_DB="${RAG_DB_PATH:-build/rag.db}"
TOPK="3"

usage() {
  cat <<'EOF'
Usage: scripts/run_downstream_retrieval_eval.sh [--out-dir DIR] [--rag-db PATH] [--topk N]

Runs RAIR-RAG downstream retrieval evaluation for:
  datasets: rair_test, rair_test_multi_intent_negation
  systems:  vanilla-rag, keyword-rag, bert-rag, rair-rag

Options:
  --out-dir DIR   Output directory for predictions and summaries.
  --rag-db PATH   Path to rag.db.
  --topk N        Retrieval top-k.
  -h, --help      Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --rag-db)
      RAG_DB="$2"
      shift 2
      ;;
    --topk)
      TOPK="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[downstream-retrieval] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$RAG_DB" ]]; then
  echo "[downstream-retrieval] RAG database not found: $RAG_DB" >&2
  echo "[downstream-retrieval] Please run 'uv run monibox-build-rag' first, or pass --rag-db / set RAG_DB_PATH." >&2
  exit 2
fi

mkdir -p "$OUT_DIR"

run_eval() {
  local dataset_name="$1"
  local data_path="$2"
  local system="$3"
  local out_path="$OUT_DIR/${dataset_name}_${system}_predictions.jsonl"
  local summary_path="$OUT_DIR/${dataset_name}_${system}_summary.json"

  echo "[downstream-retrieval] dataset=${dataset_name} system=${system} topk=${TOPK}"
  uv run python -m benchmarks.rair_rag.downstream.retrieval_eval \
    --data "$data_path" \
    --system "$system" \
    --rag-db "$RAG_DB" \
    --topk "$TOPK" \
    --out "$out_path" \
    --summary "$summary_path"
}

run_dataset() {
  local dataset_name="$1"
  local data_path="$2"

  run_eval "$dataset_name" "$data_path" "vanilla-rag"
  run_eval "$dataset_name" "$data_path" "keyword-rag"
  run_eval "$dataset_name" "$data_path" "bert-rag"
  run_eval "$dataset_name" "$data_path" "rair-rag"
}

run_dataset "rair_test" "benchmarks/rair_rag/data/test/rair_test.jsonl"
run_dataset "rair_test_multi_intent_negation" "benchmarks/rair_rag/data/test/rair_test_multi_intent_negation.jsonl"

echo "[downstream-retrieval] done: $OUT_DIR"
