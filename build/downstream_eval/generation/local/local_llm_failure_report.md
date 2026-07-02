# Local LLM Failure Report

- Generation directory: `D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local`
- Output files: 3
- Sample failures shown: 4

## Failure Type Counts

| FailureType | Count |
|---|---:|
| model_load_error | 0 |
| context_overflow | 0 |
| empty_generation | 0 |
| invalid_json | 4 |
| runtime_exception | 0 |

## Exception Types

| ExceptionType | Count |
|---|---:|
| none | 0 |

## Files

| Output | Rows | SummaryFailedCases | FailedCases | ParseFailedCases | EmptyOutputCases |
|---|---:|---:|---:|---:|---:|
| D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\rair_test_rair-rag_local-llm_outputs.jsonl | 5 | 0 | 0 | 1 | 0 |
| D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\rair_test_vanilla-rag_local-llm_outputs.jsonl | 5 | 0 | 0 | 2 | 0 |
| D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\smoke_vanilla_outputs.jsonl | 1 | 0 | 0 | 1 | 0 |

## First Failure Samples

| # | File | ID | System | FailureType | Status | Error | ParseError | RawOutputPreview | PromptLength | RetrievedEvidenceCount |
|---:|---|---|---|---|---|---|---|---|---:|---:|
| 1 | D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\rair_test_rair-rag_local-llm_outputs.jsonl | clean_0004 | rair-rag | invalid_json | ok |  | invalid JSON: Expecting value: line 1 column 1 (char 0) | ```json {    "protocol_id": null,    "reply": "I'm sorry to hear that you're feeling憋 up. Can you please tell me more about what's causing you to feel like this?",    "safety_notes": ["I'm not sure what's causing you to feel like this. Can you please provide me with more information?",    "used_evid | 1944 | 3 |
| 2 | D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\rair_test_vanilla-rag_local-llm_outputs.jsonl | clean_0001 | vanilla-rag | invalid_json | ok |  | invalid JSON: Unterminated string starting at: line 3 column 13 (char 38) | {    "protocol_id": null,    "reply": "I'm sorry, I'm not sure what you're trying to say. Can you please provide more context or information? I'm not sure what you're trying to do or what you're trying to say. I'm not sure what you're trying to do or what you're trying to say. I'm not sure what you' | 1487 | 3 |
| 3 | D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\rair_test_vanilla-rag_local-llm_outputs.jsonl | clean_0004 | vanilla-rag | invalid_json | ok |  | invalid JSON: Expecting value: line 1 column 1 (char 0) | ```json {    "protocol_id": null,    "reply": "I'm sorry to hear that you're feeling憋 up. Can you please tell me what happened to you?",    "safety_notes": ["Don't worry, I'll do my best to help you."],    "used_evidence": [] } ``` | 1459 | 3 |
| 4 | D:\projects\monibox-Y\monibox\build\downstream_eval\generation\local\smoke_vanilla_outputs.jsonl | clean_0001 | vanilla-rag | invalid_json |  |  | invalid JSON: Expecting value: line 1 column 1 (char 0) | not json | 982 | 1 |
