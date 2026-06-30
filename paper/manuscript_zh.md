# RAIR-RAG：面向灾害受困文本的风险感知意图路由与检索增强生成评测

## 摘要

灾害受困文本求助通常短促、嘈杂且包含高风险信息。用户可能在同一输入中同时表达被困、出血、呼吸困难、低电量和恐慌，也可能明确否认某些风险。普通 RAG 若只依赖关键词或语义相似度，容易漏掉最高风险意图，或在否定样本中误触发高风险协议。本文提出 RAIR-RAG，即 Risk-Aware Intent Routing for Retrieval-Augmented Generation，并构建 RAIR-RAG-Bench 对风险路由进行可复现评测。当前数据集是 guideline-informed, human-reviewed synthetic benchmark，主文件位于 `benchmarks/rair_rag/data/gold/rair_gold_all.jsonl`。本文比较关键词 baseline、否定消融、单意图消融、手工风险路由和 DE 搜索策略。主 test 结果显示，`risk-router-manual` 达到 RouteAcc 0.9729、HRR 0.9831、PFTR 0.0063、NegRiskF1 0.7410 和 SecondaryIntentF1 0.8333，clean/control 子集 RouteAcc 为 1.0000。DE 搜索得到可行策略，但 best policy 仍为 manual-baseline，应作为中性校准结果报告。本文不声称每条样本已有完整权威来源映射，`reference_reply` 当前也未填充；旧 `paper_final_v2` / HSC-DisasterBench-v2 结果仅作为历史背景，不进入 RAIR-RAG 主表。

## 关键词

RAIR-RAG；风险感知意图路由；检索增强生成；灾害受困文本；否定理解；多意图识别；合成基准

## 1 引言

灾害受困场景中的人机交互具有强烈的时间压力和风险不对称。用户输入往往不完整、重复、情绪化，并可能包含多种风险或约束。对于这类输入，系统首先需要判断“最应该如何处理风险”，而不是直接生成看似完整的回答。

RAG 为这类任务提供了知识访问基础，但普通 RAG 的语义相似度并不等同于安全路由。若系统忽略否定表达，可能把“没有流血”误判为出血风险；若系统只保留单一意图，可能漏掉“被困且低电量”等次级需求；若系统在证据不足时仍给出确定建议，则可能产生不合适的安全承诺。

本文将这些问题转化为可复现的风险路由评测，提出 RAIR-RAG 并构建 RAIR-RAG-Bench。论文主线使用 `benchmarks/rair_rag/` 的数据和 `build/rair_eval/` 的结果。旧 HSC-DisasterBench-v2 / `paper_final_v2` 仅可作为历史实验背景。

## 2 相关工作

本文关联三个方向：检索增强生成的可靠性评估、高风险场景中的安全约束、以及面向噪声文本的意图识别。与一般 RAG 评测不同，RAIR-RAG-Bench 不把核心问题设为开放式答案质量，而是聚焦路由、否定、多意图和约束识别。

## 3 方法

RAIR-RAG 将输入映射为结构化路由变量：主风险路由、次级意图、否定风险和安全约束。系统流程包括输入规范化、风险触发识别、否定窗口处理、多意图聚合、约束识别和路由决策。

否定处理用于避免“没有流血”“不是被困”等表达误触发协议。多意图处理用于在选择主路由的同时保留次级需求。约束识别用于记录不能提供药物剂量、不能承诺救援到达、不能给出确定诊断等安全边界。

## 4 数据集与实验设置

RAIR-RAG-Bench 的主数据位于 `benchmarks/rair_rag/`。`rair_gold_all.jsonl` 由候选样本和仲裁表生成，dev/test 与否定、多意图子集由脚本切分。当前数据集可以表述为指南启发、人工复核的合成基准。

必须说明的是，权威证据链尚未完整填充。`source_type` 已改为 `template_generated_human_reviewed`；`guideline_refs` 主要来自风险 taxonomy 的标签级映射；`reference_reply` 仍为空。因此论文不能写成“每条样本都有权威来源映射”。

主实验比较 `keyword-baseline`、`no-negation`、`single-intent`、`risk-router-manual` 和 `risk-router-de`。指标包括 RouteAcc、HRR、PFTR、NegRiskF1、SecondaryIntentF1 和 ConstraintF1。

## 5 实验结果

主 test 集结果如下：

| Method | RouteAcc | HRR | PFTR | NegRiskF1 | SecondaryIntentF1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| keyword-baseline | 0.8000 | 0.8315 | 0.0083 | 0.0000 | 0.0000 |
| no-negation | 0.8208 | 0.9410 | 0.1542 | 0.0000 | 0.6533 |
| single-intent | 0.8083 | 0.8596 | 0.0021 | 0.7410 | 0.0000 |
| risk-router-manual | 0.9729 | 0.9831 | 0.0063 | 0.7410 | 0.8333 |
| risk-router-de | 0.9729 | 0.9831 | 0.0063 | 0.7410 | 0.8333 |

否定子集显示，关闭否定处理会显著提高误触发风险；完整风险路由在该子集上保持较低 PFTR。多意图子集显示，完整策略能够保留次级意图，而 `single-intent` 消融无法评估这一能力。

DE 结果应报告为中性校准结果：当前 `de_summary.json` 显示 `feasible_trial_found=true`，但 best policy 仍为 manual-baseline；`risk-router-de` 与 `risk-router-manual` 指标相同。

## 6 讨论

RAIR-RAG-Bench 当前最有价值的方向是风险路由压力测试，尤其是否定和多意图。它能暴露一般关键词或单意图策略难以发现的问题，也能让安全边界从主观描述变成可度量指标。

当前限制同样明确。数据集仍是合成基准；逐例权威证据链尚未补齐；评测主要覆盖路由与结构化识别，不证明真实救援场景中的最终回复安全有效。

## 7 结论

本文将当前论文主线确定为 RAIR-RAG 与 RAIR-RAG-Bench。实验结果表明，风险感知路由、否定处理和多意图保留是值得继续推进的核心方向。后续必须补齐逐例权威证据链，扩展真实噪声覆盖，并保持 RAIR-RAG 主结果与旧 HSC 历史结果分离。
