# 阶段 7：benchmark schema、metrics 与运行输出

> [!WARNING]
> OBSOLETE / HISTORICAL: This document is retained only as project history. Do not use it as the current RAIR-RAG paper or reproduction source. Current canonical entry points are `docs/RAIR_RAG_routing_reproduction.md`, `docs/RAIR_RAG_downstream_reproduction.md`, `models/README.md`, and `models/llm/README.md`.

本文档说明 MoniBox / HSC-RAG-DE 论文复现实验中 benchmark 数据、预测输出、指标计算和结果表的工程边界。阶段 7 的目标是使 clean evaluation、robust evaluation、ablation 和后续表格导出具备稳定的输入输出契约，而不是扩充数据集或改变主实验方法。

## 数据 schema

benchmark case 使用 JSONL，每行是一个独立样本。当前入口为：

- `benchmarks/data/clean_dev.jsonl`
- `benchmarks/data/robustness_dev.jsonl`

每条 case 至少需要非空 `id` 和非空 `query`。可选字段包括：

- `risk_level`：如存在，应属于 `low`、`medium`、`high`、`critical`。
- `expected_route`：期望路由或主风险路径，用于 route accuracy。
- `expected_protocol_id`：期望协议 id；空字符串或 `null` 表示该样本不要求协议命中。
- `expected_primary_intent`：期望主意图，应属于仓库内定义的 intent 集合。
- `expected_tags`：字符串列表，用于后续标签覆盖和错误分析。
- `gold_chunk_ids`：字符串列表，用于 evidence hit 类指标。
- `unsafe_actions`：字符串列表，用于检测回复中是否出现危险建议或过度承诺。
- `reference_reply`：开发阶段参考回复，不作为当前自动指标的唯一标准答案。

schema 校验在 `benchmarks/schema.py` 中执行。加载失败时应报告文件路径、行号和 case id，便于定位数据问题。

## 数据集定位

当前 clean 与 robust 数据仍属于 dev/evaluation prototype。它们用于验证实验链路、指标计算、trace 保留和方法对比流程，不等同于最终 SCI 论文完整数据集。

最终 SCI 实验仍需要扩展样本规模、覆盖更多风险等级和场景，并补齐 gold evidence 标注。阶段 7 不修改 `.jsonl` 数据本身。

## 运行入口

推荐通过阶段 0/1 固定的 paper profile 和脚本运行：

```bash
scripts/run_clean_eval.sh
scripts/run_robust_eval.sh
scripts/run_de_optimize.sh
scripts/run_ablation.sh
scripts/export_tables.sh
```

脚本应使用 `profiles/paper_eval.yaml`。该 profile 默认关闭远端 LLM、rewrite、TTS 和硬件接口，以避免本地开发环境影响论文复现结果。

## 输出文件

`benchmarks/run_eval.py` 生成三类主要产物：

- predictions JSONL：逐样本预测，每行包含 `case`、`case_id`、`query`、`method`、`reply`、`trace`、`primary_intent`、`protocol_id` 和 `latency_ms`。
- summary CSV/JSON：单次运行的指标摘要，包含方法、数据路径、profile、policy、ablation、disabled modules 和所有 metrics。
- results table：主实验写入 `main_results.csv/json`，消融实验写入 `ablation_results.csv/json`。

prediction 中的 `trace.metadata` 应保留 `method`、`disabled_modules`、`profile`、`policy`、`ablation`、`data_path`，并在可推断时保留 `suite`。

## 指标与计数

`benchmarks/metrics.py` 保留原有指标，并在 `compute_all_metrics()` 中补充指标分母计数：

- `num_cases`
- `num_predictions`
- `num_route_eval_cases`
- `num_protocol_eval_cases`
- `num_primary_intent_eval_cases`
- `num_evidence_eval_cases`
- `num_high_risk_cases`

主要指标包括：

- `route_accuracy`
- `protocol_hit_rate`
- `high_risk_recall`
- `high_risk_miss_rate`
- `evidence_hit_at_3`
- `unsafe_response_rate`
- `unsupported_claim_rate`
- `primary_intent_accuracy`
- `protocol_false_trigger_rate`
- `robust_consistency`
- `avg_latency_ms`
- `p95_latency_ms`
- `avg_response_length`

`compute_all_metrics()` 要求 case 数量与 prediction 数量一致；长度不一致时直接失败，避免静默截断导致指标偏移。

## gold evidence 边界

`gold_chunk_ids` 是 RAG 证据评价的关键字段，用于计算 `evidence_hit_at_3` 以及后续可能引入的 grounding coverage 等指标。

如果当前数据集中 `num_evidence_eval_cases = 0`，则 `evidence_hit_at_3` 只能表示“没有可评价的 gold evidence 样本”，不能解释为模型证据检索能力为 0 或完全失败。最终 SCI 实验必须补齐每个应急问题对应的 1 到 3 个 gold evidence chunk。

## robust evaluation

robust case 应从 clean case 派生，并通过 `clean_id`、`canonical_id` 或 `clean_query` 保留与原始 clean case 的关系。`robust_consistency` 使用 clean query 分组比较 route 和 protocol 是否稳定。

当前 robust 数据用于 smoke/dev 评估。后续应增加自动或半自动 perturbation generator，并覆盖 ASR 同音错误、filler noise、repetition、long context、multi-intent、negation conflict 和 out-of-scope distraction 等扰动类型。

## 后续阶段使用

- 阶段 8/9：基于 summary 和 predictions 比较不同方法与消融设置。
- 阶段 10：使用稳定 metrics 评估 DE policy 权重搜索结果。
- 阶段 11：从 summary、results table 和 trace 中导出论文表格。
- 最终报告：应同时报告指标值和对应的 `num_*_eval_cases`，避免在分母不足时过度解释指标。
