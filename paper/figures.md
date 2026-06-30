# 论文图清单

本文图件应服务于 RAIR-RAG 主线。若仓库中尚无对应图片文件，本清单只保留图的设计说明，不编造图片路径。

## Figure 1: RAIR-RAG 任务与数据流

建议内容：用户输入 -> 输入规范化 -> 风险触发识别 -> 否定窗口处理 -> 多意图聚合 -> 约束识别 -> 路由决策 -> 预测 JSONL 与 summary。

对应章节：Method 与 Experimental Setup。

数据来源：`benchmarks/rair_rag/data/gold/rair_gold_all.jsonl`、dev/test split 和 `build/rair_eval/`。

## Figure 2: RAIR-RAG-Bench 构建流程

建议内容：candidates -> adjudication sheet -> gold JSONL -> dev/test split -> negation/multi-intent subsets -> evaluation outputs。

需要标注：当前 benchmark 是 guideline-informed, human-reviewed synthetic benchmark；权威证据链尚未完整逐例填充。

## Figure 3: 否定与多意图压力测试示意

建议内容：展示否定样本如何把风险词放入 `negated_risks`，以及多意图样本如何同时保留 primary route 与 secondary intents。

对应指标：PFTR、NegRiskF1、SecondaryIntentF1。

## Figure 4: 主实验方法对比

建议内容：以柱状图或雷达图展示 `keyword-baseline`、`no-negation`、`single-intent`、`risk-router-manual`、`risk-router-de` 在 RouteAcc、HRR、PFTR、NegRiskF1、SecondaryIntentF1 上的差异。

数据来源：`build/rair_eval/rair_test_*_summary.json`。

## Figure 5: DE 校准结果

建议内容：展示 DE 搜索流程和当前负结果：`feasible_trial_found=false`，最终没有优于手工策略的可行策略。图中应避免暗示 DE 带来性能提升。

数据来源：`build/rair_eval/de_summary.json` 与 `build/rair_eval/de_trials.jsonl`。

## 历史图件边界

旧 HSC-DisasterBench-v2 或 `paper_final_v2` 图件只能放在历史背景或附录中，不能与 RAIR-RAG 主实验图混排。