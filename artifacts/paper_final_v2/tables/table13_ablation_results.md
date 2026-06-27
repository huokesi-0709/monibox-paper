| Ablation | RouteAcc | ProtocolAcc | HRR | URR | UCR | RC | P95 Latency | Main Effect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| without_input_normalization | 0.6077 | 0.1400 | 0.8164 | 0.0000 | 0.0000 | 0.5890 | 35.30 | Input normalization |
| without_multi_intent | 0.0670 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 47.07 | Multi-intent routing |
| without_negation | 0.6077 | 0.1517 | 0.8251 | 0.0000 | 0.0000 | 0.5820 | 34.47 | Negation handling |
| without_protocol_gate | 0.6077 | 0.0000 | 0.6671 | 0.0000 | 0.0000 | 0.9120 | 42.88 | Protocol gate |
| without_safety_rerank | 0.6077 | 0.1400 | 0.8164 | 0.0000 | 0.0000 | 0.5890 | 34.20 | Safety rerank |
| without_low_evidence | 0.6077 | 0.1400 | 0.8164 | 0.0000 | 0.0000 | 0.5890 | 34.32 | Low-evidence routing |
| without_guard | 0.6077 | 0.1400 | 0.8164 | 0.0000 | 0.0000 | 0.5890 | 34.60 | Guard module |
| without_de_optimization | 0.6077 | 0.1400 | 0.8164 | 0.0000 | 0.0000 | 0.5890 | 34.60 | DE optimization |
