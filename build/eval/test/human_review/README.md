# Human Review Traceability Notes

This directory contains the digital review artifacts for the test-set error analysis.

Important boundary: this is an LLM-assisted digital evaluation review, not an expert human evaluation. The results are intended only to support qualitative error analysis and auditability. The paper's main conclusions should still be based on the full test-set automatic metrics.

## Files

- `review_sample.jsonl`: the 100-item sampled review set exported from `build/eval/test` predictions.
- `annotator_A_labels.jsonl`: labels from the emergency-safety review perspective.
- `annotator_B_labels.jsonl`: labels from the NLP/system-evaluation review perspective.
- `final_labels_C.jsonl`: adjudicated final labels.
- `disagreement_report.json`: machine-readable merge and agreement statistics.
- `disagreement_report.md`: human-readable merge and agreement report.
- `review_sample.md`: readable copy of the sampled review items.

## Interpretation

Use these files to trace how the sampled digital review was constructed, independently labeled, adjudicated, and merged. Do not present these artifacts as a substitute for expert clinical, emergency-management, or field-rescue assessment.
