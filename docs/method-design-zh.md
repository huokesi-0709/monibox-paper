# HSC-RAG 方法设计说明

## 总体思路

HSC-RAG 是 heuristic safety-constrained retrieval-augmented generation。它不是单纯的 RAG 检索增强，也不是在线大模型安全分类器，而是在离线低算力条件下，将多个可解释模块串成安全约束链路。

## 模块顺序

1. 输入归一化：修正保守 ASR 错听、口语噪声和重复词。
2. 风险感知多意图抽取：识别 primary intent、secondary intents、negated risks。
3. 协议优先风险门控：计算 protocol confidence，优先处理高风险协议。
4. 候选证据检索：从本地 `build/rag.db` 检索候选 chunk。
5. 安全约束重排：结合相似度、质量、标签、风险、安全和冗余项。
6. 低证据分流：证据不足时澄清或保守回复。
7. 输出安全护栏：过滤危险操作、医学诊断和保证获救类文本。
8. 统一 trace：记录 query、intent、protocol、top chunks、guard 和 latency。

## 安全约束重排公式

\[
Score(c|q)=w_{vec}SimVec(q,c)+w_{sparse}SimSparse(q,c)+w_{quality}Quality(c)+w_{tag}TagMatch(q,c)+w_{risk}RiskMatch(q,c)-w_{unsafe}Unsafe(c)-w_{redundancy}Redundancy(c)
\]

如果底层检索返回 distance，则使用：

\[
SimVec(q,c)=\frac{1}{1+distance(q,c)}
\]

## 协议置信度

协议置信度由关键词、风险词、身体部位、场景、routed tags、协议优先级和否定冲突共同决定。其作用不是替代医学判断，而是为 route accuracy 和 trace 分析提供可解释信号。

## DE 的位置

DE 只优化 `scoring/policy_de.json` 中的权重。优化使用 dev 数据，不使用 test 数据。部署和评测时不在线运行 DE。

## 不做的事

- 不做医学诊断。
- 不承诺救援到达。
- 不输出药物剂量或侵入性医疗操作。
- 不把 MoniBox 包装成完整救援系统。
