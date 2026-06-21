# 阶段 4 协议匹配置信度说明

阶段 4 位于论文 pipeline 的中前段：输入归一化和意图抽取之后，协议执行和 RAG 检索之前。该阶段接收 `canonical_text`、`routed_tags`、`events` 和 `IntentContext`，输出 `ProtocolMatchResult`。

## 模块定位

协议匹配置信度用于把协议匹配从单纯关键词触发扩展为可解释的启发式评分。它仍然是规则系统，不是训练模型，也不调用远端 LLM。

`confidence` 是工程评分，不是真实概率，不是医学判断，也不是临床分诊或救援严重程度预测。它只用于论文复现实验中的协议命中解释、trace 分析、metrics 统计和 ablation 对比。

## 输入信号

`match_with_score()` 使用以下信号计算协议匹配结果：

- 关键词：协议 trigger、keywords、aliases 中与文本直接匹配的词。
- 风险意图：来自 `IntentContext` 的 primary intent 和 secondary intents。
- 身体部位：例如腿、手、头、胸口等，辅助解释协议命中。
- 场景词：例如地震、废墟、被困、压住、余震等。
- tags：来自路由或意图抽取的标签。
- 事件：例如 `imu_strong_shake` 等硬件或运行时事件。
- 协议优先级：作为轻量 tie-breaker，不单独决定高置信度命中。
- 否定冲突：例如“没流血”“不是被困”等表达会降低或阻断高风险协议。

## 输出结构

`ProtocolMatchResult` 包含：

- `matched`
- `protocol_id`
- `protocol_name`
- `confidence`
- `priority`
- `matched_terms`
- `body_part_matches`
- `scene_matches`
- `negation_conflict`
- `reason`
- `protocol`
- `score_breakdown`
- `threshold`
- `active_risks`
- `negated_risks`
- `protocol_risks`

其中 `reason` 和 `score_breakdown` 用于 trace 和错误分析。`protocol` 只在 `matched=True` 时作为 active protocol 返回；当 `matched=False` 时，主链路不应把候选协议当成 active hit。

## 否定与 none_of 冲突

`negation_conflict` 用于防止否定表达误触发高风险协议。例如“腿疼但是没流血”可以记录出血关键词命中，但 `severe_bleeding` 应来自 `negated_risks`，因此不应高置信度进入出血控制协议。

协议 trigger 中的 `none_of` 或 `exclude_words` 用于阻断特定冲突，例如“鼻血”不应触发普通严重出血控制协议。此类冲突会进入 reason，便于后续 trace 审计。

## match_with_score 与 match

`match_with_score()` 是论文主链路接口。它提供 confidence、reason、score_breakdown、否定冲突和可序列化 trace，是 paper eval 和 MoniSession 主链路应使用的接口。

`match()` 是旧接口兼容层，只返回协议 dict 或 None。它不作为 paper eval 的主要依据。为了避免 legacy fallback 覆盖置信度结果，当 `match_with_score()` 检测到 `negation_conflict` 时，`match()` 不再继续旧 trigger fallback。

## 后续阶段使用

阶段 6 trace 应保留 `protocol_match.to_dict()`、`protocol_confidence`、`protocol_matched_terms` 和 `protocol_match_reason`。

阶段 7 metrics 可以统计协议命中率、否定冲突、none_of 冲突、event trigger 命中和高风险协议误触发。

阶段 9 ablation 可以比较有无意图上下文、身体部位、场景词或否定冲突处理时的协议命中变化。

阶段 11 表格导出可以从离线实验结果中汇总协议置信度、协议错误类型和冲突阻断数量。
