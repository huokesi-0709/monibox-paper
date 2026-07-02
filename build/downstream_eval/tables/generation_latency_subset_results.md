# Generation Latency Subset Results

This table is the paper-level generation latency result. It reports `qwen-plus`
cloud strong-reference generation latency measured on a stratified subset. It is
not edge-device deployment latency and not the 480-case full generation latency.

Source summary:
`build/downstream_eval/generation/reference_latency_subset/reference_latency_subset_summary.json`

| Setting | System | Generator | LatencyMeasurement | NumCases | FailedCases | AvgLatencyMs | P95LatencyMs |
|---|---|---|---|---:|---:|---:|---:|
| strong_hosted_reference | all | qwen-plus | stratified_subset | 120 | 0 | 2459.700 | 3602.832 |
| strong_hosted_reference | vanilla-rag | qwen-plus | stratified_subset | 60 | 0 | 2538.447 | 3636.283 |
| strong_hosted_reference | rair-rag | qwen-plus | stratified_subset | 60 | 0 | 2380.953 | 3261.890 |

Notes:

- The system-level rows are `vanilla-rag + qwen-plus` and `rair-rag + qwen-plus`.
- These values come from the committed stratified subset summary.
- These values should not be interpreted as local 0.5B edge deployment latency.
- These values should not be interpreted as full 480-case generation latency.
