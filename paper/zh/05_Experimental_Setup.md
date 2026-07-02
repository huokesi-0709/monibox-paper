# Experimental Setup

## Data Leakage and Duplicate Text Audit

RAIR-RAG-Bench splitting is leakage-safe at both the `canonical_id` level and the normalized text level. Cases connected by the same `canonical_id`, normalized `raw_input`, or normalized `canonical_input` are kept in the same split.

The current regenerated release has zero exact normalized `raw_input` overlap between dev and test, zero exact normalized `canonical_input` overlap between dev and test, and zero exact duplicate `raw_input`/`canonical_input` groups in gold. If future template generation introduces repeated raw texts, the release must either deduplicate them or document them as intentional template variants in the data card.

## Research Questions

RQ1：在 RAIR-RAG-Bench 上，风险感知输入路由是否能提升主路由准确率、降低高风险意图漏检，并保持较低协议误触发率？

RQ2：在否定冲突输入中，显式否定消解是否能降低 Protocol False Trigger Rate（PFTR）？

RQ3：在多意图输入中，风险优先级路由是否能提升高风险召回（HRR）并保留有效 secondary intents？

RQ4：DE 仅使用 dev split 校准 routing policy 参数时，是否能优于 manual routing policy？若不能，应报告为无显著改进或未找到可行优于人工策略的 policy。

## Dataset

当前论文使用 `benchmarks/rair_rag/` 下的 RAIR-RAG-Bench，而不是 `artifacts/paper_final_v2/` 中的 HSC-DisasterBench-v2。

主文件：

```text
benchmarks/rair_rag/data/gold/rair_gold_all.jsonl
benchmarks/rair_rag/data/dev/rair_dev.jsonl
benchmarks/rair_rag/data/test/rair_test.jsonl
benchmarks/rair_rag/data/test/rair_test_negation.jsonl
benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl
benchmarks/rair_rag/data/split_manifest.json
```

数据集应表述为 guideline-informed, human-reviewed synthetic benchmark。`guideline_refs` 是标签级 guideline mapping；带有 `pending_source_confirmation` 的中文来源不能写成已经逐样本完全确认的权威证据链。`reference_reply` 当前未填，不作为评测字段。

dev split 仅用于开发、阈值选择和 DE 校准。test、test_negation、test_multi_intent 只用于最终报告。

## Methods

比较方法包括：

- `keyword-baseline`：基于首个文本关键词命中的路由基线。
- `no-negation`：不处理否定冲突，把所有风险词都作为正向风险。
- `single-intent`：处理否定，但只选择单个最高置信度意图，不建模多意图优先级。
- `bert-multilabel`：使用 `bert-base-chinese` 训练的多标签分类基线。该模型只使用 dev pool 训练和模型选择：`benchmarks/rair_rag/data/dev/rair_dev.jsonl` 共 322 条，经 `prepare_bert_multilabel_split.py` 按 canonical_id 分组、seed=42、train_ratio=0.8 切分为 264 条训练集和 58 条验证集。最终报告的 480 条主测试集 `benchmarks/rair_rag/data/test/rair_test.jsonl` 从不参与训练、阈值选择或最佳 epoch 选择；当前检查显示训练/验证集与测试集在 `id` 和 `canonical_id` 上均为 0 重叠。BERT 阈值固定为 0.5，最佳模型按验证集 micro-F1 选择。
- `risk-router-manual`：使用人工 routing policy 的完整 RAIR-RAG 路由器。
- `risk-router-de`：使用 dev split 上 DE 校准得到的 routing policy。

## Metrics

主要指标：

- RouteAcc：预测路由是否等于 gold expected_route。
- HRR：high/critical 或高风险意图样本中的高风险召回。
- PFTR：协议误触发率，尤其用于否定冲突评估。
- NegRiskF1：被否定风险集合的 micro-F1。
- SecondaryIntentF1：次要意图集合的 micro-F1。
- ConstraintF1：运行约束集合的 micro-F1。
- SafeResponseRate：生成评估中的逐样本安全通过率，不是加权平均。自动 rubric 首先计算 `CorrectProtocolUse`、`NegatedRiskAvoidance`、`HighRiskActionRecall` 等二值子项；若回复含危险关键词，或上述三个阻断项任一为 0，则该样本 `SafeResponse=0`，否则 `SafeResponse=1`。`SafeResponseRate` 是所有完成生成样本上的 `SafeResponse` 均值。例如 0.5896 表示约 58.96% 的完成样本通过该规则化安全预评分；该指标是可复现的自动预评分，不替代人工医学或应急安全审查。

## Result Sources

当前 RAIR-RAG 论文结果应来自：

```text
build/rair_eval/rair_test_*_summary.json
build/rair_eval/rair_test_negation_*_summary.json
build/rair_eval/rair_test_multi_intent_*_summary.json
build/rair_eval/de_summary.json
```

`artifacts/paper_final_v2/`、`build/eval/final_v2/`、`profiles/paper_eval.yaml` 和 HSC-DisasterBench-v2 相关结果只作为 legacy/HSC 历史归档，不进入当前 RAIR-RAG 主表。

## Safety Boundary

所有实验只评估灾害应急文本输入的风险路由能力，不评估医疗诊断能力，不声称系统可替代专业救援、急救人员或医疗人员。RAIR-RAG 的贡献限定在 RAG 检索前的风险上下文构建与路由控制。
