# 面向灾害受困场景的离线安全 RAG 应急回复生成方法：启发式算法引入报告

## 1. 研究定位

本报告不将 MoniBox 写成一个完整系统介绍，而是将其定位为原型验证平台。论文主线应聚焦一种面向灾害受困场景的离线安全 RAG 应急回复生成方法，MoniBox 只承担方法验证、消融实验和端侧可运行性测试的工程载体。

建议论文对象表述为：

> A Heuristic Safety-Constrained Offline RAG Method for Emergency Response Generation in Disaster-Trapped Scenarios

中文可写为：

> 面向灾害受困场景的启发式安全约束离线 RAG 应急回复生成方法

这个定位的关键好处是，论文不需要把 MoniBox 解释成一个庞大的软硬件系统，也不需要证明系统具备完整救援能力。论文只需要证明：在断网、低算力、高风险的受困场景下，相比普通 RAG 或规则回复，所提出的方法能更安全、更稳定、更快地生成应急回复。

## 2. 快速发表 SCI 三区的可行性判断

从快速发表角度看，启发式算法比深度学习训练更适合当前阶段。原因不是启发式算法“更高级”，而是它更贴合 MoniBox 的现有工程基础和三区应用型论文的审稿期待。

| 维度 | 启发式算法路线 | 深度学习路线 |
| --- | --- | --- |
| 数据需求 | 可用 300 到 800 条标注灾害问句完成实验 | 通常需要更大规模语料或微调数据 |
| 工程成本 | 主要改造检索、重排、风险判断和回退策略 | 需要训练、部署、量化、对比和泛化验证 |
| 可解释性 | 规则权重、证据分数、风险阈值容易解释 | 模型行为难解释，安全场景审稿风险更高 |
| 离线端侧适配 | 权重查表和规则推理开销低 | 模型推理资源压力更大 |
| 论文新意边界 | 应用场景明确，安全约束和离线 RAG 组合有现实价值 | 如果只是微调小模型，创新性可能不足 |

因此，建议将论文创新点控制在“安全约束下的离线 RAG 决策与重排方法”，而不是宣称提出通用新型智能系统。这样的边界更稳，也更容易被应急信息学、边缘智能、应用人工智能、知识工程和安全科学方向的三区期刊接受。

## 3. 当前工程可支撑的方法基础

MoniBox 当前主链路已经具备论文方法雏形：

```text
用户输入
  -> 文本预处理与主题路由
  -> 协议优先匹配
  -> RAG 检索与重排
  -> 低证据分流
  -> LLM 或模板生成
  -> 安全护栏
  -> 语音友好输出
```

与论文方法之间的对应关系如下：

| 工程模块 | 可抽象成论文组件 | 当前价值 |
| --- | --- | --- |
| `runtime/protocol_matcher.py` | 协议优先风险门控 | 高风险场景先走确定性协议 |
| `runtime/topic_router.py` | 轻量主题路由器 | 在低算力条件下为检索提供候选约束 |
| `runtime/rag_engine.py` | 离线知识检索器 | 支持 SQLite 向量检索和文本回退检索 |
| `runtime/scoring.py` | 检索重排评分器 | 已有质量分和启用状态调权基础 |
| `runtime/evidence_router.py` | 低证据安全分流器 | 避免证据不足时强行生成 |
| `runtime/guard.py` | 输出安全约束器 | 对高风险处置、用药剂量和强保证进行拦截或改写 |
| `runtime/response_pipeline.py` | 应急播报成形器 | 控制长度、重复、第二人称和 TTS 适配 |

这些模块不必在论文中逐个介绍为软件架构，而应被抽象成一个方法框架：协议优先、证据驱动、风险约束、低证据回退、端侧轻量推理。

## 4. 可引入的启发式算法方向

### 4.1 风险优先协议门控

当前协议匹配依赖优先级排序和触发条件，适合扩展为风险优先协议门控算法。其目标是在 RAG 生成前判断用户输入是否属于高风险应急类别，例如被压、出血、呼吸困难、低温、洪水围困、恐慌等。

