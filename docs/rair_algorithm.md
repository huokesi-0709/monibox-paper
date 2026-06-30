# RAIR: Pre-Retrieval Risk-Aware Input Routing

## 1. Problem Statement

Safety-critical RAG failures may originate before retrieval when user queries do not carry structured risk semantics. RAIR addresses this issue by constructing a structured risk-aware retrieval context before protocol matching, retrieval, and generation.

在离线灾害应急场景中，输入往往同时包含风险陈述、否定、操作约束和多意图混杂信号。RAIR 的目标不是优化底层检索器本身，而是在检索前先把输入整理成可路由、可解释、可抑制误触发的结构化 RiskContext。

## 2. Algorithm Name

RAIR: Pre-Retrieval Risk-Aware Input Routing

## 3. Inputs

| Symbol | Meaning |
|---|---|
| `x` | raw user input |
| `x'` | canonical input |
| `L` | risk lexicon and risk taxonomy |
| `Q` | negation expression set |
| `B` | boundary and discourse marker set |
| `P(r)` | prototype description set for risk `r` |
| `theta` | routing parameters |

## 4. Outputs

| Output | Meaning |
|---|---|
| `risk_candidates` | extracted candidate risks |
| `positive_risks` | risks not suppressed by negation |
| `negated_risks` | risks suppressed by negation |
| `primary_intent` | highest-priority route intent |
| `secondary_intents` | non-primary but retained risk intents |
| `operational_constraints` | battery, network, device, or resource constraints |
| `suppressed_protocols` | protocols blocked by negated risks |
| `predicted_route` | predicted route before retrieval |
| `risk_context` | structured context consumed by downstream RAG |

## 5. Step 1: Risk Candidate Extraction and Semantic Confidence

候选风险定义为：

```math
m_i = (r_i, s_i, t_i, e_i, c_i)
```

其中 `r_i` 为风险标签，`s_i` 为起止 span，`t_i` 为触发词，`e_i` 为证据类型，`c_i` 为候选置信度。

RAIR 采用多因子语义置信度建模：

```math
c_i = \sigma(\alpha_0 + \alpha_1 f_{lex}(m_i) + \alpha_2 f_{sem}(m_i,x') + \alpha_3 f_{ctx}(m_i,x') + \alpha_4 f_{evi}(e_i))
```

其中：

```math
f_{sem}(m_i,x') = \max_{p \in P(r_i)} \cos(E(t_i), E(p))
```

说明：

`P(r_i)` 是风险 `r_i` 的原型描述集合，`E(.)` 是嵌入函数。原型嵌入可离线预计算，在线阶段仅计算触发词嵌入并做余弦相似度匹配。

> 旧的触发词长度公式仅保留为 archived keyword confidence baseline，不属于 RAIR 主算法。

## 6. Step 2: Negation Scope Probability Modeling

否定作用域概率建模为：

```math
P_{neg}(m_i \mid x') = \sigma(\eta_0 + \sum_{q_j \in Q \cap W_i}\phi(q_j)\exp(-\gamma d(q_j,m_i)) - \sum_{b_k \in B \cap \Pi(q_j,m_i)}\psi(b_k))
```

修正置信度为：

```math
\hat{c_i} = c_i(1 - P_{neg}(m_i \mid x'))
```

若：

```math
P_{neg}(m_i \mid x') > \tau_{neg}
```

则候选 `m_i` 进入 `negated_risks`，并映射到 `suppressed_protocols`。

## 7. Step 3: Safety-Constrained Priority Routing

优先级得分定义为：

```math
s_i = w(r_i)\hat{c_i} + \beta I(r_i \in H) - \delta I(r_i \in O)
```

主意图选择为：

```math
primary\_intent = \arg\max_{i:r_i \notin O,\hat{c_i}>\tau_c,P_{neg}(m_i \mid x')\le\tau_{neg}} s_i
```

其中：

- `H` 表示高风险集合；
- `O` 表示操作约束集合；
- `beta` 表示高风险增强项；
- `delta` 表示操作约束抑制项。

