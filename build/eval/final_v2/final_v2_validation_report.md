# final_v2 Evidence Validation Report

- Generated at: 2026-06-27T03:07:50.789117+00:00
- Status: PASS
- Error count: 0
- Warning count: 0

## Errors

- None

## Warnings

- None

## Dataset

- Total samples: 6000
- Audit passed: True
- dev/test leakage count: 0
- Missing field records: 0
- Clean samples have three robust variants: True
- Risk distribution: {"critical": 2920, "high": 1400, "low": 400, "medium": 1280}
- Scenario distribution: {"crush_trapped": 480, "dehydration_hunger": 280, "fracture_immobility": 360, "head_injury_consciousness": 400, "hypothermia": 360, "multi_intent_priority": 600, "negation_conflict": 400, "out_of_scope_low_evidence": 400, "psychological_panic": 280, "respiratory_distress": 480, "severe_bleeding": 600, "smoke_dust_choking": 320, "sos_location_device": 320, "structural_danger_aftershock": 360, "unsafe_request": 360}

## Human Review

- Balanced sample count: 300
- Method distribution: {"hsc-rag-de": 75, "hsc-rag-manual": 75, "rag-guard": 75, "vanilla-rag": 75}
- Perturbation distribution: {"clean": 75, "filler_noise": 75, "long_context": 75, "repetition": 75}
- Risk distribution: {"critical": 156, "high": 64, "low": 16, "medium": 64}

## Paper Fill Readiness

- Chapter 4 can be filled from final_v2: True
- Source directory: `build/eval/final_v2/`