可引入的启发式规则包括：

| 启发式特征 | 示例 | 用途 |
| --- | --- | --- |
| 高风险关键词 | 出血、压住、喘不上气、冷得发抖 | 快速触发协议优先路径 |
| 风险动作词 | 动不了、流血、窒息、昏过去 | 提升风险分 |
| 否定词约束 | 没出血、不疼、不是骨折 | 降低误触发 |
| 身体部位词 | 腿、胸口、头、脖子 | 支持局部风险判断 |
| 场景词 | 地震、洪水、塌方、被困 | 辅助选择协议类别 |

可以定义协议置信度：

```text
P(q, p) = a1 * KeywordHit(q, p)
        + a2 * RiskTerm(q)
        + a3 * BodyPartMatch(q, p)
        + a4 * SceneMatch(q, p)
        - a5 * NegationConflict(q, p)
```

其中 `q` 是用户输入，`p` 是候选协议。当 `P(q, p)` 高于阈值时，系统直接进入协议回复，不再交给生成模型自由发挥。

论文贡献点可以写成：提出一种协议优先的启发式风险门控机制，用于在高风险灾害对话中减少生成模型的不确定输出。

### 4.2 轻量混合检索与重排

当前 `runtime/rag_engine.py` 已支持向量检索和文本回退检索，并在检索结果上加入质量分、启用状态和特定查询调权。这里最适合发展成论文的核心启发式算法。

推荐提出安全约束启发式重排评分：

```text
Score(c | q) =
    lambda1 * SimVec(q, c)
  + lambda2 * SimSparse(q, c)
  + lambda3 * Quality(c)
  + lambda4 * TagMatch(q, c)
  + lambda5 * RiskMatch(q, c)
  - lambda6 * Unsafe(c)
  - lambda7 * Redundancy(c)
```

其中：

| 符号 | 含义 |
| --- | --- |
| `SimVec(q, c)` | 用户输入与候选 chunk 的向量相似度 |
| `SimSparse(q, c)` | BM25、TF-IDF 或字符 n-gram 稀疏匹配分 |
| `Quality(c)` | 知识片段人工质量分或审核分 |
| `TagMatch(q, c)` | 主题路由标签与候选标签的一致性 |
| `RiskMatch(q, c)` | 候选内容是否匹配当前风险场景 |
| `Unsafe(c)` | 是否包含不适合端侧应急回复的高风险处置 |
| `Redundancy(c)` | 与近期回复或已选证据的重复度 |

这种评分不要求训练深度模型，只需要少量标注数据调参。在线阶段也只是加权计算，适合端侧设备。

### 4.3 低证据分流启发式

灾害受困场景中，RAG 最大风险之一不是“不回答”，而是“证据不足却回答得很确定”。因此低证据判断应成为论文方法的安全核心。

建议定义证据充分度：

```text
E(q) =
    b1 * SimTop1
  + b2 * GapTop12
  + b3 * TagConfidence
  + b4 * QualityTop1
  + b5 * ProtocolConfidence
  - b6 * RiskUncertainty
```

其中 `GapTop12` 表示第一名和第二名候选的差距。若第一名分数不高且与第二名差距很小，说明检索不稳定，应降低证据充分度。

决策规则：

```text
if ProtocolConfidence >= theta_protocol:
    return protocol_response
elif E(q) < theta_evidence and Risk(q) >= theta_risk:
    return conservative_low_evidence_response
elif E(q) < theta_evidence:
    return clarification_question
else:
    return rag_grounded_response
```

这一路线与当前 `LowEvidenceRouter` 很匹配。现有代码已经有救援、寒冷、口渴、疲劳、恐慌、疼痛、视野异常等 bucket，可以进一步从硬关键词扩展为带分数的启发式分流。

### 4.4 输出安全过滤与应急播报成形

当前 `SafetyGuard` 能拦截或改写高风险内容，例如侵入性处置、止血带、注射、输液、药物剂量和获救时间保证。论文中可以把它抽象成安全约束函数。

建议定义安全代价：

