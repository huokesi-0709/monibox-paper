# RAIR-RAG Annotation Agreement Report

- Common cases: 817
- Disagreement cases: 15
- Missing from annotator A: 0
- Missing from annotator B: 0

## Single-Label Fields

| Field | Observed Agreement | Cohen's Kappa | Macro-F1 | Disagreements |
|---|---:|---:|---:|---:|
| human_accept | 0.9890 | 0.7529 | 0.8402 | 9 |
| primary_intent | 0.9890 | 0.9873 | 0.9354 | 9 |
| perturbation_types | 1.0000 | 1.0000 | 1.0000 | 0 |

## Multi-Label Fields

| Field | Exact Match | Micro Precision | Micro Recall | Micro-F1 | Disagreements |
|---|---:|---:|---:|---:|---:|
| negated_risks | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| secondary_intents | 0.9927 | 1.0000 | 0.9798 | 0.9898 | 6 |
| operational_constraints | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |
| should_not_trigger | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0 |

## Disagreement IDs

- multi_0229
- multi_0230
- multi_0231
- multi_0247
- multi_0248
- multi_0249
- multi_0256
- multi_0257
- multi_0258
- multi_0373
- multi_0376
- multi_0379
- neg_0162
- neg_0163
- neg_0164
