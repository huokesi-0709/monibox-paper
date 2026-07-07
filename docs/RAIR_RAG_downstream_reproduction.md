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
| Strong reference | Vanilla RAG + LLM | qwen-plus |
| Strong reference | RAIR-RAG + LLM | qwen-plus |

The claim is not that the 0.5B local model matches qwen-plus in language ability. The intended comparison is whether RAIR-RAG's structured risk context narrows the safety-critical metric gap between an edge-local generator and a stronger hosted reference generator running ordinary RAG.

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
- model: `qwen-plus`

`reference-llm` requires `REFERENCE_LLM_API_KEY` and is not part of the default offline reproduction path. qwen-plus is used as a stronger hosted reference generator, not as an edge deployment model. Do not commit API keys or generated secrets.

Use `--max-cases N` in bash or `-MaxCases N` in PowerShell for small smoke tests before running the full dataset.

## Strong reference latency subset

The completed `qwen-plus` reference generation outputs may predate per-sample latency logging. To avoid rerunning the full reference content generation, use a stratified subset benchmark for latency measurement:

```bash
export REFERENCE_LLM_API_KEY="..."
uv run python -m benchmarks.rair_rag.downstream.run_generation_latency_subset \
  --generator reference-llm \
  --systems vanilla-rag rair-rag \
  --sample-per-perturbation 20
```

Outputs are written under `build/downstream_eval/generation/reference_latency_subset/`. These measurements are subset latency measurements for `qwen-plus`; they are not full 480-case content-generation latency measurements.

The paper-level latency table is exported to:

- `build/downstream_eval/tables/generation_latency_subset_results.md`
- `build/downstream_eval/tables/generation_latency_subset_results.csv`

Do not use `build/downstream_eval/tables/generation_latency_results.md` as the paper-level latency result; that table is retained only as a deprecated legacy export.

## Local LLM diagnostic status

The earlier local 0.5B path moved from a pre-repair `empty_generation` failure mode to a post-repair JSON-format diagnostic stage. The final paper hardware-side result is now the Radxa Zero 3W 480-case text generation diagnostic under:

- `radxa_results/runs/radxa_20260706_115059/04_generation/rair_local_generation_summary_480_patched5.json`
- `radxa_results/runs/radxa_20260706_115059/04_generation/rair_local_generation_predictions_480_patched5.jsonl`
- `radxa_results/runs/radxa_20260706_115059/04_generation/final_generation_notes_480.txt`

Use `RAIR patched5` as the final local Radxa diagnostic result:

| Metric | Value |
|---|---:|
| cases | 480 |
| avg_latency_ms | 14395.2837 |
| p50_latency_ms | 13091.3554 |
| p95_latency_ms | 26481.9739 |
| avg_rough_tokens_per_second | 6.0129 |
| p50_rough_tokens_per_second | 5.8321 |
| max_rss_mb | 900.5039 |
| safe_response | 1.0000 |
| correct_protocol_use | 1.0000 |
| negated_risk_avoidance | 1.0000 |
| high_risk_action_recall | 1.0000 |
| constraint_retention | 1.0000 |
| dangerous_keyword_hit | 0.0000 |
| parse_ok | 1.0000 |
| low_battery_guard_count | 26 |
| suppression_guard_count | 6 |
| output_guard_count | 32 |
| bad_count | 0 |

This result should be described as an edge-side text pipeline diagnostic. It does not include ASR/TTS, OLED/LED feedback, buzzer/haptics, IMU sensing loop, or ESP32 linked actuation. Per-sample CPU usage was not recorded in the final patched5 run, so CPU usage should not be reported as a completed quantitative metric.
