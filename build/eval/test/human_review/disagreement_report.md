# 数字评测复核分歧报告

用途：数字评测复核 / 辅助误差分析。请勿表述为专家人工评估。

## 完成情况

- 期望样本数：100
- A 标注数：100
- B 标注数：100
- C final 标注数：100
- A/B 是否都完成同一批 case_id + method：True

## A/B 一致性

- A/B 共同样本数：100
- A/B 一致率：1.0
- safety_disagreement 数量：0
- route_disagreement 数量：0
- protocol_disagreement 数量：0
- score_disagreement 数量：0

## Final 分数按方法汇总

| Method | Count | Final Safety Score | Final Usefulness Score | Final Brevity Score |
| --- | --- | --- | --- | --- |
| hsc-rag-de | 9 | 2.0 | 1.8889 | 2.0 |
| hsc-rag-manual | 9 | 1.8889 | 1.7778 | 2.0 |
| rag-guard | 9 | 0.8889 | 0.4444 | 1.8889 |
| vanilla-rag | 9 | 0.8889 | 0.4444 | 1.8889 |
| without_de_optimization | 8 | 2.0 | 1.75 | 2.0 |
| without_guard | 8 | 2.0 | 1.75 | 2.0 |
| without_input_normalization | 8 | 1.75 | 1.625 | 2.0 |
| without_low_evidence | 8 | 1.75 | 1.75 | 2.0 |
| without_multi_intent | 8 | 1.125 | 0.125 | 2.0 |
| without_negation | 8 | 2.0 | 1.875 | 2.0 |
| without_protocol_gate | 8 | 1.25 | 0.375 | 2.0 |
| without_safety_rerank | 8 | 2.0 | 1.875 | 2.0 |

## 典型分歧案例

- 暂无可展示分歧案例。

## Warnings

- 无
