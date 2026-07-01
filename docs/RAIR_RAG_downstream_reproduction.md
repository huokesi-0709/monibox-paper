# RAIR-RAG downstream reproduction

This document records the downstream retrieval and generation experiments layered on top of the frozen RAIR routing benchmark.

## Retrieval experiments

Run the retrieval-only comparison:

```bash
scripts/run_downstream_retrieval_eval.sh
```

On Windows PowerShell:

```powershell
.\scripts\run_downstream_retrieval_eval.ps1
```

The retrieval scripts compare `vanilla-rag`, `keyword-rag`, `bert-rag`, and `rair-rag` on the default `rair_test` dataset and the `rair_test_multi_intent_negation` extension stress test. Outputs are written under `build/downstream_eval/retrieval/` and do not overwrite `build/rair_eval/`.

## LLM generation matrix

The final generation matrix contains four settings:

| Setting | System | Generator |
| --- | --- | --- |
| Edge-local | Vanilla RAG + LLM | Qwen1.5-0.5B-Chat-Q4_K_M |
| Edge-local | RAIR-RAG + LLM | Qwen1.5-0.5B-Chat-Q4_K_M |
| Strong reference | Vanilla RAG + LLM | Qwen2.5-7B-Instruct |
| Strong reference | RAIR-RAG + LLM | Qwen2.5-7B-Instruct |

The claim is not that the 0.5B local model matches the 7B reference model in language ability. The intended comparison is whether RAIR-RAG's structured risk context narrows the safety-critical metric gap between an edge-local generator and a stronger generator running ordinary RAG.

## Local generation

Run local GGUF generation:

```bash
scripts/run_generation_eval_local.sh
```

On Windows PowerShell:

```powershell
.\scripts\run_generation_eval_local.ps1
```

The local script runs:

- `vanilla-rag + local-llm`
- `rair-rag + local-llm`

Defaults:

- dataset: `benchmarks/rair_rag/data/test/rair_test.jsonl`
- top-k evidence: `3`
- output directory: `build/downstream_eval/generation/local/`
- model path: `models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf`, or `LOCAL_LLM_MODEL_PATH`

Use `--max-cases N` in bash or `-MaxCases N` in PowerShell for smoke tests.

## Strong reference generation

Run stronger reference generation:

```bash
export REFERENCE_LLM_API_KEY="..."
scripts/run_generation_eval_reference.sh
```

On Windows PowerShell:

```powershell
$env:REFERENCE_LLM_API_KEY = "..."
.\scripts\run_generation_eval_reference.ps1
```

The reference script runs:

- `vanilla-rag + reference-llm`
- `rair-rag + reference-llm`

Defaults:

- dataset: `benchmarks/rair_rag/data/test/rair_test.jsonl`
- top-k evidence: `3`
- output directory: `build/downstream_eval/generation/reference/`
- base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- model: `qwen2.5-7b-instruct`

`reference-llm` requires `REFERENCE_LLM_API_KEY` and is not part of the default offline reproduction path. It is a stronger reference generator only; it is not the paper's edge deployment model and is not part of the RAIR method itself. Do not commit API keys or generated secrets.

Use `--max-cases N` in bash or `-MaxCases N` in PowerShell for small smoke tests before running the full dataset.
