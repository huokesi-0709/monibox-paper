# RAIR Routing Parameter Connectivity Diagnosis

This diagnostic varies routing-policy parameters, including extreme values, to test whether each parameter is connected to the decision path. It should not be interpreted as parameter stability evidence.

For `negation_penalty`, read `NegRiskF1`, `PFTR`, `negated_risks_changed_count`, `suppressed_protocols_changed_count`, and `avg_negation_probability_delta`.

For `high_risk_boost`, read `HRR`, `RouteAcc`, `primary_intent_changed_count`, and `avg_risk_score_delta`.

If all predictions remain identical across all tested values for a parameter, the report emits `parameter may not be connected to decision path`.

| Parameter | Value | NumCases | NegRiskF1 | PFTR | HRR | RouteAcc | primary_intent_changed_count | negated_risks_changed_count | suppressed_protocols_changed_count | avg_risk_score_delta | avg_negation_probability_delta | Warning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| negation_penalty | 0.0000 | 480 | 0.0000 | 0.1583 | 0.9354 | 0.8125 | 77 | 115 | 115 | 0.0434 | 0.1140 |  |
| negation_penalty | 0.2000 | 480 | 0.0000 | 0.1583 | 0.9354 | 0.8125 | 77 | 115 | 115 | 0.0434 | 0.0633 |  |
| negation_penalty | 0.4500 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0000 | 0.0000 |  |
| negation_penalty | 0.8000 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0000 | 0.0068 |  |
| negation_penalty | 2.0000 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0000 | 0.0068 |  |
| negation_penalty | 10.0000 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0000 | 0.0068 |  |
| high_risk_boost | 0.0000 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0344 | 0.0000 |  |
| high_risk_boost | 0.0500 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0000 | 0.0000 |  |
| high_risk_boost | 0.1000 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0269 | 0.0000 |  |
| high_risk_boost | 1.0000 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0528 | 0.0000 |  |
| high_risk_boost | 10.0000 | 480 | 0.7410 | 0.0063 | 0.9831 | 0.9625 | 0 | 0 | 0 | 0.0528 | 0.0000 |  |
