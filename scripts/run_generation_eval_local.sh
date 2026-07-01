#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/bin:/bin:$PATH"

OUT_DIR="build/downstream_eval/generation/local"
RAG_DB="${RAG_DB_PATH:-build/rag.db}"
TOPK="3"
MAX_CASES=""
INCLUDE_EXTENSION="0"
MODEL_PATH="${LOCAL_LLM_MODEL_PATH:-models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf}"

usage() {
  cat <<'EOF'
Usage: scripts/run_generation_eval_local.sh [--out-dir DIR] [--rag-db PATH] [--topk N] [--max-cases N] [--include-extension]

Runs local GGUF downstream generation for:
  systems: vanilla-rag, rair-rag
  generator: local-llm
  default dataset: rair_test

Options:
  --out-dir DIR          Output directory for generation outputs and summaries.
  --rag-db PATH          Path to rag.db.
  --topk N               Retrieval top-k.
  --max-cases N          Limit cases for smoke tests.
  --include-extension    Also run rair_test_multi_intent_negation.
  -h, --help             Show this help.
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
    --max-cases)
      MAX_CASES="$2"
      shift 2
      ;;
    --include-extension)
      INCLUDE_EXTENSION="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[generation-local] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$OUT_DIR"
args=(
  run
  python
  -m
  benchmarks.rair_rag.downstream.generation_matrix
  --generator
  local-llm
  --data
  benchmarks/rair_rag/data/test/rair_test.jsonl
  --rag-db
  "$RAG_DB"
  --topk
  "$TOPK"
  --out-dir
  "$OUT_DIR"
)

if [[ -n "$MAX_CASES" ]]; then
  args+=(--max-cases "$MAX_CASES")
fi

if [[ "$INCLUDE_EXTENSION" == "1" ]]; then
  args+=(--include-extension)
fi

echo "[generation-local] uv run python -m benchmarks.rair_rag.downstream.generation_matrix --generator local-llm"
uv "${args[@]}"
