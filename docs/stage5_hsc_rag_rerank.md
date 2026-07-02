# 阶段 5 HSC-RAG 安全约束重排说明

> [!WARNING]
> OBSOLETE / HISTORICAL: This document is retained only as project history. Do not use it as the current RAIR-RAG paper or reproduction source. Current canonical entry points are `docs/RAIR_RAG_routing_reproduction.md`, `docs/RAIR_RAG_downstream_reproduction.md`, `models/README.md`, and `models/llm/README.md`.

阶段 5 位于论文 pipeline 的 RAG 分支：当协议未命中，或主链路需要基于知识库生成回复时，对候选知识片段进行安全约束重排。该阶段发生在输入归一化、意图抽取和协议匹配之后，RAG 生成之前。

## 输入与输出

HSC-RAG 重排的输入包括：

- `canonical_text`：经过输入归一化后的用户文本。
- candidate chunks：向量检索或 fallback lexical retrieval 生成的候选知识片段。
- `routed_tags`：路由器提供的标签。
- `IntentContext`：阶段 3 产生的 primary intent、secondary intents、body_parts、scene_terms、tags 和 negated_risks。
- `HscRagPolicy`：manual policy 或 DE policy 的权重配置。

输出是重排后的 chunks。每个 chunk 应带有 `score_breakdown`，用于 trace 和后续指标分析。

## 方法边界

HSC-RAG 重排是启发式工程评分，不是训练模型，不是医学诊断，不是临床分诊，也不是自由生成能力。它的目标是在离线 RAG 候选片段中提升安全、相关、可解释的证据片段，并降低危险建议、过度承诺和冗余片段的排序。

该模块不修改知识库内容，不调用远端 LLM，也不替代专业救援判断。

## 评分因子

- `sim_vec`：向量相似度，由候选片段的向量距离转换而来。
- `sim_sparse`：稀疏词面重合度，用于补充短文本和关键词匹配。
- `quality`：知识片段的人工或构建侧质量分。
- `tag_match`：候选片段与 routed_tags、IntentContext tags、body_parts、scene_terms 的匹配程度。
- `risk_match`：候选片段是否覆盖当前 active risk，例如 severe_bleeding、respiratory_distress 或 trapped_or_crush。
- `unsafe`：候选片段中是否包含止血带、注射、药物剂量、保证获救等危险或过度承诺模式。
- `redundancy`：候选片段与已选片段的词面重复程度，用于降低重复证据。

`final_score` 由这些因子按 `HscRagPolicy` 权重合成。`final_distance` 是为了兼容旧接口而从 `final_score` 转换得到的排序辅助字段。

## Manual Policy 与 DE Policy

manual policy 是人工设定的权重配置，用于可读、可控的基线实验。

DE policy 是离线权重搜索结果，用于在 dev/evaluation 数据上校准安全重排权重。DE 在本文中优化的是 HSC-RAG 重排权重，不是提出新的进化算法本身。

正式论文实验应明确记录使用的 policy 版本，并避免把 test/final reporting set 用于权重搜索。

## 候选生成与工程保护

fallback lexical retrieval、query adjustment、whitelist 和 blacklist 属于候选生成与工程保护机制。它们用于在向量检索不可用、短文本输入或已知误召回场景下维持链路稳定，不应被夸大为 HSC-RAG 的主要论文贡献。

HSC-RAG 的论文主张应集中在安全约束重排、意图感知风险匹配、unsafe penalty、redundancy penalty 和可解释 score_breakdown。

## 后续阶段使用

阶段 6 trace 应保留 top_chunks 和每个 chunk 的 `score_breakdown`，用于解释检索证据为什么被选中或降权。

阶段 7 metrics 可使用 evidence_hit@k、grounding coverage、unsafe_response_rate 等指标评估 RAG 证据质量和安全性。

阶段 9 ablation 可比较 vector-only 与 HSC-RAG，评估安全约束重排、risk/tag/body/scene 信号和 unsafe penalty 的贡献。

阶段 10 DE 优化可对 `HscRagPolicy` 权重进行离线搜索，并将最优权重固化为 DE policy。