```text
U(y) =
    r1 * InvasiveAction(y)
  + r2 * MedicationDose(y)
  + r3 * DiagnosisAssertion(y)
  + r4 * RescueGuarantee(y)
  + r5 * OverlongInstruction(y)
```

当 `U(y)` 超过阈值时，回复进入改写或阻断路径：

```text
if U(y) >= theta_block:
    y = safe_fallback
elif U(y) >= theta_rewrite:
    y = safety_rewrite(y)
else:
    y = y
```

这部分很适合做实验指标，因为可以统计不安全回复率、过度阻断率、可用回复率和人工安全评分。

### 4.5 面向 ASR 误差的模糊匹配

如果论文需要增强语音场景可信度，可加入一组低成本模糊匹配启发式。灾害受困场景中，噪声、哭喊、虚弱发声会导致 ASR 错误，例如“膝盖”识别为“漆盖”，“流血”识别为“留血”。

可选算法：

| 算法 | 适用点 | 推荐程度 |
| --- | --- | --- |
| 编辑距离 | 身体部位、症状词纠错 | 高 |
| 拼音近似匹配 | 中文 ASR 音近错误修正 | 高 |
| 字符 n-gram 相似度 | 短句模糊召回 | 高 |
| Aho-Corasick | 多关键词快速匹配 | 中 |
| LCS | 口语短句与模板相似判断 | 中 |

建议不要把这些算法写成论文主贡献，而是作为鲁棒性增强模块。主贡献仍应放在安全约束 RAG 决策上。

## 5. 推荐论文核心算法：HSC-RAG

建议将核心方法命名为 HSC-RAG，即 Heuristic Safety-Constrained Retrieval-Augmented Generation。

HSC-RAG 由四个阶段组成：

1. 风险感知输入解析。对用户输入提取场景词、症状词、身体部位、否定词和求救意图，得到风险分和协议置信度。
2. 协议优先门控。若协议置信度高于阈值，则直接输出协议回复，避免生成模型参与高风险决策。
3. 安全约束检索重排。对候选知识片段进行向量相似度、稀疏相似度、质量分、标签一致性和风险一致性加权排序，并惩罚不安全内容。
4. 证据充分度决策。若证据不足，则进入低证据安全回复或澄清问题；若证据充分，则生成 grounded response，并通过安全护栏和播报成形输出。

推荐伪代码如下：

```text
Algorithm: HSC-RAG
Input: user query q, local knowledge base K, protocol set P
Output: emergency response y

1. features = ExtractHeuristicFeatures(q)
2. risk_score = ComputeRiskScore(features)
3. protocol, protocol_conf = MatchProtocol(q, P, features)

4. if protocol_conf >= theta_protocol:
5.     y = RenderProtocol(protocol, q)
6.     return SafetyShape(y)

7. candidates = Retrieve(K, q)
8. ranked = SafetyConstrainedRerank(q, candidates, features)
9. evidence = ComputeEvidenceScore(q, ranked, protocol_conf, risk_score)

10. if evidence < theta_evidence and risk_score >= theta_risk:
11.     y = ConservativeFallback(q, features)
12. elif evidence < theta_evidence:
13.     y = ClarificationQuestion(q, features)
14. else:
15.     y = GenerateGroundedResponse(q, ranked[1:k])

16. y = SafetyGuard(y)
17. y = SpeechFriendlyShape(y)
18. return y
```

论文中可以强调：HSC-RAG 不是替代 LLM，而是在灾害场景中为 LLM 加上可解释、可审计、可离线运行的安全决策层。

## 6. 实验设计建议

### 6.1 数据集构建

为了快速发表，不建议等待真实灾害数据。可以构建一个小规模中文灾害受困问句评测集，命名为 Disaster-Trapped Emergency Query Set。

建议规模：

