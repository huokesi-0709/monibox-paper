# Benchmark 数据集说明

本文档说明 `benchmarks/data/` 下开发阶段 benchmark 数据的定位、字段含义、鲁棒样例构造规则和后续扩展要求。该目录服务于 MoniBox / HSC-RAG-DE 的论文复现实验链路，重点是让 clean evaluation、robust evaluation、指标计算和方法对比具备可追踪的数据约定。

## 数据集定位

当前目录包含：

- `clean_dev.jsonl`：clean evaluation 的开发阶段样例。
- `robustness_dev.jsonl`：robust evaluation 的开发阶段扰动样例。

这两份文件是 dev/evaluation prototype，用于验证实验链路、指标计算、方法对比和表格导出流程是否可运行、可复现、可解释。它们不等同于最终 SCI 论文完整数据集，也不应被表述为已经覆盖真实灾害现场的完整风险分布。

后续正式实验应在保持字段 schema 稳定的前提下扩展样例规模、补齐 gold evidence 标注，并记录数据来源、构造规则、标注规范和质控流程。

## Clean Case 字段说明

`clean_dev.jsonl` 中每一行是一条 JSONL 样例，建议字段含义如下：

- `id`：样例唯一标识符。clean 样例建议使用稳定、可排序的编号，例如 `clean_001`。
- `query`：实际送入系统的用户输入文本。clean case 中通常与 `clean_query` 一致。
- `clean_query`：规范化后的干净问题文本，用作鲁棒扰动样例的原始来源和语义参照。
- `perturbation_type`：扰动类型。clean case 应为 `clean`。
- `risk_level`：风险等级。建议取值包括 `high`、`medium`、`low`、`out-of-scope`，用于区分高风险应急、一般风险、低风险安抚和超出系统能力范围的问题。
- `expected_route`：期望路由结果，用于评估路由器或主链路是否将问题分配到正确的应急处理分支。
- `expected_protocol_id`：期望匹配的协议 ID，用于检查协议优先策略和协议检索是否命中预期规则。
- `expected_primary_intent`：期望主意图，用于评估意图识别、路由和下游策略选择。
- `expected_tags`：期望标签集合，用于描述样例涉及的关键症状、场景或约束条件。
- `gold_chunk_ids`：期望命中的证据 chunk ID 列表，用于后续 RAG 证据指标评估。
- `unsafe_actions`：该样例中需要重点检测和避免的危险建议或不当输出模式。
- `reference_reply`：参考回复，用于给出最低限度的安全回复方向。该字段不是唯一正确答案，也不应替代基于证据和评分规则的系统性评价。

## Robust Case 构造说明

`robustness_dev.jsonl` 中的 robust case 应从 clean case 派生。每条 robust case 应尽量保留可追踪关系，例如使用 `clean_id` 或 `canonical_id` 指向来源 clean case，并保留 `clean_query` 作为语义参照。

鲁棒扰动的目标是测试方法在输入噪声、上下文干扰和意图冲突下是否仍能保持安全、克制和协议一致。扰动类型可以包括：

- ASR 同音错误：模拟语音识别中的同音字、近音字或词边界错误。
- filler noise：加入“呃”“就是”“那个”等口语填充噪声。
- repetition：重复关键片段或重复求助表达，测试系统对重复输入的稳定性。
- long context：加入较长背景描述或非关键信息，测试系统是否能定位主要风险。
- multi-intent：在同一输入中包含多个求助意图，测试系统是否能识别优先级。
- negation conflict：加入否定、转折或冲突描述，测试系统是否错误触发高风险协议。
- out-of-scope distraction：加入与应急回复无关或超出系统能力范围的干扰信息，测试系统是否能拒答、降级或分流。

robust case 不应随意改变原始问题的风险事实。若扰动改变了核心语义，例如从“严重出血”变为“无出血但疼痛”，则应同步更新 `risk_level`、`expected_route`、`expected_protocol_id`、`expected_primary_intent`、`expected_tags` 和 `reference_reply`。

## gold_chunk_ids 标注规范

每个应急问题最终应绑定 1 到 3 个 gold evidence chunk。gold evidence 应是能够支持参考回复、安全约束或协议决策的最小证据单元，优先选择直接对应症状、风险处理原则或禁止动作的 chunk。

如果当前 `gold_chunk_ids` 为空，应明确视为阶段 0 遗留问题。后续 RAG 证据评估阶段必须补齐该字段，否则无法严格评估检索证据是否支持最终回复。

`gold_chunk_ids` 的主要用途包括：

- 计算 `evidence_hit@k`，检查检索 Top-k 中是否包含 gold evidence。
- 计算 grounding coverage，检查回复是否覆盖或遵循关键证据。
- 分析 RAG 失败原因，区分“未检索到证据”和“检索到证据但生成/重排未使用证据”。
- 支持 ablation 中对检索、重排、安全约束和协议优先策略的分层诊断。

后续标注时应保证 chunk ID 与构建后的知识库版本一致，并记录知识库版本、chunk 切分规则和标注人/审核人信息。

## unsafe_actions 标注规范

`unsafe_actions` 用于检测模型回复中是否出现危险建议、过度承诺、药物剂量、错误自救动作或其他不应输出的内容。该字段不表示用户已经执行了这些动作，而是表示评价时需要重点拦截的风险模式。

常见 unsafe action 类型包括：

- 危险自救动作，例如强行移动被压肢体、贸然拔出异物、在不具备条件时使用止血带。
- 过度承诺，例如保证获救、保证安全、承诺具体救援时间。
- 药物相关不当建议，例如给出具体药物剂量、建议自行注射或替代医生判断。
- 错误风险判断，例如将高风险症状简单归为无需处理，或鼓励继续活动。
- 超出系统职责的建议，例如替代专业救援、医疗诊断或现场指挥。

评价脚本可使用该字段检查回复中是否触发危险关键词或危险语义模式。正式实验中建议进一步区分关键词匹配、人工复核和语义级安全评估。

## 数据规模建议

后续最终实验建议在当前 dev prototype 基础上扩展：

- clean cases 不少于 80 到 150 条，覆盖主要灾害受困、伤情、呼吸、出血、挤压、情绪安抚、定位求助和超范围问题。
- robust cases 可由 clean cases 派生，每条 clean case 生成 3 到 6 个扰动样本。
- 最终数据集应覆盖 `high`、`medium`、`low`、`out-of-scope` 多种风险等级，并报告各风险等级、意图类别、协议类别和扰动类型的数量分布。
- final reporting set 应与开发调参数据分离，避免 DE 权重搜索、提示词调整或规则修改直接使用最终报告集。

## 后续阶段 TODO

- 扩展 clean 数据规模。
- 设计自动或半自动 perturbation generator。
- 补齐 `gold_chunk_ids`。
- 增加数据集统计脚本。
- 增加标注一致性检查。
- 增加数据 schema 校验测试。
