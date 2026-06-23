# 论文表格清单

本文件列出阶段 11 导出的论文表格。所有表格均来自 `build/eval` 下已有实验产物，不应手写或编造数值。当前 clean/robust 数据仍为 dev/smoke，表格结果不能直接写成最终 SCI test set 结论。

## Table 1: main_results

路径：`build/eval/main_results.csv`

来源：阶段 11 从 clean evaluation summary 导出。

主要字段：`method`、`route_accuracy`、`evidence_hit_at_5`、`high_risk_recall`、`unsafe_response_rate`、`unsupported_claim_rate`、`avg_latency_ms`、`p95_latency_ms` 以及 count 字段。

论文位置：第 5 节实验结果，clean evaluation 主结果。

分母说明：需要报告 `num_cases`、`num_predictions`、`num_evidence_eval_cases`、`num_high_risk_cases`、`num_protocol_eval_cases`。其中 `num_evidence_eval_cases` 对解释 evidence 指标尤其重要。

边界：仅作为 dev/smoke 结果。

## Table 2: robustness_results

路径：`build/eval/robustness_results.csv`

来源：阶段 11 从 robust evaluation summary 导出。

主要字段：`method`、`robust_route_accuracy`、`primary_intent_accuracy`、`protocol_false_trigger_rate`、`robust_consistency`、`unsafe_response_rate` 以及 count 字段。

论文位置：第 5 节实验结果，robust evaluation。

分母说明：需要报告 `num_cases`、`num_predictions`、`num_evidence_eval_cases`、`num_high_risk_cases`、`num_protocol_eval_cases`。

边界：robust 数据来自 dev/smoke 扰动，不等同真实灾害现场 test set。

## Table 3: ablation_results

路径：`build/eval/ablation_results.csv`

来源：阶段 11 从 ablation summary 导出。

主要字段：`ablation`、`disabled_modules`、`route_accuracy`、`robust_route_accuracy`、`high_risk_recall`、`unsafe_response_rate`、`num_cases`、`num_predictions`、`num_high_risk_cases`。

论文位置：第 5 节实验结果，模块消融分析。

分母说明：至少报告 `num_cases`、`num_predictions` 和 `num_high_risk_cases`。

边界：消融结果用于解释模块贡献，不应被解读为真实部署性能保证。

## Table 4: de_effect_results

路径：`build/eval/de_effect_results.csv`

来源：阶段 11 从 `build/eval/de_best_metrics.json` 导出。

主要字段：`policy`、`fitness`、`clean_route_accuracy`、`robust_route_accuracy`、`high_risk_miss_rate`、`unsafe_response_rate`。

论文位置：第 5 节实验结果，DE 权重搜索效果。

分母说明：需要结合 DE 使用的数据集说明，DE 只使用 dev 数据，不使用 final test set。

边界：DE 优化的是 HSC-RAG scoring coefficients，不是训练模型参数或医学规则。

## Table 5: latency_memory_results

路径：`build/eval/latency_memory_results.csv`

来源：阶段 11 从所有 summary 中提取 latency 相关字段。

主要字段：`method`、`suite`、`avg_latency_ms`、`p95_latency_ms`、`num_cases`。

论文位置：第 5 节或第 6 节，工程开销与离线部署讨论。

分母说明：需要报告 `num_cases`。

边界：当前表只有 CSV 输出；如需 Markdown，可由阶段 11 脚本后续扩展。

## Table 6: trace_audit_results

路径：`build/eval/trace_audit_results.csv`

来源：阶段 11 从 `*_predictions.jsonl` 的 `prediction["trace"]` 派生。

主要字段：`method`、`suite`、`num_predictions`、`num_with_trace`、`num_low_evidence`、`low_evidence_rate`、`num_protocol_decisions`、`avg_protocol_confidence`、`num_guarded`、`num_with_top_chunks`、`num_with_score_breakdown`。

论文位置：第 5 节 trace audit 或第 6 节错误分析。

分母说明：需要报告 `num_predictions` 和 `num_with_trace`。

边界：trace audit 是实验解释工具，不是用户隐私日志，不用于长期保存真实敏感输入。
