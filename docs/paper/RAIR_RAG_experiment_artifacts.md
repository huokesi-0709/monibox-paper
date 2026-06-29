# RAIR-RAG 实验数据与产物清单

本文修订稿的当前主线是 RAIR-RAG：风险感知输入路由、否定冲突消解、多意图优先级路由，以及离线 routing policy 参数校准。

## 建议上传到 GitHub 的核心数据

```text
benchmarks/rair_rag/annotation/annotation_codebook.md
benchmarks/rair_rag/annotation/risk_taxonomy.yaml
benchmarks/rair_rag/sources/guideline_sources.yaml
benchmarks/rair_rag/templates/
benchmarks/rair_rag/data/candidates/rair_candidates.jsonl
benchmarks/rair_rag/data/gold/rair_gold_all.jsonl
benchmarks/rair_rag/data/dev/rair_dev.jsonl
benchmarks/rair_rag/data/test/rair_test.jsonl
benchmarks/rair_rag/data/test/rair_test_negation.jsonl
benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl
benchmarks/rair_rag/data/split_manifest.json
```

这些文件用于说明数据集构建、标注体系、dev/test 划分和主要 benchmark 样本。

## 建议上传到 GitHub 的实验结果

```text
build/rair_eval/*_summary.json
build/rair_eval/*_predictions.jsonl
build/rair_eval/de_trials.jsonl
build/rair_eval/de_summary.json
build/rair_eval/de_best_policy.yaml
scoring/routing_policy_manual.yaml
scoring/routing_policy_de.yaml
experiments/configs/de_routing.yaml
experiments/de_routing_optimize.py
scripts/run_rair_eval.sh
```

这些文件足够 ChatGPT 或审稿前自查脚本分析主实验、分扰动实验和 DE 校准效果。

## 不建议上传的中间文件

```text
build/rair_eval/de_routing/
build/eval/
__pycache__/
.pytest_cache/
.ruff_cache/
.venv/
```

`build/rair_eval/de_routing/` 是 DE 运行过程中的候选 policy 和临时预测文件，体积容易膨胀，且可以由 `de_trials.jsonl`、`de_summary.json` 和配置文件复现。`build/eval/` 是旧 HSC-RAG-DE 主线的历史产物，不再是当前 RAIR-RAG 论文修订的主实验依据。

## HSC-RAG-DE 当前地位

HSC-RAG-DE 不需要删除。它现在更适合作为：

1. 历史复现基线；
2. 旧版论文实验存档；
3. 与 RAIR-RAG 的方法边界对照。

当前论文写作中不要再把 HSC-RAG-DE 作为主贡献展开。新的主贡献应表述为：将否定冲突和多意图输入建模为离线灾害应急 RAG 的检索前风险路由问题，并通过风险上下文构建降低协议误触发和高风险意图漏检。
