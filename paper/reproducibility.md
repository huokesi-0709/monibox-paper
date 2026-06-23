# 复现实验说明

本文件说明论文工程链路的推荐复现实验命令。所有命令应在仓库根目录执行。

## Profile

论文实验使用：

```bash
profiles/paper_eval.yaml
```

该 profile 默认关闭远端 LLM、TTS、硬件、rewrite 等 demo 路径，并开启 paper trace。普通 API、frontend、voice、hardware 代码不作为当前论文主实验结果来源。

## 推荐命令

生成 robust dev 数据：

```bash
bash scripts/generate_robustness.sh
```

运行 clean evaluation：

```bash
bash scripts/run_clean_eval.sh
```

运行 robust evaluation：

```bash
bash scripts/run_robust_eval.sh
```

运行 DE 离线权重优化：

```bash
bash scripts/run_de_optimize.sh
```

运行 ablation evaluation：

```bash
bash scripts/run_ablation.sh
```

导出论文表格：

```bash
bash scripts/export_tables.sh
```

## 输出目录

主要输出目录：

```bash
build/eval
```

Markdown 表格目录：

```bash
build/eval/tables
```

阶段 11 导出的 CSV 包括 `main_results.csv`、`robustness_results.csv`、`ablation_results.csv`、`de_effect_results.csv`、`latency_memory_results.csv` 和 `trace_audit_results.csv`。

## 数据与调参边界

DE 只使用 dev 数据，包括 clean_dev 和 robustness_dev。final test set 不得用于 DE 调参、search space 调整或 fitness 设计。

当前 clean_dev / robustness_dev 仍为 dev/smoke 数据，不等同最终 SCI test set。论文中文稿中的结果应引用阶段 11 导出的表格，不得手写或编造数值。

## 安全边界

本仓库复现实验评估的是离线约束式应急回复生成链路，不提供医学诊断，不替代专业救援，也不保证救援结果。真实灾害环境仍需要独立硬件、现场、安全和伦理验证。
