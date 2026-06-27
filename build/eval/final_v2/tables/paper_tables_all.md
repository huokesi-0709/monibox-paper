# final_v2 论文第 4 章表格汇总

## 数据集分布

| split | clean_count | robust_count | total_count | risk_distribution | scenario_family_distribution | perturbation_distribution |
| --- | --- | --- | --- | --- | --- | --- |
| dev | 500 | 1500 | 2000 | {"critical": 972, "high": 468, "low": 132, "medium": 428} | {"crush_trapped": 160, "dehydration_hunger": 96, "fracture_immobility": 120, "head_injury_consciousness": 132, "hypothermia": 120, "multi_intent_priority": 200, "negation_conflict": 132, "out_of_scope_low_evidence": 132, "psychological_panic": 92, "respiratory_distress": 160, "severe_bleeding": 200, "smoke_dust_choking": 108, "sos_location_device": 108, "structural_danger_aftershock": 120, "unsafe_request": 120} | {"clean": 500, "filler_noise": 500, "long_context": 500, "repetition": 500} |
| test | 1000 | 3000 | 4000 | {"critical": 1948, "high": 932, "low": 268, "medium": 852} | {"crush_trapped": 320, "dehydration_hunger": 184, "fracture_immobility": 240, "head_injury_consciousness": 268, "hypothermia": 240, "multi_intent_priority": 400, "negation_conflict": 268, "out_of_scope_low_evidence": 268, "psychological_panic": 188, "respiratory_distress": 320, "severe_bleeding": 400, "smoke_dust_choking": 212, "sos_location_device": 212, "structural_danger_aftershock": 240, "unsafe_request": 240} | {"clean": 1000, "filler_noise": 1000, "long_context": 1000, "repetition": 1000} |

## 表 11：整体性能

| Method | Clean RouteAcc | Clean HRR | Clean URR | Robust RouteAcc | Robust HRR | Robust URR | RC | P95 Latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vanilla-RAG | 0.0670 | 0.0000 | 0.0000 | 0.0670 | 0.0000 | 0.0000 | 1.0000 | 41.55 |
| RAG-Guard | 0.0670 | 0.0000 | 0.0000 | 0.0670 | 0.0000 | 0.0000 | 1.0000 | 42.02 |
| HSC-RAG-manual | 0.5490 | 0.7089 | 0.0000 | 0.6077 | 0.8164 | 0.0000 | 0.5890 | 34.61 |
| HSC-RAG-DE | 0.5490 | 0.7089 | 0.0000 | 0.6077 | 0.8164 | 0.0000 | 0.5890 | 34.87 |

## 表 12：扰动类型分析

| Method | Clean RouteAcc | Filler Noise RouteAcc | Long Context RouteAcc | Repetition RouteAcc |
| --- | --- | --- | --- | --- |
| Vanilla-RAG | 0.0670 | 0.0670 | 0.0670 | 0.0670 |
| RAG-Guard | 0.0670 | 0.0670 | 0.0670 | 0.0670 |
| HSC-RAG-manual | 0.5490 | 0.5490 | 0.5490 | 0.7250 |
| HSC-RAG-DE | 0.5490 | 0.5490 | 0.5490 | 0.7250 |

## 表 13：消融实验

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

## 表 14：DE 效果

| Split | Manual RouteAcc | DE RouteAcc | ΔRouteAcc | Manual HRR | DE HRR | ΔHRR | Manual URR | DE URR | ΔURR | Manual P95 | DE P95 | ΔP95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| clean | 0.5490 | 0.5490 | 0.0000 | 0.7089 | 0.7089 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 36.48 | 35.00 | -1.48 |
| robust | 0.6077 | 0.6077 | 0.0000 | 0.8164 | 0.8164 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 34.61 | 34.87 | 0.25 |

## 表 15：安全性指标

| Method | Clean HRR | Clean HMR | Clean URR | Clean UCR | Robust HRR | Robust HMR | Robust URR | Robust UCR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vanilla-RAG | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| RAG-Guard | 0.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0.0000 |
| HSC-RAG-manual | 0.7089 | 0.2911 | 0.0000 | 0.0000 | 0.8164 | 0.1836 | 0.0000 | 0.0000 |
| HSC-RAG-DE | 0.7089 | 0.2911 | 0.0000 | 0.0000 | 0.8164 | 0.1836 | 0.0000 | 0.0000 |

## 表 16：效率指标

| Method | Avg Latency | P95 Latency | Avg Response Length |
| --- | --- | --- | --- |
| Vanilla-RAG | 34.06 | 41.55 | 24.48 |
| RAG-Guard | 33.91 | 42.02 | 24.48 |
| HSC-RAG-manual | 15.63 | 34.61 | 22.29 |
| HSC-RAG-DE | 15.64 | 34.87 | 22.24 |

## 表 17：Bootstrap 95% CI

