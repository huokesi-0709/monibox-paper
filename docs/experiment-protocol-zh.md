# 实验协议

本文实验用于评估 HSC-RAG 在灾害受困文本输入下的离线回复生成能力。所有实验必须通过配置和脚本运行，不通过手工修改源码完成。

## Dev/Test 分离

- dev 集用于开发、调参、阈值选择、错误分析和 DE 离线权重优化。
- test 集只用于最终一次性报告结果。
- DE 不允许在 test 集上优化，不允许根据 test 指标反复改权重。
- 表格中的 test 结果必须标明生成日期、policy 版本和 profile。

当前仓库小样例以 `clean_dev.jsonl` 和 `robustness_dev.jsonl` 为主；正式论文实验应补齐独立 test 集。

## Methods

- `rule-only`：规则回复基线，不使用完整 RAG。
- `vanilla-rag`：关闭输入归一化、多意图、协议门控、安全重排、低证据分流和输出护栏。
- `rag-guard`：在 vanilla RAG 上开启输出安全护栏。
- `hsc-rag-manual`：完整 HSC-RAG，使用 `scoring/policy_manual.json`。
- `hsc-rag-de`：完整 HSC-RAG，使用 `scoring/policy_de.json`。

## Ablations

- `without_input_normalization`
- `without_multi_intent`
- `without_negation`
- `without_protocol_gate`
- `without_safety_rerank`
- `without_low_evidence`
- `without_guard`
- `without_de_optimization`

消融必须通过 `benchmarks.run_eval --ablation ...` 配置完成，不允许通过手工注释代码完成。

## Metrics

- route accuracy：预测主路由是否等于 expected route。
- protocol hit rate：预测协议 ID 是否等于 expected protocol ID。
- high-risk recall：高风险样本是否被识别为高风险。
- high-risk miss rate：`1 - high-risk recall`。
- evidence hit@k：top-k chunk 是否命中 gold chunk。
- unsafe response rate：回复是否包含样本标注的 unsafe actions。
- unsupported claim rate：回复是否包含保证获救、准确诊断等 unsupported claim。
- primary intent accuracy：预测 primary intent 是否正确。
- protocol false trigger rate：无协议样本是否误触发协议。
- robust consistency：同一 clean query 的扰动样本是否保持一致 route/protocol。
- latency：平均延迟与 p95 延迟。

## 输出路径

- predictions JSONL：`build/eval/**/**/*_predictions.jsonl`
- summary JSON/CSV：`build/eval/**/*_summary.json` 和 `build/eval/**/*_summary.csv`
- DE trials：`build/eval/de_trials.csv`
- 自动表格：`build/eval/*.csv` 和 `build/eval/tables/*.md`
- trace：`build/eval/traces/*.jsonl`

## 安全边界

实验只评价应急信息辅助，不评价真实救援成功率。系统不替代专业救援，不保证救援成功，不提供医学诊断或高风险医疗操作建议。
