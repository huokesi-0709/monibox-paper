# Negation Failure Cases

- Total mismatches: 64
- Reported: 20 of max 20

This is preliminary rule-based error typing, not manual qualitative analysis.

| ID | Gold Negated Risks | Predicted Negated Risks | Missing | Extra | Error Type | Reason | Raw Input |
|---|---|---|---|---|---|---|---|
| clean_0077 |  | altered_consciousness_or_head_injury |  | altered_consciousness_or_head_injury | over_negation | Prediction marked an additional risk as negated beyond gold labels. | 我意识有点不清楚 |
| multi_0355 |  | trauma_or_fracture |  | trauma_or_fracture | over_negation | Prediction marked an additional risk as negated beyond gold labels. | 我腿疼得动不了，还出不去 |
| multi_0356 |  | trauma_or_fracture |  | trauma_or_fracture | over_negation | Prediction marked an additional risk as negated beyond gold labels. | 我腿疼得动不了，还被困住 |
| multi_0357 |  | trauma_or_fracture |  | trauma_or_fracture | over_negation | Prediction marked an additional risk as negated beyond gold labels. | 我腿疼得动不了，还门打不开 |
| neg_0011 | severe_bleeding_or_shock |  | severe_bleeding_or_shock |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 手上有伤口，但血已经止住了 |
| neg_0014 | severe_bleeding_or_shock |  | severe_bleeding_or_shock |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 腿上有伤口，但血已经止住了 |
| neg_0017 | severe_bleeding_or_shock |  | severe_bleeding_or_shock |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 胳膊上有伤口，但血已经止住了 |
| neg_0020 | severe_bleeding_or_shock |  | severe_bleeding_or_shock |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 脚踝那儿有伤口，但血已经止住了 |
| neg_0022 | severe_bleeding_or_shock | altered_consciousness_or_head_injury, severe_bleeding_or_shock |  | altered_consciousness_or_head_injury | over_negation | Prediction marked an additional risk as negated beyond gold labels. | 我撞到头了，不过没有头部出血 |
| neg_0023 | severe_bleeding_or_shock |  | severe_bleeding_or_shock |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我撞到头了，不过没看到血 |
| neg_0025 | severe_bleeding_or_shock | altered_consciousness_or_head_injury, severe_bleeding_or_shock |  | altered_consciousness_or_head_injury | over_negation | Prediction marked an additional risk as negated beyond gold labels. | 我头晕，不过没有头部出血 |
| neg_0026 | severe_bleeding_or_shock |  | severe_bleeding_or_shock |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我头晕，不过没看到血 |
| neg_0028 | severe_bleeding_or_shock | altered_consciousness_or_head_injury, severe_bleeding_or_shock |  | altered_consciousness_or_head_injury | over_negation | Prediction marked an additional risk as negated beyond gold labels. | 我头被碰了一下，不过没有头部出血 |
| neg_0029 | severe_bleeding_or_shock |  | severe_bleeding_or_shock |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我头被碰了一下，不过没看到血 |
| neg_0066 | respiratory_distress |  | respiratory_distress |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我被困住了，但还能正常呼吸 |
| neg_0067 | respiratory_distress |  | respiratory_distress |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我被困住了，但还能正常喘气 |
| neg_0068 | respiratory_distress |  | respiratory_distress |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我被困住了，但还能正常说话 |
| neg_0069 | respiratory_distress |  | respiratory_distress |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我被卡住了，但还能正常呼吸 |
| neg_0070 | respiratory_distress |  | respiratory_distress |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我被卡住了，但还能正常喘气 |
| neg_0071 | respiratory_distress |  | respiratory_distress |  | missing_negated_candidate | Gold negated risk was not present among predicted risk candidates. | 我被卡住了，但还能正常说话 |
