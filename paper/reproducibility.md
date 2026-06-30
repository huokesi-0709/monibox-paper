# 复现实验说明

当前复现说明对应 RAIR-RAG-Bench。旧版 `profiles/paper_eval.yaml`、`build/eval/` 和 `artifacts/paper_final_v2/` 属于 HSC-RAG-DE 历史实验线，不作为当前论文主结果来源。

## 数据与边界

主数据：

```text
benchmarks/rair_rag/data/gold/rair_gold_all.jsonl
benchmarks/rair_rag/data/dev/rair_dev.jsonl
benchmarks/rair_rag/data/test/rair_test.jsonl
benchmarks/rair_rag/data/test/rair_test_negation.jsonl
benchmarks/rair_rag/data/test/rair_test_multi_intent.jsonl
```

`dev` 仅用于开发、阈值选择和 DE calibration；`test`、`test_negation`、`test_multi_intent` 用于最终报告。

## 推荐命令

在支持 bash 的环境中：

```bash
bash scripts/run_rair_eval.sh
uv run python -m experiments.de_routing_optimize
```

Windows 环境如无 bash，可直接运行：

```bash
uv run python -m benchmarks.rair_rag.run_routing_eval \
  --data benchmarks/rair_rag/data/test/rair_test.jsonl \
  --method risk-router \
  --policy scoring/routing_policy_manual.yaml \
  --out build/rair_eval/rair_test_risk-router-manual_predictions.jsonl \
  --summary build/rair_eval/rair_test_risk-router-manual_summary.json
```

其他方法和子集使用同一 entry point，替换 `--data`、`--method`、`--policy`、`--out` 和 `--summary` 即可。

## 输出目录

主要输出目录：

```text
build/rair_eval/
```

主要文件：

```text
build/rair_eval/rair_test_*_summary.json
build/rair_eval/rair_test_negation_*_summary.json
build/rair_eval/rair_test_multi_intent_*_summary.json
build/rair_eval/de_summary.json
build/rair_eval/de_trials.jsonl
```

## 安全边界

RAIR-RAG 评估的是检索前风险上下文构建和输入路由，不评估医疗诊断能力，不替代专业救援或急救人员。数据集应表述为 guideline-informed, human-reviewed synthetic benchmark with label-level guideline references and explicit pending-source markers。

## Legacy HSC 复现

旧 HSC-RAG-DE 命令仍可用于历史复现：

```bash
bash scripts/run_clean_eval.sh
bash scripts/run_robust_eval.sh
bash scripts/run_de_optimize.sh
bash scripts/run_ablation.sh
bash scripts/export_tables.sh
```

这些命令产出的 `build/eval/` 和 `artifacts/paper_final_v2/` 不应混入当前 RAIR-RAG 主结果。
