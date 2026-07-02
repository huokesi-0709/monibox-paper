# Paper 工作目录

当前论文主线：**RAIR-RAG: Risk-Aware Input Routing for Offline RAG-Based Disaster Emergency Response**。

本目录用于存放当前 RAIR-RAG 论文草稿、图表清单、表格清单和复现实验说明。当前主线不是旧版 HSC-RAG-DE / HSC-DisasterBench-v2，而是 `benchmarks/rair_rag/` 下的 RAIR-RAG-Bench。

## 当前主线

论文应围绕以下问题展开：

- 否定冲突：用户明确否定某个风险时，系统是否能避免协议误触发。
- 多意图输入：同一输入包含多个风险或运行约束时，系统是否能按安全优先级选择主路由并保留次要风险。
- 风险感知输入路由：在 RAG 检索和协议门控前，构建更可靠的风险上下文。
- 路由参数校准：DE 仅作为 dev split 上的离线校准工具，不是主要性能来源。

## 当前数据与结果来源

主数据集与 split：

```text
benchmarks/rair_rag/data/gold/rair_gold_all.jsonl
benchmarks/rair_rag/data/dev/rair_dev.jsonl
benchmarks/rair_rag/data/dev/clean_dev / robustness_dev
benchmarks/rair_rag/data/test/rair_test.jsonl
benchmarks/rair_rag/data/test/rair_test_negation.jsonl
benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl
```

主实验产物：

```text
build/rair_eval/
```

当前论文表格和结果描述应优先引用 `build/rair_eval/rair_test_*_summary.json`、`build/rair_eval/rair_test_negation_*_summary.json`、`build/rair_eval/rair_test_multi_intent_*_summary.json`。

## Legacy HSC 归档

`artifacts/paper_final_v2/` 和 `build/eval/final_v2/` 属于旧版 HSC-RAG-DE / HSC-DisasterBench-v2 实验归档。它们可以用于历史背景、方法演进或附录说明，但不要作为当前 RAIR-RAG 论文的主实验表格、主结论或当前 benchmark 结果来源。

推荐阅读顺序：

1. `zh/01_论文定位与贡献.md`
2. `zh/04_Method.md`
3. `zh/05_Experimental_Setup.md`
4. `zh/06_Results.md`
5. `reproducibility.md`
6. `tables.md`
7. `figures.md`