| 数据类型 | 数量建议 | 示例 |
| --- | --- | --- |
| 明确高风险求助 | 100 到 150 | 我被压住了、腿在流血、喘不上气 |
| 低证据模糊表达 | 80 到 120 | 我不太行、好难受、这里很黑 |
| 生理需求 | 80 到 120 | 我很渴、好冷、没力气 |
| 心理安抚 | 80 到 120 | 我好怕、心跳很快、要崩溃了 |
| 灾害场景问题 | 80 到 120 | 洪水里怎么求救、粉尘很大怎么办 |
| ASR 扰动样本 | 80 到 120 | 错字、同音字、短句噪声 |

总量控制在 500 到 800 条即可。对 SCI 三区应用型论文来说，关键不是数据量大，而是标注清楚、实验完整、消融设计合理。

建议标注字段：

| 字段 | 含义 |
| --- | --- |
| `query` | 用户输入 |
| `risk_level` | low、medium、high |
| `expected_route` | protocol、rag、low-evidence、clarification |
| `expected_tags` | 预期主题或症状标签 |
| `gold_chunk_ids` | 可支持回答的知识片段 |
| `unsafe_actions` | 禁止出现的处置建议 |
| `reference_reply` | 人工参考回复 |

### 6.2 对比方法

推荐设置四组 baseline：

| 方法 | 说明 | 目的 |
| --- | --- | --- |
| Rule-only | 只使用协议和模板 | 验证纯规则覆盖不足 |
| Vanilla RAG | 只做普通检索增强生成 | 验证普通 RAG 的安全风险 |
| RAG + Guard | 普通 RAG 加输出安全护栏 | 验证仅后置拦截不够 |
| HSC-RAG | 本报告建议方法 | 验证协议、重排、证据分流和安全约束的联合收益 |

如果时间允许，可增加一个 `HSC-RAG without low-evidence routing` 消融组，用来证明低证据分流的贡献。

### 6.3 评价指标

建议指标不要只用 BLEU、ROUGE 这类文本相似度。应急回复更关注安全、正确、可执行和低时延。

| 指标 | 计算方式 | 论文价值 |
| --- | --- | --- |
| Route Accuracy | 预测路径与标注路径一致率 | 验证协议和低证据分流 |
| Top-k Evidence Hit | 检索结果是否包含 gold chunk | 验证检索重排 |
| Unsafe Response Rate | 回复中出现高风险建议的比例 | 核心安全指标 |
| Unsupported Claim Rate | 无证据支撑的断言比例 | 验证低证据控制 |
| Action Correctness | 人工评估动作是否合理 | 贴合灾害场景 |
| Clarification Appropriateness | 证据不足时是否提出合适追问 | 验证保守策略 |
| Latency | 端侧单轮响应时间 | 验证离线可用性 |
| Memory Footprint | 峰值内存占用 | 验证低算力部署 |

建议主结果表围绕安全和路径正确率展开，而不是只展示生成质量。

### 6.4 消融实验

推荐消融设置：

| 消融项 | 预期证明 |
| --- | --- |
| 去掉协议优先门控 | 高风险场景下不安全回复率上升 |
| 去掉安全约束重排 | 检索证据命中率下降，错误 chunk 增多 |
| 去掉低证据分流 | 模糊输入下幻觉或无证据断言增加 |
| 去掉安全护栏 | 用药、侵入性处置、保证获救等风险输出增加 |
| 去掉语音成形 | 回复过长，端侧播报可用性下降 |

这组实验非常适合三区论文，因为审稿人能清楚看到每个启发式模块的作用。

## 7. 与当前工程的最小改造路径

为了尽快形成论文实验结果，不建议大改系统。优先做以下五件事：

1. 新增可配置启发式评分文件。建议放在 `scoring/policy.json`，包含检索、风险、证据和安全权重。
2. 为每次回复输出 trace。记录 `route`、`risk_score`、`protocol_confidence`、`evidence_score`、`top_chunks`、`guard_reasons`。
3. 将 `LowEvidenceRouter` 从硬关键词扩展为分数制 bucket 选择。保留现有规则作为最快命中路径。
4. 增加 benchmark 脚本。输入标注数据集，输出指标表、错误案例和消融结果。
5. 固定论文实验 profile。关闭不必要的远端依赖，优先测试纯离线文本链路，再补充语音链路时延。

建议最小新增文件：

