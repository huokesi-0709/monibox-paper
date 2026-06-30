# Method

## 4.1 Problem Definition

给定用户输入 \(q\)，RAIR-RAG 的目标不是直接生成开放式答案，而是先预测一组可审计的路由变量：主风险路由、次级意图、否定风险、安全约束和边界标签。系统随后根据这些变量决定是否进入高风险回复、低风险回复、澄清或域外处理路径。

本文评估的核心函数可写为：

\[
f(q) \rightarrow (r, I_s, N, C)
\]

其中 \(r\) 是主路由，\(I_s\) 是次级意图集合，\(N\) 是否定风险集合，\(C\) 是约束集合。评测关注这些结构化输出是否与 gold annotation 一致。

## 4.2 RAIR-RAG Pipeline

RAIR-RAG 包含五个阶段：输入规范化、风险触发识别、否定窗口处理、多意图聚合、约束与路由决策。每个阶段都输出可检查字段，便于在预测 JSONL 中追踪错误来源。

输入规范化只做保守处理，例如统一标点、空白和常见噪声，不把否定表达改写成肯定风险，也不推断用户没有说出的医学事实。

风险触发识别使用风险 taxonomy 中的标签、触发词和边界条件识别候选风险。该步骤是工程启发式分类，不是医学诊断，也不是真实救援优先级判定。

## 4.3 Negation Handling

否定处理用于识别“没有流血”“不是被困”“没有喘不上气”等表达。若风险触发词出现在否定窗口内，系统应把它记录为 `negated_risks`，而不是作为主风险路由依据。

该设计直接对应 NegRiskF1 与 PFTR。`no-negation` 消融关闭这一能力，用来衡量否定理解对误触发率的影响。

## 4.4 Multi-Intent Handling

多意图处理用于从同一输入中保留主风险与次级意图。例如“我被困了，腿也在流血，手机快没电”应同时体现被困、出血和低电量信息。RAIR-RAG 使用风险优先级选择主路由，同时保留其余有效意图用于 SecondaryIntentF1 评估。

`single-intent` 消融只保留单一意图，用来衡量多意图聚合对复杂输入的贡献。

## 4.5 Constraints and Boundary Labels

约束字段记录系统在回复或路由时必须遵守的边界，例如不能提供药物剂量、不能承诺救援到达、不能给出确定医学诊断，以及域外输入应进入边界处理。ConstraintF1 衡量这些约束是否被正确识别。

## 4.6 Benchmark Construction

RAIR-RAG-Bench 的当前主文件是 `benchmarks/rair_rag/data/gold/rair_gold_all.jsonl`。数据由候选样本、仲裁表和 taxonomy 生成；dev/test 与否定、多意图子集由脚本重新切分。当前数据集应表述为指南启发、人工复核的合成基准。

权威证据链尚未完整填充。`guideline_refs` 当前主要是从风险 taxonomy 映射到的标签级依据；`reference_reply` 为空，不能作为逐例参考回复使用。

## 4.7 Policies and Baselines

本文比较五类方法：

| 方法 | 说明 |
| --- | --- |
| `keyword-baseline` | 基于关键词触发的弱 baseline。 |
| `no-negation` | 关闭否定处理的消融。 |
| `single-intent` | 关闭多意图保留的消融。 |
| `risk-router-manual` | 手工设定的完整风险路由策略。 |
| `risk-router-de` | 在 dev 集上使用 Differential Evolution 搜索得到的策略。 |

DE 只用于策略校准，不在 test 集上调参。当前 `risk-router-de` 与 `risk-router-manual` 指标相同，且 `de_summary.json` 显示没有找到更优可行 trial。

## 4.8 Evaluation Metrics

主指标包括 RouteAcc、HRR、PFTR、NegRiskF1、SecondaryIntentF1 和 ConstraintF1。主表来自 `build/rair_eval/rair_test_*_summary.json`；否定子集来自 `rair_test_negation_*`；多意图子集来自 `rair_test_multi_intent_*`。

历史 HSC-DisasterBench-v2 的 clean/robust 结果不参与这些表格计算，只能作为历史实验背景。