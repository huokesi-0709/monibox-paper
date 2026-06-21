# Method

## 4.1 Problem Definition

给定用户输入 \(q\)、本地知识库 chunk 集合 \(C\)、协议集合 \(P\) 和安全约束集合 \(S\)，目标是在离线环境下生成回复 \(y\)。回复应满足：优先处理最高风险意图；引用或依赖足够证据；避免危险操作、医学诊断和救援保证；在证据不足时进行澄清或保守分流。

## 4.2 HSC-RAG Overall Framework

HSC-RAG 由六个阶段组成：输入归一化、风险感知多意图抽取、协议优先风险门控、候选证据检索、安全约束重排、输出安全护栏。每轮交互生成统一 trace，用于 route accuracy、protocol confidence、evidence score、guard reason 和 latency 分析。

## 4.3 Input Normalization

输入归一化处理空输入、全角/半角空格、中文标点、ASR 精确纠错、口语噪声和重复词压缩。所有替换都记录为 correction，避免不可解释改写。示例包括“留血→流血”“穿不上气→喘不上气”“旧我→救我”。

## 4.4 Risk-Aware Multi-Intent Extraction

系统将长输入切分为 clauses，并识别 respiratory distress、severe bleeding、trapped/crush、head/consciousness、hypothermia、dehydration、panic、low battery 等意图。primary intent 按风险优先级选择；否定窗口内的风险词进入 negated risks，不作为主风险。

## 4.5 Protocol-Prioritized Risk Gate

协议门控计算每个候选协议的置信度：

\[
Conf(p|q)=0.35K+0.20R+0.15B+0.15S+0.10T+0.05Pr-0.30N
\]

其中 \(K\) 为关键词命中，\(R\) 为风险词命中，\(B\) 为身体部位匹配，\(S\) 为场景匹配，\(T\) 为 routed tag 匹配，\(Pr\) 为协议优先级归一化，\(N\) 为否定冲突。该分数用于 trace 和路由分析。

## 4.6 Safety-Constrained Reranking

候选 chunk 的重排分数为：

\[
Score(c|q)=w_{vec}SimVec(q,c)+w_{sparse}SimSparse(q,c)+w_{quality}Quality(c)+w_{tag}TagMatch(q,c)+w_{risk}RiskMatch(q,c)-w_{unsafe}Unsafe(c)-w_{redundancy}Redundancy(c)
\]

若底层检索返回 distance，系统使用 \(SimVec=1/(1+distance)\)，避免把距离误当正向相似度。

## 4.7 Evidence Sufficiency

证据充分度用于判断是否直接回复或进入低证据分流。当前实现可由 top chunk 分数、协议置信度、route 一致性和 low-evidence threshold 组合得到。形式上可写为：

\[
Evidence(q)=\alpha TopScore+\beta ProtocolConf+\gamma RouteAgreement
\]

当 \(Evidence(q)<\tau\) 时，系统应澄清、请求更多信息或给出保守安全提示。

## 4.8 Output Safety Guard

输出护栏检查危险医疗操作、药物剂量、注射输液、准确诊断、保证获救和救援到达承诺。护栏不负责替代完整医疗判断，而是在最终文本层降低明显 unsafe response。

## 4.9 Differential Evolution Objective

DE 在 dev 数据上离线优化 HSC-RAG 权重，目标函数为：

\[
Fitness=0.20RA_c+0.20RA_r+0.15EH@5+0.20SC+0.10RC+0.10CA+0.05AC-0.25HRM-0.20UR-0.15UC-0.05LP
\]

其中 clean/robust route accuracy、evidence hit、安全合规、鲁棒一致性、澄清适当性和动作正确性为正项，高风险漏检、unsafe response、unsupported claim 和 latency penalty 为负项。DE 只使用 dev 集，不使用 test 集。
