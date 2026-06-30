# RAIR-RAG Dataset Notes

This dataset should be described as a guideline-informed, human-reviewed synthetic benchmark for risk-aware input routing.

Important evidence-scope notes:

- `source_type=template_generated_human_reviewed` means the input was generated from templates and then passed through the annotation/adjudication workflow.
- `guideline_refs` are label-level mappings inherited from `benchmarks/rair_rag/annotation/risk_taxonomy.yaml`.
- `guideline_refs.review_status=confirmed` means the source mapping is confirmed at the taxonomy-label level.
- `guideline_refs.review_status=pending_source_confirmation` means the label is retained for evaluation, but the Chinese public-guidance source still needs concrete source confirmation before claiming a fully authoritative per-case evidence chain.
- `risk_mentions` records matched or inferred text-level risk mentions used to support the routing label.
- `reference_reply` is not populated in the current benchmark and should not be described as available per case.

Split and duplicate-text notes:

- Dev/test splitting is leakage-safe at the `canonical_id` level and at the normalized text level.
- The split script keeps any cases connected by the same `canonical_id`, normalized `raw_input`, or normalized `canonical_input` in the same split.
- Exact normalized `raw_input` or `canonical_input` overlap between dev and test should be treated as a release-blocking error.
- Template-generated data may contain near-duplicate or repeated surface forms only when they represent intentional template variants, annotation checks, or different perturbation contexts.
- For a formal release, exact duplicate raw texts should either be deduplicated before publishing or documented as intentional template variants with their labels and perturbation context.
- The split manifest records duplicate-text audit counts under `gold_duplicate_text_groups` and per-split `duplicate_text_groups`.

Do not claim that every sample has a fully confirmed authoritative source mapping. A safer paper description is:

> guideline-informed, human-reviewed synthetic benchmark with label-level guideline references and explicit pending-source markers.
