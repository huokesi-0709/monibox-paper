# 阶段 11：实验结果导出表格

阶段 11 的作用是从已有实验产物中导出论文表格。该阶段只读取 `build/eval` 下已经生成的 summary、predictions 和 DE 结果，不重新运行 benchmark，不调用远端 LLM，也不修改 metrics 计算逻辑。

## 输入与输出

默认输入目录：

```bash
build/eval
```

默认输出：

- CSV：写入 `build/eval`
- Markdown：写入 `build/eval/tables`

推荐命令：

```bash
python -m experiments.export_tables --eval-dir build/eval --out-dir build/eval/tables
```

脚本入口：

```bash
scripts/export_tables.sh
```

## 表格说明

`main_results`：汇总 clean evaluation 中主方法和对照方法的核心指标。主要字段包括 `method`、`route_accuracy`、`evidence_hit_at_5`、`high_risk_recall`、`unsafe_response_rate`、`unsupported_claim_rate`、latency 以及 count 字段。

`robustness_results`：汇总 robust evaluation 指标。主要字段包括 `robust_route_accuracy`、`primary_intent_accuracy`、`protocol_false_trigger_rate`、`robust_consistency`、`unsafe_response_rate` 以及 count 字段。

`ablation_results`：汇总消融实验结果。主要字段包括 `ablation`、`disabled_modules`、clean/robust route accuracy、`high_risk_recall`、`unsafe_response_rate` 和 count 字段。

`de_effect_results`：从 `de_best_metrics.json` 中导出 DE 权重搜索效果，包括 policy、fitness、clean/robust route accuracy、high-risk miss rate 和 unsafe response rate。

`latency_memory_results`：导出每个 summary 的 latency 和样本数。目前该表只输出 CSV，不额外输出 Markdown。

`trace_audit_results`：从 `*_predictions.jsonl` 派生实验 trace 审计表。字段包括 `method`、`suite`、`num_predictions`、`num_with_trace`、`num_low_evidence`、`low_evidence_rate`、`num_protocol_decisions`、`avg_protocol_confidence`、`num_guarded`、`num_with_top_chunks` 和 `num_with_score_breakdown`。

## count 字段

main 和 robust 表包含：

- `num_cases`
- `num_predictions`
- `num_evidence_eval_cases`
- `num_high_risk_cases`
- `num_protocol_eval_cases`

ablation 表包含：

- `num_cases`
- `num_predictions`
- `num_high_risk_cases`

这些字段用于解释指标分母，尤其是 `num_evidence_eval_cases`。如果 evidence 分母为 0 或很小，不能把 `evidence_hit_at_5` 或 `evidence_hit_at_3` 解释为稳定的 RAG 证据能力结论。

当前导出中 `evidence_hit_at_5` 会 fallback 到 `evidence_hit_at_3`，这是为了兼容阶段 7 已有 metrics；论文表述时应说明实际可用 evidence 指标来自当前 summary 中的字段。

## trace audit 边界

`trace_audit_results` 用于实验解释和错误分析，例如检查低证据分流、协议置信度、guard 触发和 top chunk score breakdown 是否被保留。

trace audit 不是用户隐私日志，不应扩展为长期存储真实用户敏感信息的机制。导表脚本只统计结构化字段，不重新解释用户原文。

## 缺失输入

如果输入目录缺少 summary、DE 结果或 predictions，脚本会输出 warning，并写出带表头的空表。空表只能说明输入产物缺失，不能作为实验结论。

## 数据边界

当前 `clean_dev.jsonl` 和 `robustness_dev.jsonl` 仍是 dev/smoke 数据，不是最终论文 test set。阶段 12 写论文中文稿时可以引用这些表格作为工程复现与开发集实验产物，但不能把 dev/smoke 结果写成最终 SCI 结论。