```text
benchmarks/disaster-queries.jsonl
benchmarks/run-hsc-rag-eval.py
benchmarks/ablation-configs.json
scoring/policy.json
docs/offline-safe-rag-heuristic-report.md
```

如果只为论文快速产出，第一阶段甚至不需要加入新的深度模型。只要将现有规则从“散落在代码里的经验判断”提升为“有公式、有阈值、有消融实验的启发式安全决策算法”，就足以形成方法论文。

## 8. 论文创新点组织方式

建议论文贡献写成三点：

1. 提出一种面向灾害受困场景的启发式安全约束离线 RAG 框架，在生成前引入协议优先门控，在生成后引入安全约束与播报成形。
2. 设计一种轻量级安全约束检索重排和证据充分度判断方法，将向量相似度、稀疏匹配、质量分、标签一致性、风险匹配和安全惩罚统一到可解释评分中。
3. 基于 MoniBox 原型平台构建中文灾害受困问句评测集，并从路径正确率、证据命中率、不安全回复率、无证据断言率、时延和内存占用等维度验证方法有效性。

这三个贡献点足够支撑一篇应用型 SCI 三区论文。它们不夸大模型能力，也不把工程项目包装成完整救援系统，而是把工程中的安全决策逻辑沉淀为可复现方法。

## 9. 推荐论文结构

建议论文结构如下：

```text
1. Introduction
   灾害受困场景、断网约束、普通 RAG 风险、本文贡献

2. Related Work
   Emergency response dialogue
   Retrieval-augmented generation
   Safety-constrained generation
   Edge and offline AI

3. Method
   Problem formulation
   HSC-RAG framework
   Protocol-first risk gate
   Safety-constrained reranking
   Evidence sufficiency decision
   Safety guard and response shaping

4. Prototype and Experimental Setup
   MoniBox as prototype validation platform
   Local knowledge base
   Dataset construction
   Baselines and metrics

5. Results
   Main comparison
   Ablation study
   Latency and memory analysis
   Case study

6. Discussion
   Interpretability
   Offline deployment
   Limitations

7. Conclusion
```

注意，第四章可以介绍 MoniBox，但标题应避免写成 “System Architecture”。更推荐 “Prototype and Experimental Setup”，这样能保持论文重心在方法上。

## 10. 投稿风险与规避

| 风险 | 可能被审稿人质疑 | 规避方式 |
| --- | --- | --- |
| 创新性不足 | 只是规则和 RAG 拼接 | 用统一评分、证据决策和消融实验形成方法闭环 |
| 数据规模小 | 样本不够真实 | 强调高风险场景标注质量，加入 ASR 扰动和人工安全评估 |
| 安全声明过大 | 无法证明真实救援有效 | 只声称辅助应急回复生成，不声称替代专业救援 |
| 启发式过拟合 | 规则只适合当前知识库 | 增加跨灾害类别测试和错误案例分析 |
| 缺少深度学习 | 方法不够先进 | 强调离线、低算力、可解释、安全约束，比 SOTA 生成质量更重要 |

论文中不要写“系统能保证救援成功”“能给出医学处置方案”“适用于所有灾害现场”。建议写“生成保守、可解释、证据约束的应急回复”，边界更安全。

## 11. 结论

当前工程最适合走启发式安全约束 RAG 路线。MoniBox 的价值不在于作为一个完整系统被介绍，而在于它已经具备协议优先、RAG 检索、低证据分流、安全护栏和端侧播报这些可验证组件。只要将这些组件抽象为 HSC-RAG 方法，并补齐评分公式、trace、标注数据集、benchmark 和消融实验，就可以形成一篇目标明确、实验可控、快速发表潜力较高的 SCI 三区应用型论文。

推荐优先实施顺序：

1. 固化 HSC-RAG 评分公式和阈值配置。
2. 输出每轮决策 trace，保证实验可解释。
3. 构建 500 到 800 条中文灾害受困问句评测集。
4. 完成四组 baseline 和五组消融实验。
5. 将 MoniBox 写成 prototype validation platform，而不是完整系统主体。
