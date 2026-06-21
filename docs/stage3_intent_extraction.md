# 阶段 3 风险感知多意图抽取说明

阶段 3 位于论文 pipeline 的前段：输入归一化之后，协议匹配和 RAG 检索之前。该模块接收的是 `canonical_text`，不是原始 `raw_text`。输出为 `IntentContext`，供协议置信度、RAG 标签、trace 解释和后续指标分析使用。

## 模块定位

风险感知多意图抽取用于从规范化后的用户文本中识别启发式意图信号，例如呼吸困难、严重出血、被困/挤压、头部或意识异常、余震/坍塌、失温、脱水、疼痛/受伤、恐慌和低电量等。

该模块不是医学诊断模型，不是临床分诊系统，也不预测真实救援严重程度。`risk_score` 是工程启发式评分，用于在论文实验中稳定排序风险意图、解释路由行为和支持 ablation，不应被解释为医学评分。

## Primary 与 Secondary Intents

`primary_intent` 表示当前输入中按照预设风险优先级选出的主意图。它用于 trace、协议匹配辅助和结果统计。

`secondary_intents` 表示同一输入中同时出现但优先级低于主意图的其他 active intents。多意图抽取用于处理灾害场景中常见的复合求助，例如“喘不上气，还很冷，也很渴”。

优先级是论文工程中的安全启发式规则，而不是对真实医学严重程度的临床判断。

## 否定风险处理

当高风险词出现在否定表达附近时，该风险进入 `negated_risks`，不作为 active intent。否定风险仍会保留在 `matched_terms` 和 `explanation` 中，以便后续错误分析。

例如“腿疼但是没流血”中，`severe_bleeding` 应记录为 negated risk，而主意图应由“腿疼”触发为 `pain_or_injury`。

该原则用于避免把“没有流血”“没有喘不上气”“不是被困”等表达错误升级为高风险主意图。

## Body Parts 与 Scene Terms

`body_parts` 提取文本中的身体部位，例如腿、手、头、胸口等。`scene_terms` 提取灾害场景词，例如地震、废墟、被困、压住等。

这些字段不单独决定医学结论，而是为协议置信度、RAG 标签和 trace 解释提供辅助信号。它们也会进入 tags，例如 `body:腿`、`scene:地震`。

## Matched Terms 与 Explanation

`matched_terms` 记录每个命中的意图词，包括 intent、term、clause、negated、start 和 end。start/end 表示匹配词在 normalized text 中的位置，用于定位触发主意图或次意图的具体片段。

`explanation` 记录简短的可解释原因，例如某个 intent 命中了某个 term，或该 term 被否定。它用于论文 trace、错误分析和 ablation，不作为用户可见输出。

`IntentContext.to_dict()` 还提供轻量统计字段：

- `num_active_intents`
- `num_secondary_intents`
- `num_negated_risks`
- `has_high_risk_intent`

这些字段用于后续 benchmark 统计和鲁棒性分析。

## 后续阶段使用

阶段 4 的协议置信度可以使用 primary intent、secondary intents、body_parts、scene_terms、negated_risks 和 matched_terms 辅助判断协议命中质量。

阶段 6 的 trace 应保留完整 `intent_context`，用于解释输入归一化、意图抽取、协议匹配和 RAG 检索之间的关系。

阶段 7 的 metrics 可以统计多意图命中、否定风险处理和高风险 intent 的稳定性。

阶段 9 的 ablation 可以关闭或替换多意图抽取，评估其对 clean evaluation、robust evaluation、协议命中和安全输出的贡献。
