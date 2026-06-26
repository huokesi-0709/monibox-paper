# HSC-DisasterBench-v2 Dataset Audit

- Generated at: 2026-06-26T12:39:24.277655+00:00
- Input dir: `D:\projects\monibox-Y\monibox\benchmarks\data_v2`
- Passed: `True`
- Serious issue count: 0
- Total samples: 6000 / 6000
- Dev/test leakage count: 0
- Missing-field record count: 0
- Exact duplicate query rate: 0.0%
- Normalized duplicate query rate: 0.0%

## File Counts

| file | actual | expected |
|---|---:|---:|
| clean_dev.jsonl | 500 | 500 |
| robustness_dev.jsonl | 1500 | 1500 |
| clean_test.jsonl | 1000 | 1000 |
| robustness_test.jsonl | 3000 | 3000 |

## Canonical Scenario Distribution

| scenario_family | clean_count | expected |
|---|---:|---:|
| severe_bleeding | 150 | 150 |
| respiratory_distress | 120 | 120 |
| crush_trapped | 120 | 120 |
| fracture_immobility | 90 | 90 |
| head_injury_consciousness | 100 | 100 |
| hypothermia | 90 | 90 |
| dehydration_hunger | 70 | 70 |
| smoke_dust_choking | 80 | 80 |
| structural_danger_aftershock | 90 | 90 |
| sos_location_device | 80 | 80 |
| psychological_panic | 70 | 70 |
| unsafe_request | 90 | 90 |
| negation_conflict | 100 | 100 |
| multi_intent_priority | 150 | 150 |
| out_of_scope_low_evidence | 100 | 100 |

## Risk Distribution

| risk_level | count |
|---|---:|
| critical | 2920 |
| high | 1400 |
| low | 400 |
| medium | 1280 |

## Perturbation Distribution

| perturbation_type | count |
|---|---:|
| clean | 1500 |
| filler_noise | 1500 |
| long_context | 1500 |
| repetition | 1500 |

## Errors

- None
