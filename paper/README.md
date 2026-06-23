# Paper 工作目录

论文题目：**面向灾害受困场景的鲁棒启发式安全约束离线 RAG 应急回复生成方法**

本目录用于存放中文论文工作稿、图表清单、表格清单和复现实验说明。当前内容是仓库内论文工程写作材料，不是最终投稿版，也不代表已经完成最终 SCI 实验。

实验结果应来自 `build/eval/` 及阶段 11 导出的表格，包括 `main_results.csv`、`robustness_results.csv`、`ablation_results.csv`、`de_effect_results.csv`、`latency_memory_results.csv` 和 `trace_audit_results.csv`。不要在论文稿中手写或编造实验数值。

当前 `benchmarks/data/clean_dev.jsonl` 与 `benchmarks/data/robustness_dev.jsonl` 仍属于 dev/smoke 数据，用于验证复现实验链路、指标计算和方法对比流程，不等同最终 SCI test set。

简写说明：`clean_dev / robustness_dev` 均指当前开发与 smoke 评估数据，不代表最终测试集。

推荐阅读顺序：

1. `reproducibility.md`
2. `tables.md`
3. `figures.md`
4. `manuscript_zh.md`
