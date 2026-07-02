# Generation Latency Results

| Setting | System | Generator | NumCases | FailedCases | AvgLatencyMs | P95LatencyMs |
|---|---|---|---:|---:|---:|---:|
| edge_local | rair-rag | Qwen1.5-0.5B-Chat-Q4_K_M | 480 | 0 | 2773.806 | 4293.565 |
| edge_local | vanilla-rag | Qwen1.5-0.5B-Chat-Q4_K_M | 480 | 0 | 2895.185 | 9742.895 |
| strong_hosted_reference | rair-rag | qwen-plus | 480 | 0 | N/A | N/A |
| strong_hosted_reference | vanilla-rag | qwen-plus | 480 | 0 | N/A | N/A |

> N/A means latency was not recorded. Legacy reference outputs did not record per-sample latency; run the newer generation_eval.py to remeasure generation latency.
