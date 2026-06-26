# 论文第 4 章结果表

## 表 11 整体性能

| Method | Clean RouteAcc | Clean HRR | Clean URR | Robust RouteAcc | Robust HRR | Robust URR | RC | P95 Latency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vanilla-RAG | 0.1467 | 0.0000 | 0.0000 | 0.1467 | 0.0000 | 0.0000 | 1.0000 | 85.36 |
| RAG-Guard | 0.1467 | 0.0000 | 0.0000 | 0.1467 | 0.0000 | 0.0000 | 1.0000 | 85.32 |
| HSC-RAG-manual | 0.9244 | 0.9860 | 0.0000 | 0.9244 | 0.9860 | 0.0000 | 0.9644 | 28.35 |
| HSC-RAG-DE | 0.9244 | 0.9860 | 0.0000 | 0.9244 | 0.9860 | 0.0000 | 0.9644 | 29.57 |

## 表 12 不同扰动类型 RouteAcc

| Method | Clean RouteAcc | Filler Noise RouteAcc | Long Context RouteAcc | Repetition RouteAcc |
| --- | --- | --- | --- | --- |
| Vanilla-RAG | 0.1467 | 0.1467 | 0.1467 | 0.1467 |
| RAG-Guard | 0.1467 | 0.1467 | 0.1467 | 0.1467 |
| HSC-RAG-manual | 0.9244 | 0.9244 | 0.9244 | 0.9244 |
| HSC-RAG-DE | 0.9244 | 0.9244 | 0.9244 | 0.9244 |

## 表 13 消融实验

| Method | Main Affected Metrics | RouteAcc | HRR | URR | UCR | RC | P95 Latency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| without_input_normalization | RouteAcc, RC | 0.9244 | 0.9860 | 0.0000 | 0.0000 | 0.9644 | 29.00 |
| without_multi_intent | RouteAcc, HRR | 0.1467 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 85.69 |
| without_negation | HRR, UCR | 0.9244 | 0.9860 | 0.0000 | 0.0000 | 0.9667 | 28.43 |
| without_protocol_gate | RouteAcc, HRR | 0.9244 | 0.9790 | 0.0000 | 0.0000 | 1.0000 | 84.97 |
| without_safety_rerank | URR, UCR | 0.9244 | 0.9860 | 0.0000 | 0.0000 | 0.9644 | 28.02 |
| without_low_evidence | UCR, HRR | 0.9244 | 0.9860 | 0.0000 | 0.0000 | 0.9644 | 32.04 |
| without_guard | URR, UCR | 0.9244 | 0.9860 | 0.0000 | 0.0000 | 0.9644 | 35.78 |
| without_de_optimization | RouteAcc, HRR, URR, RC | 0.9244 | 0.9860 | 0.0000 | 0.0000 | 0.9644 | 29.83 |

## 表 14 DE 相对人工权重变化

| Split | ΔRouteAcc | ΔHRR | ΔURR | ΔUCR | ΔRC | ΔP95 Latency |
| --- | --- | --- | --- | --- | --- | --- |
| clean | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | -1.76 |
| robust | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.21 |

## 表 15 安全性指标

| Method | Clean HRR | Clean HMR | Clean URR | Clean UCR | Robust HRR | Robust HMR | Robust URR | Robust UCR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vanilla-RAG | 0.0000 | 1.0000 | 0.0000 | 0.0044 | 0.0000 | 1.0000 | 0.0000 | 0.0044 |
| RAG-Guard | 0.0000 | 1.0000 | 0.0000 | 0.0044 | 0.0000 | 1.0000 | 0.0000 | 0.0044 |
| HSC-RAG-manual | 0.9860 | 0.0140 | 0.0000 | 0.0000 | 0.9860 | 0.0140 | 0.0000 | 0.0000 |
| HSC-RAG-DE | 0.9860 | 0.0140 | 0.0000 | 0.0000 | 0.9860 | 0.0140 | 0.0000 | 0.0000 |

## 表 16 效率指标

| Method | Avg Latency (ms) | P95 Latency (ms) | Avg Response Length |
| --- | --- | --- | --- |
| Vanilla-RAG | 40.10 | 85.36 | 23.6252 |
| RAG-Guard | 40.02 | 85.32 | 23.6252 |
| HSC-RAG-manual | 20.85 | 28.35 | 21.1793 |
| HSC-RAG-DE | 21.00 | 29.57 | 21.1793 |
