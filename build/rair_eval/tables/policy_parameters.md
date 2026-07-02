# RAIR Routing Policy Parameters

| Parameter | Value | Group | Description |
|---|---:|---|---|
| negation_window | 6 | negation | Token/window span used for negation scope resolution. |
| negation_penalty | 0.45 | negation | Confidence penalty applied to risks resolved as negated. |
| confidence_threshold | 0.25 | confidence | Global minimum confidence for retaining a risk candidate. |
| high_risk_boost | 0.05 | priority | Priority boost for high-risk intents during route selection. |
| operational_constraint_weight | 0.2 | priority | Weight for operational constraints such as low battery. |
| negation_words | 没有, 没, 不是, 未, 无, 不 | negation | Lexical triggers used by the negation resolver. |
| boundary_terms | 但是, 不过, 然后, 还有, 并且, 而且, 同时, 另外, 还, 又, 也, ，, ,, 。, ., ；, ;, 、, ？, ?, ！, ! | negation | Boundary terms that limit negation scope. |
| intent_base_weights.aftershock_or_collapse_hazard | 0.84 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.altered_consciousness_or_head_injury | 0.9 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.crush_injury | 0.92 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.dehydration_or_resource_deprivation | 0.55 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.hypothermia | 0.82 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.low_battery | 0.2 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.out_of_scope | 0.05 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.psychological_distress | 0.45 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.respiratory_distress | 1 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.severe_bleeding_or_shock | 0.95 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.trapped_or_entrapment | 0.88 | intent_weight | Base priority weight for this intent. |
| intent_base_weights.trauma_or_fracture | 0.78 | intent_weight | Base priority weight for this intent. |
