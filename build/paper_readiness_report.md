# Paper Readiness Report

- Overall: **PASS**
- PASS: 12
- WARN: 0
- FAIL: 0

| Status | Check | Detail |
|---|---|---|
| PASS | Forbidden legacy strings | No legacy Qwen marker or BERT proxy marker found in text files. |
| PASS | qwen-plus reference manifest | qwen-plus manifest present with 2 outputs: D:\projects\monibox-Y\monibox\build\downstream_eval\generation\reference\reference_generation_manifest.json |
| PASS | Reference generation vanilla outputs | 480 rows: D:\projects\monibox-Y\monibox\build\downstream_eval\generation\reference\rair_test_vanilla-rag_reference-llm_outputs.jsonl |
| PASS | Reference generation RAIR outputs | 480 rows: D:\projects\monibox-Y\monibox\build\downstream_eval\generation\reference\rair_test_rair-rag_reference-llm_outputs.jsonl |
| PASS | Local generation vanilla outputs | 960 rows: D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\rair_test_vanilla-rag_local-llm_outputs.jsonl |
| PASS | Local generation RAIR outputs | 960 rows: D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\rair_test_rair-rag_local-llm_outputs.jsonl |
| PASS | Generation safety table | 570 bytes: D:\projects\monibox-Y\monibox\build\downstream_eval\tables\generation_safety_results.md |
| PASS | Generation latency table | 474 bytes: D:\projects\monibox-Y\monibox\build\downstream_eval\tables\generation_latency_results.md |
| PASS | Retrieval main table | 442 bytes: D:\projects\monibox-Y\monibox\build\downstream_eval\tables\retrieval_main_results.md |
| PASS | Real BERT test summary | Real BERT summary present: D:\projects\monibox-Y\monibox\build\bert_multilabel\test_summary.json |
| PASS | Policy parameter table | 2242 bytes: D:\projects\monibox-Y\monibox\build\rair_eval\tables\policy_parameters.md |
| PASS | Negation failure analysis | 4644 bytes: D:\projects\monibox-Y\monibox\build\rair_eval\error_analysis\negation_failures.md |
