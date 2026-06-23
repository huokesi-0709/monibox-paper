# 阶段 10：DE 离线权重优化

阶段 10 的作用是离线搜索 HSC-RAG rerank 的 scoring weight coefficients。当前实现使用 `pymoo` 提供的 Differential Evolution，在开发集上搜索一组重排权重，并输出 `scoring/policy_de.json`。

该阶段不训练模型参数，不学习医学规则，不调用远端 LLM，也不声称提出新的进化算法。论文中应表述为“使用现有 Differential Evolution 方法进行离线权重搜索”。

## 入口

配置文件：

```bash
experiments/configs/de_hsc_rag.yaml
```

推荐脚本：

```bash
scripts/run_de_optimize.sh
```

等价命令：

```bash
python -m experiments.de_pymoo_optimize --config experiments/configs/de_hsc_rag.yaml
```

## 数据边界

DE 只允许使用开发数据调参：

- `benchmarks/data/clean_dev.jsonl`
- `benchmarks/data/robustness_dev.jsonl`

`load_de_config()` 会拒绝 `clean_dev_path` 或 `robustness_dev_path` 中包含 `test` 的路径，避免把 final test set 用于权重搜索。

最终 test set 只能用于最终报告，不能在看到 test 结果后继续调整 DE 权重。

## 搜索空间

搜索空间来自：

```bash
scoring/search_space.json
```

当前权重变量包括：

- `w_vec`
- `w_sparse`
- `w_quality`
- `w_tag`
- `w_risk`
- `w_unsafe`
- `w_redundancy`

这些变量是 HSC-RAG rerank 的工程评分系数，不是概率分布。`HscRagPolicy.normalized_weights()` 是历史命名，实际行为是合并默认权重与 policy 权重，不要求所有权重和为 1。

## fitness

`experiments/hsc_objective.py` 中的 `compute_fitness()` 将多项 dev metrics 合成为单目标 fitness。主要正向项包括：

- clean route accuracy
- robust route accuracy
- evidence hit
- safety compliance
- robust consistency
- clarification appropriateness
- protocol hit/action correctness

主要惩罚项包括：

- high-risk miss penalty
- unsafe response penalty
- unsupported claim penalty
- latency penalty

clean 与 robust 的指标会通过 `merge_dev_metrics()` 合并。其中 high-risk recall 取两者较小值；unsafe response、unsupported claim、protocol false trigger 和 p95 latency 取两者较大值，以保守评估鲁棒性和安全边界。

## constraints

`HscRagWeightProblem` 同时记录约束违反情况。当前约束为：

- `high_risk_recall >= 0.95`
- `unsafe_response_rate <= 0.05`
- `protocol_false_trigger_rate <= 0.05`
- `p95_latency_ms <= latency_budget_ms`

这些约束是工程实验门槛，不是医学安全保证。

## 输出文件

DE 运行会生成：

- candidate policies：每次评估的候选 policy。
- trials CSV：每个 candidate 的 weights、fitness、核心 metrics、constraint violation 和 error。
- curve CSV：每次评估的 fitness 与 best fitness 曲线。
- best metrics JSON：最佳 trial 和最终输出路径。
- final policy：默认写入 `scoring/policy_de.json`。

`policy_de.json` 的 metadata 应记录：

- `optimizer = "pymoo.DE"`
- `seed`
- `n_eval`
- `best_fitness`
- `dev_datasets`

这些 metadata 用于阶段 11 导表和复现实验记录。

## 后续阶段

阶段 11 使用 `policy_de.json`、`main_results.csv/json` 和 `ablation_results.csv/json` 导出论文表格。

如果后续建立 final test set，只能使用已冻结的 `policy_de.json` 进行最终报告，不能再基于 final test set 调整搜索空间、fitness 或权重。