| Group | Name | Metric | Mean | CI Lower | CI Upper | N |
| --- | --- | --- | --- | --- | --- | --- |
| ablation | without_de_optimization | RouteAcc | 0.6077 | 0.5893 | 0.6250 | 3000 |
| ablation | without_de_optimization | HRR | 0.8164 | 0.7998 | 0.8316 | 2298 |
| ablation | without_de_optimization | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_de_optimization | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_de_optimization | RC | 0.5890 | 0.6296 | 0.6786 | 3000 |
| ablation | without_guard | RouteAcc | 0.6077 | 0.5913 | 0.6247 | 3000 |
| ablation | without_guard | HRR | 0.8164 | 0.7994 | 0.8325 | 2298 |
| ablation | without_guard | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_guard | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_guard | RC | 0.5890 | 0.6304 | 0.6782 | 3000 |
| ablation | without_input_normalization | RouteAcc | 0.6077 | 0.5900 | 0.6250 | 3000 |
| ablation | without_input_normalization | HRR | 0.8164 | 0.8011 | 0.8316 | 2298 |
| ablation | without_input_normalization | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_input_normalization | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_input_normalization | RC | 0.5890 | 0.6286 | 0.6766 | 3000 |
| ablation | without_low_evidence | RouteAcc | 0.6077 | 0.5913 | 0.6243 | 3000 |
| ablation | without_low_evidence | HRR | 0.8164 | 0.8011 | 0.8325 | 2298 |
| ablation | without_low_evidence | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_low_evidence | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_low_evidence | RC | 0.5890 | 0.6283 | 0.6779 | 3000 |
| ablation | without_multi_intent | RouteAcc | 0.0670 | 0.0583 | 0.0757 | 3000 |
| ablation | without_multi_intent | HRR | 0.0000 | 0.0000 | 0.0000 | 2298 |
| ablation | without_multi_intent | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_multi_intent | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_multi_intent | RC | 1.0000 | 1.0000 | 1.0000 | 3000 |
| ablation | without_negation | RouteAcc | 0.6077 | 0.5900 | 0.6263 | 3000 |
| ablation | without_negation | HRR | 0.8251 | 0.8094 | 0.8407 | 2298 |
| ablation | without_negation | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_negation | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_negation | RC | 0.5820 | 0.6203 | 0.6716 | 3000 |
| ablation | without_protocol_gate | RouteAcc | 0.6077 | 0.5897 | 0.6257 | 3000 |
| ablation | without_protocol_gate | HRR | 0.6671 | 0.6488 | 0.6858 | 2298 |
| ablation | without_protocol_gate | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_protocol_gate | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_protocol_gate | RC | 0.9120 | 0.9159 | 0.9358 | 3000 |
| ablation | without_safety_rerank | RouteAcc | 0.6077 | 0.5900 | 0.6253 | 3000 |
| ablation | without_safety_rerank | HRR | 0.8164 | 0.8003 | 0.8320 | 2298 |
| ablation | without_safety_rerank | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_safety_rerank | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| ablation | without_safety_rerank | RC | 0.5890 | 0.6270 | 0.6776 | 3000 |
| clean | hsc-rag-de | RouteAcc | 0.5490 | 0.5210 | 0.5800 | 1000 |
| clean | hsc-rag-de | HRR | 0.7089 | 0.6762 | 0.7402 | 766 |
| clean | hsc-rag-de | URR | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | hsc-rag-de | UCR | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | hsc-rag-de | RC | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | hsc-rag-manual | RouteAcc | 0.5490 | 0.5170 | 0.5810 | 1000 |
| clean | hsc-rag-manual | HRR | 0.7089 | 0.6789 | 0.7415 | 766 |
| clean | hsc-rag-manual | URR | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | hsc-rag-manual | UCR | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | hsc-rag-manual | RC | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | rag-guard | RouteAcc | 0.0670 | 0.0520 | 0.0830 | 1000 |
| clean | rag-guard | HRR | 0.0000 | 0.0000 | 0.0000 | 766 |
| clean | rag-guard | URR | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | rag-guard | UCR | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | rag-guard | RC | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | vanilla-rag | RouteAcc | 0.0670 | 0.0530 | 0.0820 | 1000 |
| clean | vanilla-rag | HRR | 0.0000 | 0.0000 | 0.0000 | 766 |
| clean | vanilla-rag | URR | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | vanilla-rag | UCR | 0.0000 | 0.0000 | 0.0000 | 1000 |
| clean | vanilla-rag | RC | 0.0000 | 0.0000 | 0.0000 | 1000 |
| robust | hsc-rag-de | RouteAcc | 0.6077 | 0.5900 | 0.6260 | 3000 |
| robust | hsc-rag-de | HRR | 0.8164 | 0.8003 | 0.8320 | 2298 |
| robust | hsc-rag-de | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| robust | hsc-rag-de | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| robust | hsc-rag-de | RC | 0.5890 | 0.6288 | 0.6771 | 3000 |
| robust | hsc-rag-manual | RouteAcc | 0.6077 | 0.5907 | 0.6260 | 3000 |
| robust | hsc-rag-manual | HRR | 0.8164 | 0.8003 | 0.8320 | 2298 |
| robust | hsc-rag-manual | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| robust | hsc-rag-manual | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| robust | hsc-rag-manual | RC | 0.5890 | 0.6271 | 0.6786 | 3000 |
| robust | rag-guard | RouteAcc | 0.0670 | 0.0590 | 0.0770 | 3000 |
| robust | rag-guard | HRR | 0.0000 | 0.0000 | 0.0000 | 2298 |
| robust | rag-guard | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| robust | rag-guard | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| robust | rag-guard | RC | 1.0000 | 1.0000 | 1.0000 | 3000 |
| robust | vanilla-rag | RouteAcc | 0.0670 | 0.0583 | 0.0760 | 3000 |
| robust | vanilla-rag | HRR | 0.0000 | 0.0000 | 0.0000 | 2298 |
| robust | vanilla-rag | URR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| robust | vanilla-rag | UCR | 0.0000 | 0.0000 | 0.0000 | 3000 |
| robust | vanilla-rag | RC | 1.0000 | 1.0000 | 1.0000 | 3000 |

## 表 18：数字复核

| Method | Review Count | Final Safety Score | Final Usefulness Score | Final Brevity Score | Route Correct Rate | Protocol Correct Rate | Unsafe Action Rate | Unsupported Claim Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vanilla-RAG |  |  |  |  |  |  |  |  |
| RAG-Guard |  |  |  |  |  |  |  |  |
| HSC-RAG-manual |  |  |  |  |  |  |  |  |
| HSC-RAG-DE |  |  |  |  |  |  |  |  |
