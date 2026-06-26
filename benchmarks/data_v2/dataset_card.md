# HSC-DisasterBench-v2 Dataset Card

- Generated at: 2026-06-26T12:29:37.979076+00:00
- Random seed: 42
- Version role: 6000-sample formal dataset for paper main experiments.
- Split policy: grouped by canonical_id; all robust variants stay with their clean canonical sample.
- Robust variants: filler_noise, long_context, repetition.

## Files

- clean_dev.jsonl: 500
- robustness_dev.jsonl: 1500
- clean_test.jsonl: 1000
- robustness_test.jsonl: 3000
- total: 6000

## Canonical Scenario Distribution

| scenario_family | clean_count |
|---|---:|
| severe_bleeding | 150 |
| respiratory_distress | 120 |
| crush_trapped | 120 |
| fracture_immobility | 90 |
| head_injury_consciousness | 100 |
| hypothermia | 90 |
| dehydration_hunger | 70 |
| smoke_dust_choking | 80 |
| structural_danger_aftershock | 90 |
| sos_location_device | 80 |
| psychological_panic | 70 |
| unsafe_request | 90 |
| negation_conflict | 100 |
| multi_intent_priority | 150 |
| out_of_scope_low_evidence | 100 |

## Risk Distribution

| risk_level | total_count |
|---|---:|
| low | 400 |
| medium | 1280 |
| high | 1400 |
| critical | 2920 |

## Usage Boundary

Dev split is reserved for DE weight optimization, threshold adjustment, and rule debugging. Test split is reserved for final paper results, final tables, and final case analysis.
