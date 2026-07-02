# 论文表格清单

当前表格清单对应 RAIR-RAG-Bench。不要从 `artifacts/paper_final_v2/`、`build/eval/final_v2/` 或 HSC-DisasterBench-v2 复制主表数字。

## Table 1: RAIR-RAG-Bench Dataset Summary

来源：

```text
benchmarks/rair_rag/data/gold/label_distribution.json
benchmarks/rair_rag/data/split_manifest.json
benchmarks/rair_rag/data/README.md
```

应报告总样本数、dev/test split、perturbation type、primary_intent、risk_level、source_type，以及 guideline evidence scope。

## Table 2: Main Test Results

来源：

```text
build/rair_eval/rair_test_keyword-baseline_summary.json
build/rair_eval/rair_test_no-negation_summary.json
build/rair_eval/rair_test_single-intent_summary.json
build/rair_eval/rair_test_risk-router-manual_summary.json
build/rair_eval/rair_test_risk-router-de_summary.json
build/rair_eval/trace_audit_results.csv
```

主要字段：RouteAcc、HRR、PFTR、NegRiskF1、SecondaryIntentF1、ConstraintF1。

## Table 3: Negation Conflict Subset

来源：

```text
build/rair_eval/rair_test_negation_*_summary.json
```

重点字段：RouteAcc、PFTR、NegRiskExact、NegRiskF1。该表用于证明否定消解降低协议误触发。

## Table 4: Multi-Intent Subset

来源：

```text
build/rair_eval/rair_test_multi_intent_*_summary.json
```

重点字段：RouteAcc、HRR、SecondaryIntentF1、ConstraintF1。该表用于证明风险优先级路由和 secondary intents 保留价值。

## Table 5: DE Calibration

来源：

```text
build/rair_eval/de_summary.json
build/rair_eval/de_trials.jsonl
scoring/routing_policy_manual.yaml
scoring/routing_policy_de.yaml
```

当前结论应如实报告：DE 框架已接入，但当前运行未找到优于 manual baseline 的可行策略，因此不能把 DE 写成主要性能提升来源。

## Legacy Tables

`artifacts/paper_final_v2/tables/` 中的表格属于 HSC-RAG-DE / HSC-DisasterBench-v2 历史归档。它们只能用于附录背景或方法演进说明，不进入当前 RAIR-RAG 主表。
