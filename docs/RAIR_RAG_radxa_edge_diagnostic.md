# RAIR-RAG Radxa edge-side text generation diagnostic

This document records the final hardware-side diagnostic boundary and the final selected 480-case Radxa Zero 3W result used by the RAIR-RAG paper revision.

## Scope boundary

The completed hardware-side experiment is an **edge-side text pipeline diagnostic**, not a full speech-peripheral closed-loop experiment.

Included in the quantitative diagnostic:

- Text input.
- RAIR risk routing.
- RiskContext-conditioned local RAG retrieval.
- Local Qwen1.5-0.5B-Chat-Q4_K_M GGUF generation on Radxa Zero 3W.
- Runtime latency, rough tokens/s, peak RSS, and rule-based safety scoring.
- Deterministic patched5 output guards.

Excluded from the current quantitative diagnostic:

- ASR.
- TTS.
- OLED / LED feedback.
- Buzzer / haptics.
- IMU sensing loop.
- ESP32 linked actuation.
- Per-sample CPU utilization. CPU was described as a diagnostic target, but this final run did not record per-sample CPU usage, so the paper should not report a CPU usage table.

## Final selected result

- Device: Radxa Zero 3W.
- Run ID: `radxa_20260706_115059`.
- Mode: RAIR patched5.
- Cases: 480.
- Model: `models/llm/qwen1_5-0_5b-chat-q4_k_m.gguf`.
- Final summary: `radxa_results/runs/radxa_20260706_115059/04_generation/rair_local_generation_summary_480_patched5.json`.
- Final predictions: `radxa_results/runs/radxa_20260706_115059/04_generation/rair_local_generation_predictions_480_patched5.jsonl`.
- Final notes: `radxa_results/runs/radxa_20260706_115059/04_generation/final_generation_notes_480.txt`.

## Quantitative summary

| Metric | Value |
|---|---:|
| num_cases | 480 |
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

## Patched5 interpretation

`patched5` is a deterministic post-processing guard applied to the completed patched4 generation outputs. It includes:

1. Low-battery output guard.
2. Suppressed bleeding protocol guard.
3. Safer dangerous-keyword scoring for avoidance phrases such as `避免剧烈活动`.

The paper may use patched5 as the final 480-case Radxa local generation diagnostic result.

## Paper wording

Recommended wording:

> To verify the deployability of the RAIR-RAG core pipeline on a low-power edge device, we deployed the RAIR router, RiskContext-conditioned retrieval, and a quantized 0.5B local generator on Radxa Zero 3W. We conducted a 480-case text-input generation diagnostic. The experiment intentionally excludes ASR/TTS and peripheral actuation to avoid confounding pre-retrieval routing and generation-safety evaluation with speech-recognition errors and hardware-control delays.

Avoid this wording:

> The complete hardware closed loop has been validated.

More precise wording:

> The Radxa Zero 3W edge-side text pipeline deployment and local generation diagnostic have been completed.
