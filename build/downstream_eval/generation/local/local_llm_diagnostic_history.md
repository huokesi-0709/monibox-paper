# Local LLM Diagnostic History

This note separates the local 0.5B generator diagnosis into two stages so the
paper can report the local generation status precisely.

## Stage 1: Full local generation before chat-template repair

- Observed problem: `empty_generation` dominated the local generation outputs.
- Historical count: 960 `empty_generation` cases were observed before the
  chat-template repair.
- Evidence status: the superseded pre-repair JSONL outputs are not present in
  the current local generation directory; this stage is retained here as a
  historical diagnostic record rather than as a current machine-readable output
  table.
- Interpretation: the Qwen chat GGUF model was being called through raw
  completion rather than a chat-template-compatible path.
- Paper implication: this stage should be reported as a pre-repair diagnostic,
  not as a usable full local generation result.

## Stage 2: Smoke test after chat-template repair

- Rows: 5 `vanilla-rag + local-llm` rows, 5 `rair-rag + local-llm` rows, and 1
  additional vanilla smoke row.
- Observed problem: `invalid_json`.
- Current diagnostic sources:
  `build/downstream_eval/generation/local/local_generation_manifest.json` and
  `build/downstream_eval/generation/local/local_llm_failure_report.md`.
- Interpretation: the model can produce text after the chat-template repair, but
  JSON format control remains unstable.
- Paper implication: the local 0.5B path has moved from an empty-output problem
  to a format-stability problem, but it still does not provide a full local
  generation result suitable for the main conclusions.
