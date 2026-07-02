# Generation Safety Results

> Rows are exported from evaluated generation summary JSON files. Missing evaluated metrics are skipped with a warning.

| Setting | System | Generator | SafeResponseRate | CorrectProtocolUse | NegatedRiskAvoidance | HighRiskActionRecall | ConstraintRetention | ParseOkRate |
|---|---|---|---:|---:|---:|---:|---:|---:|
| edge_local | rair-rag | Qwen1.5-0.5B-Chat-Q4_K_M | 0.0000 | 0.0000 | 1.0000 | 0.2583 | 0.8146 | 0.0000 |
| edge_local | vanilla-rag | Qwen1.5-0.5B-Chat-Q4_K_M | 0.0000 | 0.0000 | 1.0000 | 0.2583 | 0.8146 | 0.0000 |
| strong_hosted_reference | rair-rag | qwen-plus | 0.5896 | 0.9688 | 0.9792 | 0.6312 | 0.9417 | 1.0000 |
| strong_hosted_reference | vanilla-rag | qwen-plus | 0.1542 | 0.2979 | 0.9688 | 0.4833 | 0.8542 | 1.0000 |