这一步的核心不是“分类得分越大越好”，而是“在安全约束下挑出最应该优先路由的风险意图”。

## 8. Step 4: Risk Context Construction Before Retrieval

RAIR 在检索前构建结构化风险上下文：

```math
C = \{M,R^+,R^-,I_p,I_s,O_c,P_s,\rho,S\}
```

其中：

- `M`：`risk_candidates`
- `R+`：`positive_risks`
- `R-`：`negated_risks`
- `Ip`：`primary_intent`
- `Is`：`secondary_intents`
- `Oc`：`operational_constraints`
- `Ps`：`suppressed_protocols`
- `rho`：`predicted_route`
- `S`：`risk_score`

RAG retrieval is a downstream consumer of `RAIR` risk_context, not the optimized component.

## 9. Algorithm 1 Pseudocode

```text
Algorithm 1 RAIR: Pre-Retrieval Risk-Aware Input Routing
Input: raw text x, canonical text x', lexicon L, negation set Q, boundary set B, prototype set P(.), parameters theta
Output: risk_context C

1:  candidates <- ExtractRiskCandidates(x', L, P(.), theta)
2:  for each candidate m_i in candidates do
3:      c_i <- MultiFactorConfidence(m_i, x', P(.), theta)
4:      P_neg(m_i) <- EstimateNegationScope(m_i, x', Q, B, theta)
5:      if P_neg(m_i) > tau_neg then
6:          mark m_i as negated
7:          add r_i to negated_risks
8:          add mapped protocol of r_i to suppressed_protocols
9:      else
10:         add r_i to positive_risks
11:     end if
12: end for
13: route_scores <- SafetyConstrainedPriorityScore(candidates, theta)
14: primary_intent <- argmax route_scores under safety constraints
15: secondary_intents <- retain non-primary positive intents
16: operational_constraints <- extract operational constraint intents
17: predicted_route <- map(primary_intent)
18: protocol_id <- map(predicted_route)
19: risk_context <- assemble(Candidates, positive_risks, negated_risks, primary_intent, secondary_intents, operational_constraints, suppressed_protocols, predicted_route, protocol_id)
20: return risk_context
```

## 10. Complexity Analysis

```math
O(n|L| + kpd + kh + k\log k)
```

其中：

- `n`：输入长度；
- `|L|`：风险词表规模；
- `k`：候选数量；
- `p`：每个风险类别的原型描述数量；
- `d`：嵌入维度；
- `h`：否定窗口大小。

Risk prototype embeddings are pre-computed offline. In typical disaster emergency inputs, user utterances are short and the number of extracted candidates is small, making RAIR suitable for offline edge deployment.

## 11. Theoretical Properties

**Proposition 1: Negation suppression monotonicity.**  
If the negation evidence for a candidate increases while all other terms remain fixed, then its adjusted confidence does not increase.

**Proposition 2: Operational constraints cannot become the primary route.**  
Operational constraint intents may be retained in `operational_constraints`, but they are excluded from primary route selection unless all non-operational candidates are absent.

**Proposition 3: High-risk priority condition.**  
If two candidates are both non-negated and non-operational, the one in the higher-risk set `H` is preferred whenever its weighted score dominates.

## 12. Code Mapping

| Algorithm Component | Code Location |
|---|---|
| Risk Candidate Extraction | `runtime/risk_router.py`, `runtime/risk_candidate.py` |
| Semantic Confidence | `runtime/risk_confidence.py` |
| Negation Scope Modeling | `runtime/negation_resolver.py` |
| Multi-Intent Priority Routing | `runtime/multi_intent_router.py` |
| Risk Context Construction | `runtime/risk_router.py`, `benchmarks/rair_rag/run_routing_eval.py` |
| Evaluation Metrics | `benchmarks/rair_rag/routing_metrics.py` |

## Archived Baseline Note

历史上的 keyword confidence 公式仅作为归档基线保留，用于兼容旧实验或对照结果；RAIR 主算法不再采用基于触发词长度的单因子打分。
