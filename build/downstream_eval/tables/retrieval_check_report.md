# Downstream Retrieval Check Report

- Dataset: `rair_test`
- Retrieval directory: `D:\projects\monibox-Y\monibox\build\downstream_eval\retrieval`

| System | Status | NumCases | ProtocolAcc | EvidenceHit@1 | EvidenceHit@3 | PFTR | HRR | Summary | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| vanilla-rag | OK | 480 | 0.0042 | 0.0042 | 0.0063 | 0.0000 | 0.0084 | D:\projects\monibox-Y\monibox\build\downstream_eval\retrieval\rair_test_vanilla-rag_summary.json |  |
| keyword-rag | OK | 480 | 0.7875 | 0.0354 | 0.0396 | 0.0167 | 0.7388 | D:\projects\monibox-Y\monibox\build\downstream_eval\retrieval\rair_test_keyword-rag_summary.json |  |
| bert-rag | OK | 480 | 0.3771 | 0.0417 | 0.0521 | 0.0458 | 0.3624 | D:\projects\monibox-Y\monibox\build\downstream_eval\retrieval\rair_test_bert-rag_summary.json |  |
| rair-rag | OK | 480 | 0.9625 | 0.0542 | 0.0750 | 0.0063 | 0.9831 | D:\projects\monibox-Y\monibox\build\downstream_eval\retrieval\rair_test_rair-rag_summary.json |  |
