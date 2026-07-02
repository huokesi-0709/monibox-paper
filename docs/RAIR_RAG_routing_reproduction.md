# RAIR-RAG Routing Reproduction

This document freezes the current RAIR routing benchmark as the first-layer
evidence for the RAIR-RAG paper. Downstream retrieval and generation experiments
should be added under separate downstream experiment directories and must not
change the routing algorithm logic.

## Experiment Entry Points

Use the repository scripts as the main routing experiment entry points:

```bash
bash scripts/run_rair_eval.sh
```

```powershell
.\scripts\run_rair_eval.ps1
```

Both scripts call the stable routing evaluator:

```text
benchmarks/rair_rag/run_routing_eval.py
```

The scripts evaluate the same method set across the configured RAIR test files:

- `keyword-baseline`
- `bert-multilabel`
- `no-negation`
- `single-intent`
- `risk-router`

`bert-multilabel` is a real `bert-base-chinese` multilabel classifier. It no
longer falls back to the old keyword/candidate proxy. Train it before running
the full routing script. First prepare the BERT-only split from the RAIR dev
pool:

```bash
uv run python -m benchmarks.rair_rag.baselines.prepare_bert_multilabel_split
```

The committed split manifest is `build/bert_multilabel/bert_split_manifest.json`.
It records 322 dev-pool cases split by `canonical_id` into 264 training cases
and 58 validation cases with seed 42 and train_ratio 0.8. The held-out main test
set, `benchmarks/rair_rag/data/test/rair_test.jsonl`, contains 480 cases and is
not used for training, threshold choice, or best-epoch/model selection. The
current split has zero overlap with the 480-case test set by both `id` and
`canonical_id`.

Then train the BERT baseline:

```bash
uv run --extra bert python -m benchmarks.rair_rag.baselines.train_bert_multilabel \
  --train-data build/bert_multilabel/rair_train.jsonl \
  --dev-data build/bert_multilabel/rair_validation.jsonl
```

`--train-data` must point to a training JSONL that excludes the held-out test
cases. The training script selects `build/bert_multilabel/best_model/` on the
validation split only. Do not use any `data/test/*.jsonl` file for model
selection or hyperparameter tuning. Test-set evaluation is then:

```bash
uv run --extra bert python -m benchmarks.rair_rag.baselines.eval_bert_multilabel \
  --data benchmarks/rair_rag/data/test/rair_test.jsonl
```

The archived keyword/candidate proxy is still available as
`candidate-multilabel`, but it is not reported as BERT.

## Datasets

The main test set is:

```text
benchmarks/rair_rag/data/test/rair_test.jsonl
```

This is the primary dataset for the main routing benchmark and paper-level
method comparison.

The composite perturbation extension set is:

```text
benchmarks/rair_rag/data/test/rair_test_multi_intent_negation.jsonl
```

This file should be treated as an extension stress test for multi-intent and
negation interactions. It is useful for robustness and candidate-level analysis,
but it is not the fully manual consensus-gold main test set.

The scripts also run intermediate perturbation sets:

- `benchmarks/rair_rag/data/test/rair_test_negation.jsonl`
- `benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl`

These support diagnostic reporting and ablation interpretation.

## Output Boundary

Routing outputs are written under:

```text
build/rair_eval/
```

This directory is reserved for the first-layer routing experiment. Keep it
limited to:

- summary JSON files;
- selected prediction JSONL files needed for paper trace analysis;
- exported tables under `build/rair_eval/tables/`;
- routing runtime latency summaries.

The main paper table is:

```text
build/rair_eval/tables/main_results.md
```

The routing-stage latency summary is:

```text
build/rair_eval/runtime_latency_summary.json
```

Downstream retrieval or generation results should be written to a separate
output root, such as `build/downstream_eval/`, so they do not pollute the frozen
routing benchmark artifacts.

## Metric Interpretation

The core routing benchmark should focus on route-level safety and intent
construction metrics, including:

- `RouteAcc`
- `HRR`
- `PFTR`
- `NegRiskF1`
- `SecondaryIntentF1`

On the main test set, `CandidateF1` and `EvidenceTypeAcc` are not core routing
claims. They may appear in summaries for completeness, but they should not be
used as the main evidence for the first-layer routing result.

Candidate-level metrics, especially `CandidateF1` and `EvidenceTypeAcc`, are
primarily reported on the composite perturbation extension set:

```text
benchmarks/rair_rag/data/test/rair_test_multi_intent_negation.jsonl
```

In that setting, they help explain whether the router preserves useful protocol
candidates and evidence-type decisions under combined multi-intent and negation
stress. Interpret these numbers as robustness diagnostics rather than as the
main consensus-gold benchmark conclusion.
