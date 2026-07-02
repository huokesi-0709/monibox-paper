#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/bin:/bin:$PATH"

OUT_DIR="build/downstream_eval/generation/reference"
RAG_DB="${RAG_DB_PATH:-build/rag.db}"
TOPK="3"
MAX_CASES=""
INCLUDE_EXTENSION="0"
REFERENCE_BASE_URL="${REFERENCE_LLM_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
REFERENCE_PROVIDER="${REFERENCE_LLM_PROVIDER:-dashscope_openai}"
REFERENCE_MODEL="${REFERENCE_LLM_MODEL:-qwen-plus}"

usage() {
  cat <<'EOF'
Usage: scripts/run_generation_eval_reference.sh [--out-dir DIR] [--rag-db PATH] [--topk N] [--max-cases N] [--include-extension]

Runs stronger reference downstream generation for:
  systems: vanilla-rag, rair-rag
  generator: reference-llm
  default dataset: rair_test

Required environment:
  REFERENCE_LLM_API_KEY    API key for the OpenAI-compatible reference endpoint.

Optional environment:
  REFERENCE_LLM_PROVIDER   Defaults to dashscope_openai
  REFERENCE_LLM_BASE_URL   Defaults to https://dashscope.aliyuncs.com/compatible-mode/v1
  REFERENCE_LLM_MODEL      Defaults to qwen-plus

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
      echo "[generation-reference] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -f "$RAG_DB" ]]; then
  echo "[generation-reference] RAG database not found: $RAG_DB" >&2
  echo "[generation-reference] Please run 'uv run monibox-build-rag' first, or pass --rag-db / set RAG_DB_PATH." >&2
  exit 2
fi

mkdir -p "$OUT_DIR"
if [[ -z "${REFERENCE_LLM_API_KEY:-}" ]]; then
  echo "[generation-reference] REFERENCE_LLM_API_KEY is not set." >&2
  echo "[generation-reference] Export it in your shell before running this script. Do not commit API keys." >&2
  exit 2
fi

export REFERENCE_LLM_BASE_URL="$REFERENCE_BASE_URL"
export REFERENCE_LLM_PROVIDER="$REFERENCE_PROVIDER"
export REFERENCE_LLM_MODEL="$REFERENCE_MODEL"

args=(
  run
  python
  -m
  benchmarks.rair_rag.downstream.generation_matrix
  --generator
  reference-llm
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

echo "[generation-reference] uv run python -m benchmarks.rair_rag.downstream.generation_matrix --generator reference-llm model=${REFERENCE_MODEL}"
uv "${args[@]}"
